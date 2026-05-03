import logging
import os
import time

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
        # Match a real browser's compression set (gzip + br + deflate).
        headers["Accept-Encoding"] = "gzip, deflate, br"
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


def get_auth_proxy_url() -> str | None:
    """Return the residential proxy URL for the L1 ``/auth/api-key`` call.

    Read from ``POLY_AUTH_PROXY`` env var; ``None`` when unset (direct
    path). Whitespace-only values are treated as unset so an empty .env
    line does not accidentally enable a broken proxy.
    """
    raw = os.environ.get("POLY_AUTH_PROXY", "").strip()
    return raw or None


def build_auth_http_client(timeout_s: float = 30.0) -> "httpx.Client":
    """Build a per-call httpx.Client for the L1 ``/auth/api-key`` endpoint.

    When ``POLY_AUTH_PROXY`` is set, the resulting client routes through
    the residential proxy. Otherwise it returns a direct client. Used ONLY
    for the auth call — all other traffic flows through the long-lived
    module-level ``_http_client`` to amortise connection setup cost.

    Args:
        timeout_s: Per-request timeout. Defaults to 30 s (auth derive can
            take 5-15 s on residential IPs).
    """
    proxy_url = get_auth_proxy_url()
    if proxy_url is None:
        return httpx.Client(http2=True, timeout=timeout_s)
    # httpx accepts either a single proxy string (applies to all schemes)
    # or a per-scheme dict ``{"https://": "..."}``. We default to the dict
    # form so a residential proxy that only serves HTTPS does not silently
    # bypass HTTP — the auth endpoint is HTTPS but defense-in-depth.
    return httpx.Client(
        http2=True,
        timeout=timeout_s,
        proxies={"https://": proxy_url, "http://": proxy_url},
    )

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
