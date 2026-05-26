from unittest import TestCase

from py_clob_client_v2.clob_types import CreateOrderOptions, OrderArgsV2, OrderType
from py_clob_client_v2.constants import AMOY, BYTES32_ZERO
from py_clob_client_v2.order_builder.builder import OrderBuilder
from py_clob_client_v2.order_builder.constants import BUY, SELL
from py_clob_client_v2.order_utils.model import SignedOrderV2, Side, SignatureTypeV2
from py_clob_client_v2.signer import Signer
from py_clob_client_v2.order_utils.model.order_data_v2 import order_to_json_v2
from py_clob_client_v2.utilities import (
    adjust_market_buy_amount,
    generate_orderbook_summary_hash,
    is_tick_size_smaller,
    parse_raw_orderbook_summary,
    price_valid,
)

# publicly known private key
private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
chain_id = AMOY
signer = Signer(private_key=private_key, chain_id=chain_id)
builder = OrderBuilder(signer)

TOKEN_ID = "71321045679252212594626385532706912750332728571942532289631379312455583992563"


class TestUtilities(TestCase):
    def test_parse_raw_orderbook_summary(self):
        raw = {
            "market": "0xbd31dc8a20211944f6b70f31557f1001557b59905b7738480ca09bd4532f84af",
            "asset_id": "52114319501245915516055106046884209969926127482827954674443846427813813222426",
            "bids": [
                {"price": "0.15", "size": "100"},
                {"price": "0.31", "size": "148.56"},
                {"price": "0.33", "size": "58"},
                {"price": "0.5", "size": "100"},
            ],
            "asks": [],
            "hash": "9d6d9e8831a150ac4cd878f99f7b2c6d419b875f",
            "min_order_size": "100",
            "neg_risk": False,
            "tick_size": "0.01",
            "timestamp": "123456789",
            "last_trade_price": "",
        }
        obs = parse_raw_orderbook_summary(raw)

        self.assertEqual(
            obs.market,
            "0xbd31dc8a20211944f6b70f31557f1001557b59905b7738480ca09bd4532f84af",
        )
        self.assertEqual(
            obs.asset_id,
            "52114319501245915516055106046884209969926127482827954674443846427813813222426",
        )
        self.assertEqual(obs.hash, "9d6d9e8831a150ac4cd878f99f7b2c6d419b875f")
        self.assertEqual(obs.timestamp, "123456789")
        self.assertEqual(obs.min_order_size, "100")
        self.assertFalse(obs.neg_risk)
        self.assertEqual(obs.tick_size, "0.01")
        self.assertIsNotNone(obs.asks)
        self.assertIsNotNone(obs.bids)
        self.assertEqual(len(obs.asks), 0)
        self.assertEqual(len(obs.bids), 4)
        self.assertEqual(obs.bids[0].price, "0.15")
        self.assertEqual(obs.bids[0].size, "100")
        self.assertEqual(obs.bids[3].price, "0.5")
        self.assertEqual(obs.bids[3].size, "100")

        # empty orderbook
        raw2 = {
            "market": "0xaabbcc",
            "asset_id": "100",
            "bids": [],
            "asks": [],
            "hash": "7f81a35a09e1933a96b05edb51ac4be4a6163146",
            "timestamp": "123456789",
            "min_order_size": "100",
            "neg_risk": False,
            "tick_size": "0.01",
            "last_trade_price": "",
        }
        obs2 = parse_raw_orderbook_summary(raw2)
        self.assertEqual(obs2.market, "0xaabbcc")
        self.assertEqual(len(obs2.asks), 0)
        self.assertEqual(len(obs2.bids), 0)

    def test_generate_orderbook_summary_hash(self):
        raw = {
            "market": "0xaabbcc",
            "asset_id": "100",
            "bids": [
                {"price": "0.3", "size": "100"},
                {"price": "0.4", "size": "100"},
            ],
            "asks": [
                {"price": "0.6", "size": "100"},
                {"price": "0.7", "size": "100"},
            ],
            "hash": "",
            "timestamp": "123456789",
            "min_order_size": "100",
            "neg_risk": False,
            "tick_size": "0.01",
            "last_trade_price": "0.5",
        }
        obs = parse_raw_orderbook_summary(raw)
        self.assertEqual(
            generate_orderbook_summary_hash(obs),
            "0458ea5755c9f73d64a14636fa5c36ed460ec394",
        )
        self.assertEqual(obs.hash, "0458ea5755c9f73d64a14636fa5c36ed460ec394")

    def test_order_to_json_v2_0_1(self):
        for side in [BUY, SELL]:
            for order_type in [OrderType.GTC, OrderType.GTD]:
                order = builder.build_order(
                    OrderArgsV2(
                        token_id=TOKEN_ID,
                        price=0.5,
                        size=100,
                        side=side,
                    ),
                    CreateOrderOptions(tick_size="0.1", neg_risk=False),
                )
                result = order_to_json_v2(order, "owner", order_type)
                o = result["order"]
                self.assertIsNotNone(o["salt"])
                self.assertIsNotNone(o["maker"])
                self.assertIsNotNone(o["signer"])
                self.assertIsNotNone(o["tokenId"])
                self.assertIsNotNone(o["makerAmount"])
                self.assertIsNotNone(o["takerAmount"])
                self.assertIsNotNone(o["signatureType"])
                self.assertIsNotNone(o["signature"])
                # V2-specific fields
                self.assertIn("timestamp", o)
                self.assertIn("metadata", o)
                self.assertIn("builder", o)
                # V1 fields must NOT be present
                self.assertNotIn("nonce", o)
                self.assertNotIn("feeRateBps", o)
                self.assertNotIn("taker", o)
                self.assertEqual(result["owner"], "owner")
                self.assertEqual(result["orderType"], order_type)
                self.assertFalse(result["deferExec"])

    def test_order_to_json_v2_0_01(self):
        for side in [BUY, SELL]:
            order = builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.56, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
            )
            result = order_to_json_v2(order, "owner", OrderType.GTC)
            o = result["order"]
            self.assertIsNotNone(o["salt"])
            self.assertIsNotNone(o["signature"])
            self.assertIn("timestamp", o)
            self.assertNotIn("nonce", o)
            self.assertNotIn("feeRateBps", o)

    def test_order_to_json_v2_0_001(self):
        for side in [BUY, SELL]:
            order = builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.056, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.001", neg_risk=False),
            )
            result = order_to_json_v2(order, "owner", OrderType.GTC)
            o = result["order"]
            self.assertIsNotNone(o["salt"])
            self.assertIsNotNone(o["signature"])
            self.assertIn("timestamp", o)
            self.assertNotIn("nonce", o)

    def test_order_to_json_v2_0_0001(self):
        for side in [BUY, SELL]:
            order = builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.0056, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.0001", neg_risk=False),
            )
            result = order_to_json_v2(order, "owner", OrderType.GTC)
            o = result["order"]
            self.assertIsNotNone(o["salt"])
            self.assertIsNotNone(o["signature"])
            self.assertIn("timestamp", o)
            self.assertNotIn("nonce", o)

    def test_order_to_json_v2_neg_risk(self):
        for tick_size, price in [("0.1", 0.5), ("0.01", 0.56), ("0.001", 0.056), ("0.0001", 0.0056)]:
            for side in [BUY, SELL]:
                order = builder.build_order(
                    OrderArgsV2(token_id=TOKEN_ID, price=price, size=10, side=side),
                    CreateOrderOptions(tick_size=tick_size, neg_risk=True),
                )
                result = order_to_json_v2(order, "owner", OrderType.GTC)
                o = result["order"]
                self.assertIsNotNone(o["salt"])
                self.assertIsNotNone(o["signature"])
                self.assertIn("timestamp", o)
                self.assertNotIn("nonce", o)
                self.assertNotIn("feeRateBps", o)

    def test_order_to_json_v2_defer_exec(self):
        order = builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=10, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        result = order_to_json_v2(order, "owner", OrderType.GTC, defer_exec=True)
        self.assertTrue(result["deferExec"])

    def test_is_tick_size_smaller(self):
        self.assertTrue(is_tick_size_smaller("0.01", "0.1"))
        self.assertTrue(is_tick_size_smaller("0.001", "0.01"))
        self.assertTrue(is_tick_size_smaller("0.0001", "0.001"))
        self.assertFalse(is_tick_size_smaller("0.1", "0.01"))
        self.assertFalse(is_tick_size_smaller("0.1", "0.1"))

    def test_adjust_market_buy_amount_sufficient_balance(self):
        # balance > total_cost: original amount returned unchanged
        result = adjust_market_buy_amount(
            amount=10.0,
            user_usdc_balance=100.0,
            price=0.5,
            fee_rate=0.25,
            fee_exponent=2.0,
        )
        self.assertEqual(result, 10.0)

    def test_adjust_market_buy_amount_platform_fee_only(self):
        # invariant: adjusted = balance - reserved_fee where reserved_fee uses original amount
        budget = 50.0
        price = 0.5
        fee_rate = 0.25
        fee_exponent = 2.0
        effective = adjust_market_buy_amount(
            amount=100.0,
            user_usdc_balance=budget,
            price=price,
            fee_rate=fee_rate,
            fee_exponent=fee_exponent,
        )
        platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
        reserved_fee = (budget / price) * platform_fee_rate  # fee based on balance (feeBaseAmount = min(100, 50) = 50)
        self.assertAlmostEqual(effective, budget - reserved_fee, delta=1e-10)

    def test_adjust_market_buy_amount_builder_fee_only(self):
        # invariant: adjusted = balance - reserved_builder_fee
        budget = 50.0
        price = 0.5
        builder_taker_fee_rate = 0.01
        effective = adjust_market_buy_amount(
            amount=100.0,
            user_usdc_balance=budget,
            price=price,
            fee_rate=0,
            fee_exponent=0,
            builder_taker_fee_rate=builder_taker_fee_rate,
        )
        reserved_builder_fee = budget * builder_taker_fee_rate
        self.assertAlmostEqual(effective, budget - reserved_builder_fee, delta=1e-10)

    def test_adjust_market_buy_amount_combined_fees(self):
        # invariant: adjusted = balance - reserved_platform_fee - reserved_builder_fee
        budget = 50.0
        price = 0.5
        fee_rate = 0.25
        fee_exponent = 2.0
        builder_taker_fee_rate = 0.01
        effective = adjust_market_buy_amount(
            amount=100.0,
            user_usdc_balance=budget,
            price=price,
            fee_rate=fee_rate,
            fee_exponent=fee_exponent,
            builder_taker_fee_rate=builder_taker_fee_rate,
        )
        platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
        reserved_platform_fee = (budget / price) * platform_fee_rate
        reserved_builder_fee = budget * builder_taker_fee_rate
        self.assertAlmostEqual(effective, budget - reserved_platform_fee - reserved_builder_fee, delta=1e-10)

    def test_adjust_market_buy_amount_price_near_boundary(self):
        # price near minimum tick (0.0001) — feeBaseAmount = min(100, 50) = 50 = balance
        budget = 50.0
        price = 0.0001
        fee_rate = 0.25
        fee_exponent = 2.0
        builder_taker_fee_rate = 0.01
        effective = adjust_market_buy_amount(
            amount=100.0,
            user_usdc_balance=budget,
            price=price,
            fee_rate=fee_rate,
            fee_exponent=fee_exponent,
            builder_taker_fee_rate=builder_taker_fee_rate,
        )
        platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
        reserved_platform_fee = (budget / price) * platform_fee_rate
        reserved_builder_fee = budget * builder_taker_fee_rate
        self.assertAlmostEqual(effective, budget - reserved_platform_fee - reserved_builder_fee, delta=1e-10)

    def test_adjust_market_buy_amount_exactly_at_limit(self):
        # balance == total_cost triggers the adjustment path
        price = 0.5
        fee_rate = 0.25
        fee_exponent = 2.0
        platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
        amount = 48.484848484848484
        platform_fee = (amount / price) * platform_fee_rate
        budget = amount + platform_fee  # exactly at limit
        effective = adjust_market_buy_amount(
            amount=amount,
            user_usdc_balance=budget,
            price=price,
            fee_rate=fee_rate,
            fee_exponent=fee_exponent,
        )
        recalc_fee = (effective / price) * platform_fee_rate
        self.assertAlmostEqual(effective + recalc_fee, budget, delta=1e-10)

    def test_price_valid(self):
        self.assertTrue(price_valid(0.5, "0.1"))
        self.assertTrue(price_valid(0.1, "0.1"))
        self.assertTrue(price_valid(0.9, "0.1"))
        self.assertFalse(price_valid(0.0, "0.1"))
        self.assertFalse(price_valid(1.0, "0.1"))

        self.assertTrue(price_valid(0.01, "0.01"))
        self.assertTrue(price_valid(0.99, "0.01"))
        self.assertFalse(price_valid(0.001, "0.01"))

        self.assertTrue(price_valid(0.5, "0.001"))
        self.assertFalse(price_valid(0.0001, "0.001"))
