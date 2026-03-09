import logging
import time

import httpx

from py_clob_client_v2.clob_types import (
    DropNotificationParams,
    OrdersScoringParams,
)
from ..exceptions import PolyApiException

logger = logging.getLogger(__name__)

GET = "GET"
POST = "POST"
DELETE = "DELETE"
PUT = "PUT"

_http_client = httpx.Client(http2=True)

def _overload_headers(method: str, headers: dict) -> dict:
    if headers is None:
        headers = {}
    headers["User-Agent"] = "py_clob_client_v2"
    headers["Accept"] = "*/*"
    headers["Connection"] = "keep-alive"
    headers["Content-Type"] = "application/json"
    if method == GET:
        headers["Accept-Encoding"] = "gzip"
    return headers

def _is_transient_error(exc: Exception, status_code: int = None) -> bool:
    """
    Returns True if the error is likely transient and worth retrying once.
    Matches: 5xx responses, network-level errors (connect, timeout, network).
    """
    if status_code is not None and 500 <= status_code < 600:
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
