from unittest import TestCase
from unittest.mock import MagicMock, patch

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import FeeInfo


HOST = "https://clob.example.com"
CHAIN_ID = 137
TOKEN_ID = "0xabc123"
CONDITION_ID = "0xdeadbeef"


def _make_client() -> ClobClient:
    return ClobClient(host=HOST, chain_id=CHAIN_ID)


def _inject_market_info(client: ClobClient, token_id: str, rate: float, exponent: float):
    """Simulate getClobMarketInfo populating all cache fields."""
    client._ClobClient__fee_infos[token_id] = FeeInfo(rate=rate, exponent=exponent)
    client._ClobClient__tick_sizes[token_id] = "0.01"
    client._ClobClient__neg_risk[token_id] = False
    client._ClobClient__token_condition_map[token_id] = CONDITION_ID


class TestFeeInfoDefaults(TestCase):
    def test_fee_info_defaults_are_zero(self):
        fi = FeeInfo()
        self.assertEqual(fi.rate, 0.0)
        self.assertEqual(fi.exponent, 0.0)

    def test_fee_info_explicit_values(self):
        fi = FeeInfo(rate=0.02, exponent=2.0)
        self.assertEqual(fi.rate, 0.02)
        self.assertEqual(fi.exponent, 2.0)


class TestGetFeeRateBps(TestCase):
    def test_returns_cached_rate_from_fee_rates(self):
        client = _make_client()
        client._ClobClient__fee_rates[TOKEN_ID] = 200
        with patch.object(client, "_get") as mock_get:
            rate = client.get_fee_rate_bps(TOKEN_ID)
        self.assertEqual(rate, 200)
        mock_get.assert_not_called()

    def test_does_not_use_fee_infos_as_cache(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)
        with patch.object(client, "_get", return_value={"base_fee": 200}) as mock_get:
            rate = client.get_fee_rate_bps(TOKEN_ID)
        self.assertEqual(rate, 200)
        mock_get.assert_called_once()

    def test_get_fee_rate_via_get_fee_rate_endpoint(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"base_fee": 200}) as mock_get:
            rate = client.get_fee_rate_bps(TOKEN_ID)
        self.assertEqual(rate, 200)
        mock_get.assert_called_once()

    def test_stores_in_fee_rates_cache_not_fee_infos(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"base_fee": 150}):
            client.get_fee_rate_bps(TOKEN_ID)
        self.assertEqual(client._ClobClient__fee_rates[TOKEN_ID], 150)
        self.assertNotIn(TOKEN_ID, client._ClobClient__fee_infos)

    def test_no_refetch_after_fee_rates_cache_hit(self):
        client = _make_client()
        client._ClobClient__fee_rates[TOKEN_ID] = 100
        with patch.object(client, "_get") as mock_get:
            client.get_fee_rate_bps(TOKEN_ID)
        mock_get.assert_not_called()

    def test_zero_when_base_fee_missing(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={}):
            rate = client.get_fee_rate_bps(TOKEN_ID)
        self.assertEqual(rate, 0)


class TestGetFeeRate(TestCase):
    def test_returns_cached_rate_from_market_info(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.07, exponent=1.0)
        self.assertEqual(client.get_fee_rate(TOKEN_ID), 0.07)

    def test_fetches_market_info_when_not_cached(self):
        client = _make_client()
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.04, "e": 1.0},
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            rate = client.get_fee_rate(TOKEN_ID)

        self.assertEqual(rate, 0.04)

    def test_no_refetch_after_cache_hit(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.05, exponent=1.0)

        with patch.object(client, "_get") as mock_get:
            rate = client.get_fee_rate(TOKEN_ID)

        self.assertEqual(rate, 0.05)
        mock_get.assert_not_called()

    def test_is_not_the_fee_rate_bps_endpoint_value(self):
        """get_fee_rate exposes the real per-market rate, distinct from the
        constant base_fee flag returned by get_fee_rate_bps."""
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.07, exponent=1.0)
        with patch.object(client, "_get", return_value={"base_fee": 1000}):
            base_fee = client.get_fee_rate_bps(TOKEN_ID)
        self.assertEqual(base_fee, 1000)
        self.assertEqual(client.get_fee_rate(TOKEN_ID), 0.07)


class TestGetFeeExponent(TestCase):
    def test_returns_cached_exponent_from_market_info(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)
        self.assertEqual(client.get_fee_exponent(TOKEN_ID), 2.0)

    def test_cache_hit_any_fee_info_entry(self):
        client = _make_client()
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=0.03, exponent=0.0)
        self.assertEqual(client.get_fee_exponent(TOKEN_ID), 0.0)

    def test_fetches_market_info_when_not_cached(self):
        client = _make_client()
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.02, "e": 4.0},
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            exponent = client.get_fee_exponent(TOKEN_ID)

        self.assertEqual(exponent, 4.0)

    def test_no_refetch_after_cache_hit(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=1.5)

        with patch.object(client, "_get") as mock_get:
            exponent = client.get_fee_exponent(TOKEN_ID)

        self.assertEqual(exponent, 1.5)
        mock_get.assert_not_called()


class TestGetClobMarketInfo(TestCase):
    def test_sets_fee_info_with_defaults_when_fd_missing(self):
        client = _make_client()

        response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
        }
        with patch.object(client, "_get", return_value=response):
            client.get_clob_market_info(CONDITION_ID)

        fi = client._ClobClient__fee_infos.get(TOKEN_ID)
        self.assertIsNotNone(fi)
        self.assertEqual(fi.rate, 0.0)
        self.assertEqual(fi.exponent, 0.0)

    def test_sets_fee_info_from_fd(self):
        client = _make_client()

        response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.03, "e": 2.0},
        }
        with patch.object(client, "_get", return_value=response):
            client.get_clob_market_info(CONDITION_ID)

        fi = client._ClobClient__fee_infos[TOKEN_ID]
        self.assertEqual(fi.rate, 0.03)
        self.assertEqual(fi.exponent, 2.0)

    def test_no_repeated_fetch_after_clob_market_info(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)

        with patch.object(client, "_get", return_value={"base_fee": 200}):
            fee_rate = client.get_fee_rate_bps(TOKEN_ID)
            fee_exponent = client.get_fee_exponent(TOKEN_ID)

        self.assertEqual(fee_rate, 200)
        self.assertEqual(fee_exponent, 2.0)


class TestEnsureMarketInfoCached(TestCase):
    def test_no_refetch_when_fee_infos_has_token(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)

        with patch.object(client, "_get") as mock_get:
            client._ClobClient__ensure_market_info_cached(TOKEN_ID)

        mock_get.assert_not_called()

    def test_fetches_when_not_in_fee_infos(self):
        client = _make_client()
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.01, "e": 1.0},
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            client._ClobClient__ensure_market_info_cached(TOKEN_ID)

        self.assertIn(TOKEN_ID, client._ClobClient__fee_infos)

    def test_get_fee_rate_endpoint_entry_blocks_refetch(self):
        client = _make_client()
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=0.05, exponent=0.0)
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        with patch.object(client, "_get") as mock_get:
            client._ClobClient__ensure_market_info_cached(TOKEN_ID)

        mock_get.assert_not_called()
