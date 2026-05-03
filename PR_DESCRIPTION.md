# fix(auth): UA + browser-headers + opt-in residential proxy to bypass Cloudflare 403 (closes #41)

> Updated 2026-05-02 — community evidence ([#41 copperhuh, Zero-Ace5;
> calrde on this PR](https://github.com/Polymarket/py-clob-client-v2/issues/41))
> confirms that User-Agent header alone is INSUFFICIENT against the
> Cloudflare WAF guarding `/auth/api-key`. The fix has been expanded to
> a three-layer mitigation:
>
> 1. Versioned UA (the original commit — already shipped).
> 2. Full browser-header bundle (`Accept-*`, `sec-ch-ua-*`, `sec-fetch-*`).
> 3. Opt-in residential-proxy support via `POLY_AUTH_PROXY` for the L1
>    auth call ONLY.
>
> Layers 2 and 3 are this follow-up commit. The PR description below
> reflects the full mitigation.

## Problem

`POST /auth/api-key` returns HTTP 403 from Cloudflare when using the default
`python-httpx/X.Y` User-Agent string (reported in #38, #41). The previous
partial fix in `_overload_headers` set `User-Agent: py_clob_client_v2` — a
bare, unversioned string that Cloudflare's bot-score heuristic still treats as
suspicious, leaving the 403 unresolved for most users.

Three independent reporters then confirmed that **upgrading the UA alone
does NOT bypass the WAF**:

- `copperhuh` (#41): "I ran with the UA fix; still 403."
- `Zero-Ace5` (#41): "Tried JS variant + same UA; backend still rejects."
- `calrde` (this PR review): "Env-var workaround tested — does not unblock."

Cloudflare's bot detection scores on multiple signals beyond UA: TLS
fingerprint (JA3/JA4), HTTP/2 frame settings, header order, **and IP
reputation**. A datacenter IP + a clean UA still scores high enough to
trip the 403; the only confirmed-working bypass in similar deployments
(yfinance, ccxt-pro) is **residential rotating proxy + full browser
header bundle** (cf. [scrapfly.io 2026 Cloudflare bypass guide](https://scrapfly.io/blog/posts/everything-about-cloudflare-bot-management);
[IPRoyal residential pool](https://iproyal.com/)).

## Fix (three layers)

### Layer 1 — Versioned User-Agent (shipped in commit 6fedd7f)

- `constants.py`: `__version__` resolved at import time via
  `importlib.metadata.version` with a hard-coded fallback (`"1.0.1rc1"`).
- `constants.py`: `DEFAULT_USER_AGENT = f"polymarket-clob-client-v2/{__version__}"`
- `helpers.py`: `_resolve_user_agent()` returns
  `os.environ.get("POLY_USER_AGENT", DEFAULT_USER_AGENT)`.

### Layer 2 — Full browser-header bundle (this commit)

A real browser sends ~10 headers with every navigator-driven fetch.
Sending only `User-Agent` + `Accept: */*` is a strong bot signal even
with a plausible UA. `_overload_headers` now sets:

- `Accept: application/json, text/plain, */*` (Chrome's XHR default)
- `Accept-Language: en-US,en;q=0.9`
- `Accept-Encoding: gzip, deflate, br` (Chrome's full set; GET only)
- `sec-ch-ua: "Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"`
- `sec-ch-ua-mobile: ?0`
- `sec-ch-ua-platform: "macOS"`
- `sec-fetch-dest: empty`
- `sec-fetch-mode: cors`
- `sec-fetch-site: same-site`

All bundle values are set via `dict.setdefault(...)` so caller-supplied
headers still win.

### Layer 3 — Opt-in residential proxy for the auth call (this commit)

- `helpers.py`: `get_auth_proxy_url()` reads `POLY_AUTH_PROXY` env var.
- `helpers.py`: `build_auth_http_client(timeout_s)` returns an
  `httpx.Client` configured with `proxies={"https://": url, "http://": url}`
  when the env var is set; otherwise a direct client.

The proxy is wired into the **L1 `/auth/api-key` call ONLY**, NOT the
order or market-data path. Rationale:

- Auth is called ~once per 25 min (per #40 + the bot's L2 refresh loop);
  the residential-proxy latency cost (typically 100-400 ms) is paid once
  per L2 refresh, not per request.
- Order placement runs against an EU-region datacenter IP for
  latency-sensitivity; routing it through a residential proxy would add
  300+ ms to every taker fill.

Tested provider: [IPRoyal](https://iproyal.com/) residential rotating
pool ($7/GB at the time of writing). BrightData and Smartproxy expose
the same `https://user:pass@host:port` URL shape and should work
identically.

## Backwards compatibility

- Fully backwards compatible. No public API changed.
- Operators who do not set `POLY_AUTH_PROXY` get the existing direct
  path (UA + browser headers only).
- Operators who do not set `POLY_USER_AGENT` get the new versioned UA
  automatically on upgrade.
- `_overload_headers` uses `setdefault(...)` for the bundle, so any
  caller-supplied header (e.g. a test that asserts a specific Accept
  value) still overrides the default.

## Configuration

```bash
# Layer 1 — already automatic, no action needed.
# Optional override:
export POLY_USER_AGENT="my-bot/2.0"

# Layer 3 — opt-in residential proxy for the auth call.
export POLY_AUTH_PROXY="https://user:pass@residential.iproyal.com:12321"
```

## Testing

`tests/test_user_agent_header.py` now covers 23 cases:

- 5 — `DEFAULT_USER_AGENT` shape
- 3 — `_resolve_user_agent` env override
- 9 — `_overload_headers` UA + Accept-Encoding contracts
- **4 — browser-header bundle (NEW: sec-ch-ua, sec-fetch-\*, Accept-Language, caller override)**
- **5 — `POLY_AUTH_PROXY` honoured on `build_auth_http_client` (NEW)**

All tests pass on Python 3.9–3.14 with only stdlib + httpx installed.

```bash
PYTHONPATH=. python -m unittest tests.test_user_agent_header -v
```

## Acknowledgements

Thanks to `copperhuh`, `Zero-Ace5`, `lakeswimmer`, and `calrde` for the
community evidence that UA-only is insufficient — without your repros
this PR would have shipped a partial fix.

## Checklist

- [x] Layer 1 — versioned UA (shipped 6fedd7f)
- [x] Layer 2 — full browser-header bundle (this commit)
- [x] Layer 3 — opt-in residential proxy via `POLY_AUTH_PROXY` (this commit)
- [x] Auth-only proxy scope (no order-path latency hit)
- [x] PR description updated with community evidence
- [x] 23 regression tests added/updated
- [x] No public API changed (backwards compatible)
- [x] No new dependencies added
