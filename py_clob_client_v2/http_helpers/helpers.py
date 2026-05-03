# `from __future__ import annotations` is REQUIRED here because the project
# declares ``python_requires=">=3.9.10"`` in setup.py and we use PEP 604
# union syntax (e.g. ``str | None``) on the auth-proxy helpers below. Without
# this import the module raises ``TypeError: unsupported operand type(s) for
# |: 'type' and 'NoneType'`` at import time on Python 3.9, taking the entire
# SDK down with it. Found by Cursor Bugbot on PR #42 (commit ba44d13).
from __future__ import annotations

import logging
import os
import time
from typing import Optional

import httpx

from py_clob_client_v2.clob_types import (
    BalanceAllowanceParams,
    DropNotificationParams,
    OpenOrderParams,
    OrderScoringParams,
    OrdersScoringParams,
    TradeParams,
)
from ..constants import DEFAULT_USER_AGENT
from ..exceptions import PolyApiException

logger = logging.getLogger(__name__)

GET = "GET"
POST = "POST"
DELETE = "DELETE"
PUT = "PUT"

_http_client = httpx.Client(http2=True)


def _resolve_user_agent() -> str:
    """Return the effective User-Agent string.

    Precedence (highest to lowest):

    1. ``POLY_USER_AGENT`` environment variable — allows operators to inject a
       custom UA without patching the library (useful for whitelisted IPs or
       enterprise Cloudflare bypass tokens).
    2. ``DEFAULT_USER_AGENT`` constant — ``polymarket-clob-client-v2/{version}``
       which resolves the Cloudflare 403 on ``/auth/api-key`` (issues #38 / #41).
    """
    return os.environ.get("POLY_USER_AGENT", DEFAULT_USER_AGENT)


# ---------------------------------------------------------------------------
# Browser-bundle headers (Phase 2 of UA-bypass — community-fix discovery
# 2026-05-02 confirmed UA-only is INSUFFICIENT against Cloudflare WAF).
#
# Cloudflare's bot-score layer scores on multiple signals: User-Agent,
# Accept, Accept-Language, Accept-Encoding, sec-ch-ua, sec-fetch-*. A bare
# UA string + ``Accept: */*`` still trips the heuristic on residential
# datacenter IPs without a JS challenge. This bundle mirrors a recent
# Chrome 124 GET so the request looks like a navigator-driven call.
#
# Source: scrapfly.io 2026 Cloudflare bypass guide; cross-referenced against
# IPRoyal's residential-proxy header recipe for the same use case.
# ---------------------------------------------------------------------------
_BROWSER_HEADER_BUNDLE = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
}


def _overload_headers(method: str, headers: dict) -> dict:
    if headers is None:
        headers = {}
    headers["User-Agent"] = _resolve_user_agent()
    # Browser-bundle defaults — only set when the caller has not already
    # provided the header (preserves existing test contracts).
    for key, value in _BROWSER_HEADER_BUNDLE.items():
        headers.setdefault(key, value)
    headers["Connection"] = "keep-alive"
    headers["Content-Type"] = "application/json"
    if method == GET:
        # Advertise ONLY codecs httpx can decode out of the box. Brotli
        # (``br``) is intentionally omitted because the ``brotli`` /
        # ``brotlicffi`` packages are not in install_requires — advertising
        # ``br`` would let Cloudflare answer with ``Content-Encoding: br``
        # and httpx would fail to decode the response body. ``gzip`` +
        # ``deflate`` is sufficient to look like a modern client without
        # introducing a new mandatory dependency. Found by Cursor Bugbot on
        # PR #42 (commit ba44d13).
        headers["Accept-Encoding"] = "gzip, deflate"
    return headers


# ---------------------------------------------------------------------------
# Residential-proxy support for the auth-only path (Phase 2 of UA-bypass).
#
# Community-fix discovery 2026-05-02: UA-only is insufficient because
# Cloudflare's WAF also checks TLS JA3/JA4 and IP reputation. The only
# confirmed-working bypass is a residential rotating proxy + the full
# browser-header bundle above. We expose this through ``POLY_AUTH_PROXY``
# so operators can route ONLY the L1 ``/auth/api-key`` call through a
# residential proxy (e.g. IPRoyal, BrightData) while keeping every other
# call on the direct path — the latency cost is paid once per L2 refresh.
#
# The auth client is constructed lazily so the proxy URL is read at first
# use (not at module import time); operators that toggle the env var at
# runtime get the new value on the next refresh cycle.
# ---------------------------------------------------------------------------


def get_auth_proxy_url() -> Optional[str]:
    """Return the residential proxy URL for the L1 ``/auth/api-key`` call.

    Read from ``POLY_AUTH_PROXY`` env var; ``None`` when unset (direct
    path). Whitespace-only values are treated as unset so an empty .env
    line does not accidentally enable a broken proxy.

    Type annotation uses ``Optional[str]`` (not ``str | None``) so the
    module imports cleanly on Python 3.9 even if ``from __future__ import
    annotations`` is removed by a future maintainer.
    """
    raw = os.environ.get("POLY_AUTH_PROXY", "").strip()
    return raw or None


def build_auth_http_client(timeout_s: float = 30.0) -> httpx.Client:
    """Build a per-call httpx.Client for the L1 ``/auth/api-key`` endpoint.

    When ``POLY_AUTH_PROXY`` is set, the resulting client routes through
    the residential proxy. Otherwise it returns a direct client. Used ONLY
    for the auth call (``create_api_key`` / ``derive_api_key`` via
    ``client._l1_post`` / ``client._l1_get``) — all other traffic flows
    through the long-lived module-level ``_http_client`` to amortise
    connection setup cost.

    httpx 0.28 removed the ``proxies={"https://": url, "http://": url}``
    kwarg. The replacement APIs are ``proxy=<single url>`` or
    ``mounts={scheme: HTTPTransport(proxy=...)}`` for per-scheme routing.
    We use the single-URL form because both schemes route to the same
    residential proxy — this is forward-compatible with httpx >=0.28
    and back-compatible with httpx >=0.27. Found by Cursor Bugbot on
    PR #42 (commit ba44d13).

    Args:
        timeout_s: Per-request timeout. Defaults to 30 s (auth derive can
            take 5-15 s on residential IPs).
    """
    proxy_url = get_auth_proxy_url()
    if proxy_url is None:
        return httpx.Client(http2=True, timeout=timeout_s)
    return httpx.Client(
        http2=True,
        timeout=timeout_s,
        proxy=proxy_url,
    )

def _auth_request_attempt(endpoint: str, method: str, headers, data, params):
    """Single auth-call attempt. Raises on non-200 or network error.

    Body of ``auth_request`` extracted so the retry wrapper can call it
    twice without duplicating the proxy-aware client construction. Each
    attempt builds a fresh ``httpx.Client`` so a transient connection
    leak in the proxy can't poison the retry.
    """
    with build_auth_http_client() as client:
        if isinstance(data, str):
            resp = client.request(
                method=method,
                url=endpoint,
                headers=headers,
                content=data.encode("utf-8"),
                params=params,
            )
        else:
            resp = client.request(
                method=method,
                url=endpoint,
                headers=headers,
                json=data,
                params=params,
            )

    if resp.status_code != 200:
        logger.error(
            "[py_clob_client_v2] auth request error status=%s url=%s body=%s",
            resp.status_code,
            endpoint,
            resp.text,
        )
        raise PolyApiException(resp)

    try:
        return resp.json()
    except ValueError:
        return resp.text


def auth_request(
    endpoint: str,
    method: str,
    headers=None,
    data=None,
    params=None,
    retry_on_error: bool = False,
):
    """L1-auth-only request path that honours ``POLY_AUTH_PROXY``.

    Identical surface to ``request()`` (same headers, same JSON encoding,
    same exception contract) but constructs a per-call ``httpx.Client``
    via ``build_auth_http_client()`` so the residential proxy actually
    gets used. Without this wiring, ``build_auth_http_client`` would be
    dead code and the proxy env var would have no effect — the four bug
    fixes on PR #42 require all three layers (UA + browser headers +
    proxy) to flow through the SAME request, and the L1 auth call is the
    one Cloudflare blocks.

    Closed as a context manager so the per-call client is disposed
    immediately after the auth call returns. The auth round-trip is rare
    (≤1× per L2 cache refresh, ≈1× per 25 min in production) so we do
    not amortise the connect cost — correctness > throughput here.

    ``retry_on_error`` mirrors the same flag on ``post()``: when True,
    a single transient-error retry (5xx response or network-level
    ``httpx.ConnectError`` / ``TimeoutException`` / ``NetworkError``) is
    attempted after a 30 ms back-off. Cursor Bugbot flagged on commit
    ``31134da`` that the original auth path went through ``self._post()``
    which forwarded ``self.retry_on_error`` to ``post()``, but the new
    ``auth_post()`` had silently dropped that semantic — restored here.

    Found by Cursor Bugbot on PR #42:
      - commit ba44d13: ``build_auth_http_client`` was defined but never
        invoked, leaving Layer 3 of the bypass non-functional.
      - commit 31134da: ``auth_post`` lost ``retry_on_error`` parity
        with the previous ``self._post()`` path.
    """
    headers = _overload_headers(method, headers)
    try:
        return _auth_request_attempt(endpoint, method, headers, data, params)
    except (PolyApiException, httpx.RequestError) as exc:
        status = getattr(exc, "status_code", None)
        if retry_on_error and _is_transient_error(exc, status):
            logger.info(
                "[py_clob_client_v2] auth transient error, retrying once after 30 ms"
            )
            time.sleep(0.03)
            try:
                return _auth_request_attempt(
                    endpoint, method, headers, data, params
                )
            except httpx.RequestError as retry_exc:
                logger.error(
                    "[py_clob_client_v2] auth retry failed: %s", retry_exc
                )
                raise PolyApiException(error_msg="Auth request exception!")
        if isinstance(exc, PolyApiException):
            raise
        logger.error("[py_clob_client_v2] auth request error: %s", exc)
        raise PolyApiException(error_msg="Auth request exception!")


def auth_get(endpoint, headers=None, data=None, params=None, retry_on_error: bool = False):
    return auth_request(endpoint, GET, headers, data, params, retry_on_error=retry_on_error)


def auth_post(endpoint, headers=None, data=None, params=None, retry_on_error: bool = False):
    return auth_request(endpoint, POST, headers, data, params, retry_on_error=retry_on_error)


def _is_transient_error(exc: Exception, status_code: int = None) -> bool:
    """
    Returns True if the error is likely transient and worth retrying once.
    Matches: 5xx responses, network-level errors (connect, timeout, network).
    """
    if status_code is not None and 500 <= status_code < 600:
        return True
    if isinstance(exc, PolyApiException) and exc.status_code is None:
        return True
    return isinstance(
        exc,
        (httpx.ConnectError, httpx.TimeoutException, httpx.NetworkError),
    )

def request(endpoint: str, method: str, headers=None, data=None, params=None):
    headers = _overload_headers(method, headers)
    try:
        if isinstance(data, str):
            resp = _http_client.request(
                method=method,
                url=endpoint,
                headers=headers,
                content=data.encode("utf-8"),
                params=params,
            )
        else:
            resp = _http_client.request(
                method=method,
                url=endpoint,
                headers=headers,
                json=data,
                params=params,
            )

        if resp.status_code != 200:
            # resp.text is the server response body (no credentials are logged here)
            logger.error(
                "[py_clob_client_v2] request error status=%s url=%s body=%s",
                resp.status_code,
                endpoint,
                resp.text,
            )
            raise PolyApiException(resp)

        try:
            return resp.json()
        except ValueError:
            return resp.text

    except PolyApiException:
        raise
    except httpx.RequestError as exc:
        logger.error("[py_clob_client_v2] request error: %s", exc)
        raise PolyApiException(error_msg="Request exception!")

def get(endpoint, headers=None, data=None, params=None):
    return request(endpoint, GET, headers, data, params)

def post(endpoint, headers=None, data=None, params=None, retry_on_error: bool = False):
    try:
        return request(endpoint, POST, headers, data, params)
    except (PolyApiException, Exception) as exc:
        status = getattr(exc, "status_code", None)
        if retry_on_error and _is_transient_error(exc, status):
            logger.info("[py_clob_client_v2] transient error, retrying once after 30 ms")
            time.sleep(0.03)
            return request(endpoint, POST, headers, data, params)
        raise

def delete(endpoint, headers=None, data=None, params=None):
    return request(endpoint, DELETE, headers, data, params)

def put(endpoint, headers=None, data=None, params=None):
    return request(endpoint, PUT, headers, data, params)

def build_query_params(url: str, param: str, val) -> str:
    last = url[-1]
    if last == "?":
        return "{}{}={}".format(url, param, val)
    return "{}&{}={}".format(url, param, val)

def add_query_trade_params(
    base_url: str, params: TradeParams = None, next_cursor: str = "MA=="
) -> str:
    url = base_url
    has_query = bool(next_cursor) or (
        bool(params)
        and any(
            [
                params.market,
                params.asset_id,
                params.after,
                params.before,
                params.maker_address,
                params.id,
            ]
        )
    )
    if has_query:
        url = url + "?"
    if params:
        if params.market:
            url = build_query_params(url, "market", params.market)
        if params.asset_id:
            url = build_query_params(url, "asset_id", params.asset_id)
        if params.after:
            url = build_query_params(url, "after", params.after)
        if params.before:
            url = build_query_params(url, "before", params.before)
        if params.maker_address:
            url = build_query_params(url, "maker_address", params.maker_address)
        if params.id:
            url = build_query_params(url, "id", params.id)
    if next_cursor:
        url = build_query_params(url, "next_cursor", next_cursor)
    return url

def add_query_open_orders_params(
    base_url: str, params: OpenOrderParams = None, next_cursor: str = "MA=="
) -> str:
    url = base_url
    has_query = bool(next_cursor) or (
        bool(params) and any([params.market, params.asset_id, params.id])
    )
    if has_query:
        url = url + "?"
    if params:
        if params.market:
            url = build_query_params(url, "market", params.market)
        if params.asset_id:
            url = build_query_params(url, "asset_id", params.asset_id)
        if params.id:
            url = build_query_params(url, "id", params.id)
    if next_cursor:
        url = build_query_params(url, "next_cursor", next_cursor)
    return url

def drop_notifications_query_params(
    base_url: str, params: DropNotificationParams = None
) -> str:
    url = base_url
    if params and params.ids:
        url = url + "?"
        url = build_query_params(url, "ids", ",".join(params.ids))
    return url

def add_balance_allowance_params_to_url(
    base_url: str, params: BalanceAllowanceParams = None
) -> str:
    url = base_url
    if params:
        url = url + "?"
        if params.asset_type:
            url = build_query_params(url, "asset_type", str(params.asset_type))
        if params.token_id:
            url = build_query_params(url, "token_id", params.token_id)
        if params.signature_type is not None:
            url = build_query_params(url, "signature_type", params.signature_type)
    return url

def add_order_scoring_params_to_url(
    base_url: str, params: OrderScoringParams = None
) -> str:
    url = base_url
    if params and params.orderId:
        url = url + "?"
        url = build_query_params(url, "order_id", params.orderId)
    return url

def add_orders_scoring_params_to_url(
    base_url: str, params: OrdersScoringParams = None
) -> str:
    url = base_url
    if params and params.orderIds:
        url = url + "?"
        url = build_query_params(url, "order_ids", ",".join(params.orderIds))
    return url

def parse_orders_scoring_params(params: OrdersScoringParams = None) -> dict:
    """Returns a query-params dict for the orders-scoring endpoint."""
    result = {}
    if params and params.orderIds:
        result["order_ids"] = ",".join(params.orderIds)
    return result

def parse_drop_notification_params(params: DropNotificationParams = None) -> dict:
    """Returns a query-params dict for the drop-notifications endpoint."""
    result = {}
    if params and params.ids:
        result["ids"] = ",".join(params.ids)
    return result
