from unittest import TestCase

from py_clob_client_v2 import ClobClient, MarketOrderArgsV2, OrderArgsV2
from py_clob_client_v2.endpoints import (
    GET_BUILDER_FEE_RATE,
    GET_CLOB_MARKET,
    GET_FEE_RATE,
    VERSION,
)


HOST = "https://clob.example.com"
CHAIN_ID = 80002
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
CONDITION_ID = "0x" + "ab" * 32
TOKEN_IDS = ("1234", "5678")
BUILDER_CODE = "0x" + "12" * 32


def _market_info() -> dict:
    return {
        "t": [{"t": token_id} for token_id in TOKEN_IDS],
        "mts": "0.01",
        "nr": False,
        "fd": {"r": 0.03, "e": 1.0},
    }


class TestClientOrderMetadataWarmup(TestCase):
    def setUp(self):
        self.client = ClobClient(host=HOST, chain_id=CHAIN_ID, key=PRIVATE_KEY)
        self.calls = []

    def _install_responses(self, version: int) -> None:
        def fake_get(endpoint, headers=None, data=None, params=None):
            del headers, data, params
            self.calls.append(endpoint)
            if endpoint == f"{HOST}{GET_CLOB_MARKET}{CONDITION_ID}":
                return _market_info()
            if endpoint == f"{HOST}{VERSION}":
                return {"version": version}
            if endpoint.startswith(f"{HOST}{GET_FEE_RATE}"):
                return {"base_fee": 100}
            if endpoint == f"{HOST}{GET_BUILDER_FEE_RATE}{BUILDER_CODE}":
                return {
                    "builder_maker_fee_rate_bps": 0,
                    "builder_taker_fee_rate_bps": 25,
                }
            self.fail(f"unexpected GET {endpoint}")

        self.client._get = fake_get

    def test_successful_v2_warmup_removes_metadata_rest_from_first_orders(self):
        self._install_responses(version=2)
        self.client.warm_up_order_metadata(CONDITION_ID, builder_code=BUILDER_CODE)
        self.client.warm_up_order_metadata(CONDITION_ID, builder_code=BUILDER_CODE)
        self.assertEqual(
            self.calls.count(f"{HOST}{GET_BUILDER_FEE_RATE}{BUILDER_CODE}"),
            1,
        )
        self.calls.clear()

        limit_order = self.client.create_order(
            OrderArgsV2(
                token_id=TOKEN_IDS[0],
                price=0.5,
                size=10,
                side="BUY",
            )
        )
        market_order = self.client.create_market_order(
            MarketOrderArgsV2(
                token_id=TOKEN_IDS[1],
                amount=10,
                side="BUY",
                price=0.5,
                user_usdc_balance=100,
                builder_code=BUILDER_CODE,
            )
        )

        self.assertEqual(self.calls, [])
        self.assertTrue(limit_order.order_hash.startswith("0x"))
        self.assertTrue(market_order.order_hash.startswith("0x"))

    def test_successful_v1_warmup_caches_each_token_fee_cap(self):
        self._install_responses(version=1)
        self.client.warm_up_order_metadata(CONDITION_ID)
        self.calls.clear()

        signed_order = self.client.create_order(
            OrderArgsV2(
                token_id=TOKEN_IDS[0],
                price=0.5,
                size=10,
                side="BUY",
            )
        )

        self.assertEqual(self.calls, [])
        self.assertEqual(signed_order.feeRateBps, "100")
        self.assertTrue(signed_order.order_hash.startswith("0x"))
