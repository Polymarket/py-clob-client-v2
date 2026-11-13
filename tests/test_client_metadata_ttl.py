from unittest import TestCase
from unittest.mock import patch

from py_clob_client_v2.client import ClobClient


HOST = "https://clob.example.com"
CHAIN_ID = 137
TOKEN_ID = "0xabc123"
OTHER_TOKEN = "0xdef456"
CONDITION_ID = "0xdeadbeef"


class _FakeClock:
    """Monotonic-clock stub so TTL expiry is testable without sleeping."""

    def __init__(self, start=1000.0):
        self.now = start

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def _make_client(**kwargs) -> ClobClient:
    return ClobClient(host=HOST, chain_id=CHAIN_ID, **kwargs)


class _GetRecorder:
    """Stub for ClobClient._get that replays canned payloads per endpoint."""

    def __init__(self, payloads):
        self.payloads = payloads
        self.calls = []

    def __call__(self, url, params=None, headers=None, data=None):
        key = next((k for k in self.payloads if k in url), None)
        self.calls.append(url)
        if key is None:
            raise AssertionError(f"unexpected endpoint: {url}")
        queue = self.payloads[key]
        return queue.pop(0) if len(queue) > 1 else queue[0]


class TestMetadataTTLRefresh(TestCase):
    """Per-market metadata must be refetched once the TTL window expires."""

    def _run(self, getter, endpoint, first, second):
        client = _make_client(metadata_ttl=300.0)
        clock = _FakeClock()
        recorder = _GetRecorder({endpoint: [first, second]})
        with patch.object(client, "_get", recorder), patch(
            "py_clob_client_v2.client.time.monotonic", clock
        ):
            self.assertEqual(getter(client, TOKEN_ID), first["expected"](first))
            self.assertEqual(len(recorder.calls), 1)

            clock.advance(299.0)
            self.assertEqual(getter(client, TOKEN_ID), first["expected"](first))
            self.assertEqual(len(recorder.calls), 1, "inside TTL: must not refetch")

            clock.advance(2.0)
            self.assertEqual(
                getter(client, TOKEN_ID),
                second["expected"](second),
                "after TTL: server-side change must be observed",
            )
        self.assertEqual(len(recorder.calls), 2)

    def test_tick_size_refetches_after_ttl(self):
        self._run(
            lambda c, t: c.get_tick_size(t),
            "/tick-size",
            {"minimum_tick_size": 0.01, "expected": lambda p: "0.01"},
            {"minimum_tick_size": 0.001, "expected": lambda p: "0.001"},
        )

    def test_neg_risk_refetches_after_ttl(self):
        self._run(
            lambda c, t: c.get_neg_risk(t),
            "/neg-risk",
            {"neg_risk": False, "expected": lambda p: False},
            {"neg_risk": True, "expected": lambda p: True},
        )

    def test_fee_rate_bps_refetches_after_ttl(self):
        self._run(
            lambda c, t: c.get_fee_rate_bps(t),
            "/fee-rate",
            {"base_fee": 0, "expected": lambda p: 0},
            {"base_fee": 200, "expected": lambda p: 200},
        )


class TestMetadataTTLServesCache(TestCase):
    def test_default_ttl_matches_tick_size_convention(self):
        client = _make_client()
        self.assertEqual(client._ClobClient__metadata_ttl, 300.0)

    def test_no_network_inside_ttl_for_all_three_getters(self):
        client = _make_client(metadata_ttl=300.0)
        clock = _FakeClock()
        recorder = _GetRecorder(
            {
                "/tick-size": [{"minimum_tick_size": 0.01}],
                "/neg-risk": [{"neg_risk": False}],
                "/fee-rate": [{"base_fee": 100}],
            }
        )
        with patch.object(client, "_get", recorder), patch(
            "py_clob_client_v2.client.time.monotonic", clock
        ):
            for getter, expected in (
                (lambda: client.get_tick_size(TOKEN_ID), "0.01"),
                (lambda: client.get_neg_risk(TOKEN_ID), False),
                (lambda: client.get_fee_rate_bps(TOKEN_ID), 100),
            ):
                self.assertEqual(getter(), expected)
                clock.advance(1.0)
                self.assertEqual(getter(), expected)
        self.assertEqual(len(recorder.calls), 3, "one fetch per getter, no refetch")


class TestMetadataCacheScoping(TestCase):
    def test_cache_is_scoped_per_token(self):
        client = _make_client(metadata_ttl=300.0)
        clock = _FakeClock()

        def fake_get(url, params=None, headers=None, data=None):
            token = params.get("token_id")
            seen[token] = seen.get(token, 0) + 1
            return {"base_fee": 10 if token == TOKEN_ID else 20}

        seen = {}
        with patch.object(client, "_get", fake_get), patch(
            "py_clob_client_v2.client.time.monotonic", clock
        ):
            self.assertEqual(client.get_fee_rate_bps(TOKEN_ID), 10)
            self.assertEqual(client.get_fee_rate_bps(OTHER_TOKEN), 20)
            self.assertEqual(client.get_fee_rate_bps(TOKEN_ID), 10)
        self.assertEqual(seen[TOKEN_ID], 1)
        self.assertEqual(seen[OTHER_TOKEN], 1)

    def test_market_info_warm_cache_is_also_ttl_gated(self):
        client = _make_client(metadata_ttl=300.0)
        clock = _FakeClock()
        recorder = _GetRecorder(
            {
                "/clob-markets/": [
                    {"t": [{"t": TOKEN_ID}], "mts": "0.01", "nr": False},
                    {"t": [{"t": TOKEN_ID}], "mts": "0.001", "nr": False},
                ],
            }
        )
        with patch.object(client, "_get", recorder), patch(
            "py_clob_client_v2.client.time.monotonic", clock
        ):
            client.get_clob_market_info(CONDITION_ID)
            self.assertEqual(client.get_tick_size(TOKEN_ID), "0.01")
            self.assertEqual(len(recorder.calls), 1, "warm cache must not refetch")
            clock.advance(301.0)
            self.assertEqual(
                client.get_tick_size(TOKEN_ID),
                "0.001",
                "stale warm entry must be refreshed after TTL",
            )
        self.assertEqual(len(recorder.calls), 2)


class TestClearMetadataCache(TestCase):
    def test_clear_single_token_forces_refresh(self):
        client = _make_client(metadata_ttl=300.0)
        recorder = _GetRecorder(
            {
                "/neg-risk": [{"neg_risk": False}, {"neg_risk": True}],
            }
        )
        with patch.object(client, "_get", recorder):
            self.assertIs(client.get_neg_risk(TOKEN_ID), False)
            client.clear_metadata_cache(TOKEN_ID)
            self.assertIs(client.get_neg_risk(TOKEN_ID), True)
        self.assertEqual(len(recorder.calls), 2)

    def test_clear_all_drops_every_bucket(self):
        client = _make_client(metadata_ttl=300.0)
        recorder = _GetRecorder(
            {
                "/tick-size": [{"minimum_tick_size": 0.01}],
                "/neg-risk": [{"neg_risk": True}],
                "/fee-rate": [{"base_fee": 50}],
            }
        )
        with patch.object(client, "_get", recorder):
            client.get_tick_size(TOKEN_ID)
            client.get_neg_risk(TOKEN_ID)
            client.get_fee_rate_bps(TOKEN_ID)
            client.clear_metadata_cache()
            buckets = [
                client._ClobClient__tick_sizes,
                client._ClobClient__neg_risk,
                client._ClobClient__fee_rates,
                client._ClobClient__metadata_stamps,
            ]
            for bucket in buckets:
                self.assertEqual(len(bucket), 0)
            self.assertEqual(client.get_tick_size(TOKEN_ID), "0.01")
        self.assertEqual(len(recorder.calls), 4, "three fetches + one refetch")


class TestBackwardCompatibleInjection(TestCase):
    """Entries written outside the client (legacy tests, subclasses) must
    keep the pre-TTL immortal behaviour — no surprise refetch."""

    def test_direct_injection_without_timestamp_is_served_forever(self):
        client = _make_client(metadata_ttl=300.0)
        clock = _FakeClock()
        client._ClobClient__tick_sizes[TOKEN_ID] = "0.01"
        client._ClobClient__neg_risk[TOKEN_ID] = True
        client._ClobClient__fee_rates[TOKEN_ID] = 100
        with patch.object(client, "_get") as mock_get, patch(
            "py_clob_client_v2.client.time.monotonic", clock
        ):
            clock.advance(10_000.0)
            self.assertEqual(client.get_tick_size(TOKEN_ID), "0.01")
            self.assertIs(client.get_neg_risk(TOKEN_ID), True)
            self.assertEqual(client.get_fee_rate_bps(TOKEN_ID), 100)
        mock_get.assert_not_called()
