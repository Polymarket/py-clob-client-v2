"""
Tests for FeeInfo cache correctness in ClobClient.

Regression coverage for the bug where get_fee_rate_bps (GET_FEE_RATE fallback)
stored a FeeInfo with only rate set, causing get_fee_exponent to see the key and
return exponent=None (formerly 0.0) without ever fetching real market info.
"""

from unittest.mock import MagicMock, patch
import pytest

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import FeeInfo


HOST = "https://clob.example.com"
CHAIN_ID = 137
TOKEN_ID = "0xabc123"
CONDITION_ID = "0xdeadbeef"


def _make_client() -> ClobClient:
    return ClobClient(host=HOST, chain_id=CHAIN_ID)


def _inject_market_info(client: ClobClient, token_id: str, rate: float, exponent: float):
    """Simulate get_clob_market_info populating all cache fields."""
    fi = FeeInfo(rate=rate, exponent=exponent)
    client._ClobClient__fee_infos[token_id] = fi
    client._ClobClient__market_info_fetched.add(token_id)
    client._ClobClient__tick_sizes[token_id] = "0.01"
    client._ClobClient__neg_risk[token_id] = False
    client._ClobClient__token_condition_map[token_id] = CONDITION_ID


class TestFeeInfoSentinels:
    def test_fee_info_defaults_are_none(self):
        fi = FeeInfo()
        assert fi.rate is None
        assert fi.exponent is None

    def test_fee_info_explicit_values(self):
        fi = FeeInfo(rate=0.02, exponent=2.0)
        assert fi.rate == 0.02
        assert fi.exponent == 2.0


class TestGetFeeRateBps:
    def test_returns_cached_rate_from_market_info(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)
        assert client.get_fee_rate_bps(TOKEN_ID) == 0.02

    def test_rate_only_entry_does_not_satisfy_cache_check(self):
        """A FeeInfo with only rate set must NOT prevent fetching exponent later."""
        client = _make_client()
        # Simulate the GET_FEE_RATE fallback: rate stored, exponent still None
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=0.03, exponent=None)

        # get_fee_rate_bps should still return the cached rate
        assert client.get_fee_rate_bps(TOKEN_ID) == 0.03

    def test_get_fee_rate_fallback_does_not_block_exponent_fetch(self):
        """
        Core regression: after get_fee_rate_bps uses GET_FEE_RATE fallback,
        get_fee_exponent must still trigger __ensure_market_info_cached.
        """
        client = _make_client()

        # Simulate GET_FEE_RATE fallback storing rate-only FeeInfo
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=0.03, exponent=None)
        # token is NOT in __market_info_fetched

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.03, "e": 2.0},
            "mbf": 0,
            "tbf": 0,
        }

        with patch.object(client, "_get", return_value=clob_market_response) as mock_get, \
             patch.object(client, "_ClobClient__token_condition_map", {TOKEN_ID: CONDITION_ID}):
            exponent = client.get_fee_exponent(TOKEN_ID)

        assert exponent == 2.0
        mock_get.assert_called_once()

    def test_get_fee_rate_via_get_fee_rate_endpoint(self):
        client = _make_client()
        with patch.object(client, "_get", return_value={"base_fee": 0.05}) as mock_get:
            rate = client.get_fee_rate_bps(TOKEN_ID)
        assert rate == 0.05
        mock_get.assert_called_once()

    def test_get_fee_rate_preserves_existing_exponent(self):
        """GET_FEE_RATE fallback must not overwrite an existing exponent."""
        client = _make_client()
        # Exponent already populated (e.g. from a prior market info fetch)
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=None, exponent=3.0)

        with patch.object(client, "_get", return_value={"base_fee": 0.04}):
            client.get_fee_rate_bps(TOKEN_ID)

        fi = client._ClobClient__fee_infos[TOKEN_ID]
        assert fi.rate == 0.04
        assert fi.exponent == 3.0


class TestGetFeeExponent:
    def test_returns_cached_exponent_from_market_info(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)
        assert client.get_fee_exponent(TOKEN_ID) == 2.0

    def test_fetches_market_info_when_not_cached(self):
        client = _make_client()
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.02, "e": 4.0},
            "mbf": 0,
            "tbf": 0,
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            exponent = client.get_fee_exponent(TOKEN_ID)

        assert exponent == 4.0

    def test_exponent_only_entry_does_not_retrigger_fetch(self):
        client = _make_client()
        # Full market info fetched, exponent set
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=1.5)

        with patch.object(client, "_get") as mock_get:
            exponent = client.get_fee_exponent(TOKEN_ID)

        assert exponent == 1.5
        mock_get.assert_not_called()

    def test_rate_only_entry_still_triggers_market_info_fetch(self):
        """
        If rate was stored via GET_FEE_RATE but exponent is None,
        get_fee_exponent must fetch market info.
        """
        client = _make_client()
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=0.03, exponent=None)
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.03, "e": 2.0},
            "mbf": 0,
            "tbf": 0,
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            exponent = client.get_fee_exponent(TOKEN_ID)

        assert exponent == 2.0


class TestEnsureMarketInfoCached:
    def test_no_refetch_after_market_info_fetched(self):
        client = _make_client()
        _inject_market_info(client, TOKEN_ID, rate=0.02, exponent=2.0)

        with patch.object(client, "_get") as mock_get:
            client._ClobClient__ensure_market_info_cached(TOKEN_ID)

        mock_get.assert_not_called()

    def test_fetches_when_not_in_fetched_set(self):
        client = _make_client()
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.01, "e": 1.0},
            "mbf": 0,
            "tbf": 0,
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            client._ClobClient__ensure_market_info_cached(TOKEN_ID)

        assert TOKEN_ID in client._ClobClient__market_info_fetched

    def test_rate_only_in_fee_infos_still_triggers_fetch(self):
        """Even with a FeeInfo entry (rate only), fetch must occur if not in __market_info_fetched."""
        client = _make_client()
        client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=0.05, exponent=None)
        client._ClobClient__token_condition_map[TOKEN_ID] = CONDITION_ID

        clob_market_response = {
            "t": [{"t": TOKEN_ID}],
            "mts": "0.01",
            "nr": False,
            "fd": {"r": 0.05, "e": 3.0},
            "mbf": 0,
            "tbf": 0,
        }
        with patch.object(client, "_get", return_value=clob_market_response):
            client._ClobClient__ensure_market_info_cached(TOKEN_ID)

        fi = client._ClobClient__fee_infos[TOKEN_ID]
        assert fi.exponent == 3.0
        assert TOKEN_ID in client._ClobClient__market_info_fetched
