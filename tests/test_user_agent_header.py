"""
Regression test for issues #38 / #41.

Verifies that every outbound HTTP call made by the SDK includes a
User-Agent header whose value begins with "polymarket-clob-client-v2/"
(not the bare "python-httpx/X.Y" UA that Cloudflare's bot-detection
layer blocks on /auth/api-key).

Also verifies the POLY_USER_AGENT env-var override path.

Import strategy
---------------
We load only the two leaf modules under test (constants.py and
http_helpers/helpers.py) via their file paths so this test can run
without the full SDK dependency tree (eth-account, poly_eip712_structs,
h2, etc.) being installed.  When those extras ARE present the normal
``import py_clob_client_v2.xxx`` path works just as well; the test is
deliberately written to be runnable from a fresh checkout with only
``httpx`` installed (and even without it).
"""
import importlib.util
import os
import sys
import types
import unittest.mock as _mock
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Locate source root.  tests/test_user_agent_header.py -> ../py_clob_client_v2/
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_PKG_DIR = _REPO_ROOT / "py_clob_client_v2"


def _load_module_from_path(name: str, path: Path) -> types.ModuleType:
    """Load a single .py file as a top-level module without running __init__."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# 1. Load constants.py — only needs stdlib.
_constants = _load_module_from_path(
    "py_clob_client_v2.constants", _PKG_DIR / "constants.py"
)

# 2. Stub py_clob_client_v2.exceptions so helpers.py does not need the
#    full package chain.
_stub_exceptions = types.ModuleType("py_clob_client_v2.exceptions")


class _StubPolyApiException(Exception):
    def __init__(self, resp=None, error_msg: str = ""):
        self.status_code = getattr(resp, "status_code", None)


_stub_exceptions.PolyApiException = _StubPolyApiException  # type: ignore[attr-defined]
sys.modules["py_clob_client_v2.exceptions"] = _stub_exceptions

# 3. Stub py_clob_client_v2.clob_types (only the names helpers.py imports).
_stub_clob_types = types.ModuleType("py_clob_client_v2.clob_types")
for _n in (
    "BalanceAllowanceParams",
    "DropNotificationParams",
    "OpenOrderParams",
    "OrderScoringParams",
    "OrdersScoringParams",
    "TradeParams",
):
    setattr(_stub_clob_types, _n, object)
sys.modules["py_clob_client_v2.clob_types"] = _stub_clob_types

# 4. Stub or patch httpx so that httpx.Client(http2=True) does not require
#    the optional 'h2' package at module-load time.
try:
    import httpx as _httpx_real  # noqa: F401 — import to check availability
    # httpx is installed but h2 may be absent.  Patch the Client so the
    # module-level ``_http_client = httpx.Client(http2=True)`` succeeds.
    with _mock.patch("httpx.Client", return_value=_mock.MagicMock()):
        _helpers = _load_module_from_path(
            "py_clob_client_v2.http_helpers.helpers",
            _PKG_DIR / "http_helpers" / "helpers.py",
        )
except ImportError:
    # httpx not installed at all.
    _stub_httpx = types.ModuleType("httpx")
    _stub_httpx.Client = _mock.MagicMock(return_value=_mock.MagicMock())  # type: ignore[attr-defined]
    for _exc_cls in ("ConnectError", "TimeoutException", "NetworkError", "RequestError"):
        setattr(_stub_httpx, _exc_cls, Exception)
    sys.modules["httpx"] = _stub_httpx
    _helpers = _load_module_from_path(
        "py_clob_client_v2.http_helpers.helpers",
        _PKG_DIR / "http_helpers" / "helpers.py",
    )

# ---------------------------------------------------------------------------
# Bind the symbols under test at module level.
# ---------------------------------------------------------------------------
DEFAULT_USER_AGENT: str = _constants.DEFAULT_USER_AGENT
__version__: str = _constants.__version__

GET = _helpers.GET
POST = _helpers.POST
DELETE = _helpers.DELETE
PUT = _helpers.PUT
_overload_headers = _helpers._overload_headers
_resolve_user_agent = _helpers._resolve_user_agent

UA_PREFIX = "polymarket-clob-client-v2/"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestUserAgentDefault(TestCase):
    """DEFAULT_USER_AGENT constant has the right shape."""

    def test_version_is_non_empty(self) -> None:
        self.assertTrue(bool(__version__), "Package __version__ must be non-empty")

    def test_default_ua_starts_with_prefix(self) -> None:
        self.assertTrue(
            DEFAULT_USER_AGENT.startswith(UA_PREFIX),
            f"Expected DEFAULT_USER_AGENT to start with '{UA_PREFIX}', got: {DEFAULT_USER_AGENT!r}",
        )

    def test_default_ua_contains_version(self) -> None:
        self.assertIn(
            __version__,
            DEFAULT_USER_AGENT,
            f"DEFAULT_USER_AGENT must embed __version__ '{__version__}'; got: {DEFAULT_USER_AGENT!r}",
        )

    def test_default_ua_is_not_bare_python_httpx(self) -> None:
        self.assertFalse(
            DEFAULT_USER_AGENT.startswith("python-httpx"),
            "DEFAULT_USER_AGENT must NOT be the bare httpx UA — Cloudflare blocks it",
        )

    def test_default_ua_is_not_unversioned_package_name(self) -> None:
        # The OLD value that Cloudflare still blocked.
        self.assertNotEqual(
            DEFAULT_USER_AGENT,
            "py_clob_client_v2",
            "DEFAULT_USER_AGENT must not be the bare unversioned package name",
        )


class TestResolveUserAgent(TestCase):
    """_resolve_user_agent() respects POLY_USER_AGENT env override."""

    def test_returns_default_when_env_unset(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("POLY_USER_AGENT", None)
            ua = _resolve_user_agent()
        self.assertEqual(ua, DEFAULT_USER_AGENT)

    def test_returns_override_when_env_set(self) -> None:
        custom = "my-trading-bot/2.0"
        with patch.dict(os.environ, {"POLY_USER_AGENT": custom}):
            ua = _resolve_user_agent()
        self.assertEqual(ua, custom)

    def test_override_does_not_persist_after_context(self) -> None:
        with patch.dict(os.environ, {"POLY_USER_AGENT": "leaked-bot/1.0"}):
            pass
        os.environ.pop("POLY_USER_AGENT", None)
        ua = _resolve_user_agent()
        self.assertEqual(ua, DEFAULT_USER_AGENT)


class TestOverloadHeadersInjectsUA(TestCase):
    """_overload_headers() injects User-Agent on every HTTP method."""

    def _assert_ua(self, method: str, initial_headers: "dict | None") -> None:
        result = _overload_headers(method, initial_headers)
        self.assertIn("User-Agent", result, f"User-Agent missing for method={method}")
        self.assertTrue(
            result["User-Agent"].startswith(UA_PREFIX),
            f"User-Agent '{result['User-Agent']}' does not start with '{UA_PREFIX}' "
            f"for method={method}",
        )

    def test_get_request_includes_ua(self) -> None:
        self._assert_ua(GET, None)

    def test_post_request_includes_ua(self) -> None:
        self._assert_ua(POST, None)

    def test_delete_request_includes_ua(self) -> None:
        self._assert_ua(DELETE, None)

    def test_put_request_includes_ua(self) -> None:
        self._assert_ua(PUT, None)

    def test_existing_headers_dict_is_mutated_and_returned(self) -> None:
        headers = {"POLY_ADDRESS": "0xabc"}
        result = _overload_headers(POST, headers)
        self.assertIs(result, headers)
        self.assertIn("User-Agent", result)

    def test_none_headers_creates_new_dict(self) -> None:
        result = _overload_headers(GET, None)
        self.assertIsInstance(result, dict)
        self.assertIn("User-Agent", result)

    def test_get_includes_accept_encoding(self) -> None:
        # Phase 2 of UA-bypass: match Chrome's compression set so the WAF
        # fingerprint stays browser-shaped (community-fix discovery
        # 2026-05-02). The header must contain "gzip" but is no longer
        # exactly "gzip".
        result = _overload_headers(GET, None)
        ae = result.get("Accept-Encoding", "")
        self.assertIn("gzip", ae)

    def test_get_does_not_advertise_brotli_without_dep(self) -> None:
        # Cursor Bugbot (PR #42, commit ba44d13): advertising Brotli when
        # neither ``brotli`` nor ``brotlicffi`` is in install_requires
        # makes httpx fail to decode any ``Content-Encoding: br`` reply
        # from Cloudflare. Since brotli is NOT a declared dependency of
        # py-clob-client-v2, the Accept-Encoding header MUST omit "br".
        result = _overload_headers(GET, None)
        ae = result.get("Accept-Encoding", "")
        self.assertNotIn("br", ae.split(","), f"Accept-Encoding leaks 'br' without brotli dep: {ae!r}")
        # Sanity: deflate is fine because httpx ships built-in support.
        self.assertIn("deflate", ae)

    def test_post_omits_accept_encoding(self) -> None:
        result = _overload_headers(POST, None)
        self.assertNotIn("Accept-Encoding", result)

    def test_ua_env_override_flows_through_overload_headers(self) -> None:
        custom = "custom-operator-bot/3.0"
        with patch.dict(os.environ, {"POLY_USER_AGENT": custom}):
            result = _overload_headers(POST, None)
        self.assertEqual(result["User-Agent"], custom)


class TestBrowserHeaderBundle(TestCase):
    """Phase 2 of UA-bypass — full browser-header bundle on every request."""

    def test_get_includes_sec_ch_ua(self) -> None:
        result = _overload_headers(GET, None)
        self.assertIn("sec-ch-ua", result)
        self.assertIn("Chrome", result["sec-ch-ua"])

    def test_post_includes_sec_fetch_headers(self) -> None:
        result = _overload_headers(POST, None)
        self.assertIn("sec-fetch-mode", result)
        self.assertIn("sec-fetch-site", result)
        self.assertIn("sec-fetch-dest", result)

    def test_accept_language_is_set(self) -> None:
        result = _overload_headers(POST, None)
        self.assertIn("Accept-Language", result)
        self.assertTrue(result["Accept-Language"].startswith("en"))

    def test_caller_supplied_header_wins(self) -> None:
        """Operator-supplied Accept overrides the bundle default."""
        result = _overload_headers(POST, {"Accept": "application/vnd.custom"})
        self.assertEqual(result["Accept"], "application/vnd.custom")


class TestAuthProxySupport(TestCase):
    """Phase 2 of UA-bypass — POLY_AUTH_PROXY honoured on the auth client."""

    def test_get_auth_proxy_url_unset_returns_none(self) -> None:
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("POLY_AUTH_PROXY", None)
            self.assertIsNone(_helpers.get_auth_proxy_url())

    def test_get_auth_proxy_url_whitespace_returns_none(self) -> None:
        with patch.dict(os.environ, {"POLY_AUTH_PROXY": "   "}):
            self.assertIsNone(_helpers.get_auth_proxy_url())

    def test_get_auth_proxy_url_returns_value_when_set(self) -> None:
        url = "https://user:pass@proxy.example.com:1234"
        with patch.dict(os.environ, {"POLY_AUTH_PROXY": url}):
            self.assertEqual(_helpers.get_auth_proxy_url(), url)

    def test_build_auth_http_client_no_proxy_when_unset(self) -> None:
        """Without POLY_AUTH_PROXY, the auth client is built without proxy kwarg."""
        captured: dict = {}

        def _fake_client(*args, **kwargs):
            captured.update(kwargs)
            return _mock.MagicMock()

        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("POLY_AUTH_PROXY", None)
            with _mock.patch.object(_helpers, "httpx", _mock.MagicMock(Client=_fake_client)):
                _helpers.build_auth_http_client()
        # No proxy kwarg when env var is unset (httpx 0.28+ uses ``proxy=``,
        # not the removed ``proxies={...}`` dict).
        self.assertNotIn("proxy", captured)
        self.assertNotIn("proxies", captured)

    def test_build_auth_http_client_uses_proxy_when_set(self) -> None:
        """POLY_AUTH_PROXY=URL routes the auth call through the proxy.

        Cursor Bugbot (PR #42, commit ba44d13): the original
        ``proxies={"https://": ..., "http://": ...}`` form was removed in
        httpx 0.28. The replacement is ``proxy=<single url>``.
        """
        captured: dict = {}

        def _fake_client(*args, **kwargs):
            captured.update(kwargs)
            return _mock.MagicMock()

        url = "https://user:pass@proxy.example.com:1234"
        with patch.dict(os.environ, {"POLY_AUTH_PROXY": url}):
            with _mock.patch.object(_helpers, "httpx", _mock.MagicMock(Client=_fake_client)):
                _helpers.build_auth_http_client()
        # Forward-compatible with httpx >=0.28 (``proxy=``); the removed
        # ``proxies=`` kwarg must NOT be present.
        self.assertIn("proxy", captured)
        self.assertEqual(captured["proxy"], url)
        self.assertNotIn("proxies", captured)


class TestAuthRequestRoutesThroughProxy(TestCase):
    """auth_post / auth_get actually invoke build_auth_http_client.

    Cursor Bugbot (PR #42, commit ba44d13) flagged that
    ``build_auth_http_client`` was defined but never called from the
    auth path, leaving Layer 3 (residential proxy) entirely dead. These
    tests pin the wiring so a future refactor can't silently bypass it.
    """

    def test_auth_post_uses_build_auth_http_client(self) -> None:
        fake_resp = _mock.MagicMock(status_code=200)
        fake_resp.json.return_value = {"ok": True}
        fake_client = _mock.MagicMock()
        fake_client.__enter__ = lambda self: fake_client
        fake_client.__exit__ = lambda self, *a: None
        fake_client.request.return_value = fake_resp

        with _mock.patch.object(_helpers, "build_auth_http_client", return_value=fake_client) as builder:
            _helpers.auth_post("https://example.com/auth/api-key", headers={})

        builder.assert_called_once()
        fake_client.request.assert_called_once()
        # Method routed through must be POST.
        call_kwargs = fake_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["method"], "POST")

    def test_auth_get_uses_build_auth_http_client(self) -> None:
        fake_resp = _mock.MagicMock(status_code=200)
        fake_resp.json.return_value = {"ok": True}
        fake_client = _mock.MagicMock()
        fake_client.__enter__ = lambda self: fake_client
        fake_client.__exit__ = lambda self, *a: None
        fake_client.request.return_value = fake_resp

        with _mock.patch.object(_helpers, "build_auth_http_client", return_value=fake_client) as builder:
            _helpers.auth_get("https://example.com/auth/derive-api-key", headers={})

        builder.assert_called_once()
        call_kwargs = fake_client.request.call_args.kwargs
        self.assertEqual(call_kwargs["method"], "GET")

    def test_auth_request_injects_browser_headers(self) -> None:
        """auth_request still flows through _overload_headers (UA + bundle)."""
        fake_resp = _mock.MagicMock(status_code=200)
        fake_resp.json.return_value = {}
        fake_client = _mock.MagicMock()
        fake_client.__enter__ = lambda self: fake_client
        fake_client.__exit__ = lambda self, *a: None
        fake_client.request.return_value = fake_resp

        with _mock.patch.object(_helpers, "build_auth_http_client", return_value=fake_client):
            _helpers.auth_post("https://example.com/x", headers={})

        sent_headers = fake_client.request.call_args.kwargs["headers"]
        self.assertIn("User-Agent", sent_headers)
        self.assertTrue(sent_headers["User-Agent"].startswith(UA_PREFIX))
        self.assertIn("sec-ch-ua", sent_headers)


class TestAuthRetryOnErrorParity(TestCase):
    """auth_post / auth_get honour ``retry_on_error`` like ``post``/``get``.

    Cursor Bugbot (PR #42, commit 31134da) flagged that the new
    ``auth_post`` silently dropped the single-retry-on-transient
    semantic that the pre-31134da ``self._post()`` path forwarded from
    ``ClobClient.retry_on_error``. These tests pin the restored
    behaviour so a future refactor can't drop it again.
    """

    def _build_fake_client_returning(self, responses):
        """Yield each response in sequence; raise StopIteration after."""
        responses_iter = iter(responses)

        def _build():
            client = _mock.MagicMock()
            client.__enter__ = lambda self: client
            client.__exit__ = lambda self, *a: None

            def _do_request(*args, **kwargs):
                resp = next(responses_iter)
                if isinstance(resp, Exception):
                    raise resp
                return resp

            client.request.side_effect = _do_request
            return client

        return _build

    def test_auth_post_retries_on_500_when_retry_on_error_true(self) -> None:
        bad_resp = _mock.MagicMock(status_code=503, text="upstream down")
        good_resp = _mock.MagicMock(status_code=200)
        good_resp.json.return_value = {"ok": True}

        builds = [bad_resp, good_resp]
        idx = {"i": 0}

        def _build():
            client = _mock.MagicMock()
            client.__enter__ = lambda self: client
            client.__exit__ = lambda self, *a: None
            client.request.return_value = builds[idx["i"]]
            idx["i"] += 1
            return client

        with _mock.patch.object(_helpers, "build_auth_http_client", side_effect=_build):
            with _mock.patch.object(_helpers.time, "sleep"):
                result = _helpers.auth_post(
                    "https://example.com/auth/api-key",
                    headers={},
                    retry_on_error=True,
                )

        self.assertEqual(result, {"ok": True})
        self.assertEqual(idx["i"], 2, "expected exactly 2 attempts (1 retry)")

    def test_auth_post_does_not_retry_when_retry_on_error_false(self) -> None:
        bad_resp = _mock.MagicMock(status_code=503, text="upstream down")
        idx = {"i": 0}

        def _build():
            client = _mock.MagicMock()
            client.__enter__ = lambda self: client
            client.__exit__ = lambda self, *a: None
            client.request.return_value = bad_resp
            idx["i"] += 1
            return client

        with _mock.patch.object(_helpers, "build_auth_http_client", side_effect=_build):
            with self.assertRaises(_helpers.PolyApiException):
                _helpers.auth_post(
                    "https://example.com/auth/api-key",
                    headers={},
                    retry_on_error=False,
                )

        self.assertEqual(idx["i"], 1, "must NOT retry when retry_on_error=False")

    def test_auth_post_does_not_retry_on_400(self) -> None:
        """4xx is non-transient — must surface immediately even with retry_on_error=True."""
        bad_resp = _mock.MagicMock(status_code=401, text="Invalid api key")
        idx = {"i": 0}

        def _build():
            client = _mock.MagicMock()
            client.__enter__ = lambda self: client
            client.__exit__ = lambda self, *a: None
            client.request.return_value = bad_resp
            idx["i"] += 1
            return client

        with _mock.patch.object(_helpers, "build_auth_http_client", side_effect=_build):
            with self.assertRaises(_helpers.PolyApiException):
                _helpers.auth_post(
                    "https://example.com/auth/api-key",
                    headers={},
                    retry_on_error=True,
                )

        self.assertEqual(
            idx["i"], 1,
            "401/400 are non-transient — retry_on_error must NOT trigger",
        )

    def test_auth_get_forwards_retry_on_error_kwarg(self) -> None:
        """auth_get accepts and forwards retry_on_error to auth_request."""
        captured = {"retry": None}

        original = _helpers.auth_request

        def _spy(*args, **kwargs):
            captured["retry"] = kwargs.get("retry_on_error")
            # Short-circuit; we only care about the forward.
            return {"ok": True}

        with _mock.patch.object(_helpers, "auth_request", side_effect=_spy):
            _helpers.auth_get("https://example.com/x", headers={}, retry_on_error=True)

        self.assertIs(captured["retry"], True)


class TestPython39Compat(TestCase):
    """Module imports cleanly on Python 3.9 (PEP 604 union syntax safety).

    Cursor Bugbot (PR #42, commit ba44d13): ``str | None`` runtime union
    syntax is Python 3.10+. The project declares
    ``python_requires=">=3.9.10"``. Guard via ``from __future__ import
    annotations`` (or ``Optional[str]``). Both must be in place.
    """

    def test_helpers_module_has_future_annotations(self) -> None:
        src = (_PKG_DIR / "http_helpers" / "helpers.py").read_text()
        self.assertIn(
            "from __future__ import annotations",
            src,
            "helpers.py MUST import `from __future__ import annotations` "
            "to keep PEP 604 syntax safe on Python 3.9",
        )

    def test_get_auth_proxy_url_annotation_uses_optional(self) -> None:
        # Belt-and-braces: also use `Optional[str]` so the annotation is
        # safe even if the future import is later removed.
        src = (_PKG_DIR / "http_helpers" / "helpers.py").read_text()
        self.assertIn(
            "def get_auth_proxy_url() -> Optional[str]:",
            src,
            "get_auth_proxy_url() MUST use Optional[str] for Python 3.9 safety",
        )
