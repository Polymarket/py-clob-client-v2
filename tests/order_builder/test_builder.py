import asyncio
from unittest import TestCase

from py_clob_client_v2.clob_types import (
    CreateOrderOptions,
    MarketOrderArgsV1,
    MarketOrderArgsV2,
    OrderArgsV1,
    OrderArgsV2,
    OrderSummary,
    OrderType,
)
from py_clob_client_v2.constants import AMOY, BYTES32_ZERO, ZERO_ADDRESS
from py_clob_client_v2.order_builder.builder import OrderBuilder, ROUNDING_CONFIG
from py_clob_client_v2.order_builder.constants import BUY, SELL
from py_clob_client_v2.order_builder.helpers import decimal_places, round_down, round_normal
from py_clob_client_v2.order_utils.model import Side, SignatureTypeV2
from py_clob_client_v2.signer import Signer
from py_clob_client_v2.utilities import adjust_market_buy_amount

# publicly known private key
private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
chain_id = AMOY
signer = Signer(private_key=private_key, chain_id=chain_id)

TOKEN_ID = "71321045679252212594626385532706912750332728571942532289631379312455583992563"


def run_async(coro):
    return asyncio.run(coro)

class TestOrderBuilder(TestCase):

    def test_calculate_buy_market_price_FOK(self):
        builder = OrderBuilder(signer)

        with self.assertRaises(Exception):
            builder.calculate_buy_market_price([], 100, OrderType.FOK)

        with self.assertRaises(Exception):
            builder.calculate_buy_market_price(
                [OrderSummary(price="0.5", size="100"), OrderSummary(price="0.4", size="100")],
                100,
                OrderType.FOK,
            )

        positions = [
            OrderSummary(price="0.5", size="100"),
            OrderSummary(price="0.4", size="100"),
            OrderSummary(price="0.3", size="100"),
        ]
        self.assertEqual(builder.calculate_buy_market_price(positions, 100, OrderType.FOK), 0.5)

        positions = [
            OrderSummary(price="0.5", size="100"),
            OrderSummary(price="0.4", size="200"),
            OrderSummary(price="0.3", size="100"),
        ]
        self.assertEqual(builder.calculate_buy_market_price(positions, 100, OrderType.FOK), 0.4)

        positions = [
            OrderSummary(price="0.5", size="200"),
            OrderSummary(price="0.4", size="100"),
            OrderSummary(price="0.3", size="100"),
        ]
        self.assertEqual(builder.calculate_buy_market_price(positions, 100, OrderType.FOK), 0.5)

    def test_calculate_sell_market_price_FOK(self):
        builder = OrderBuilder(signer)

        with self.assertRaises(Exception):
            builder.calculate_sell_market_price([], 100, OrderType.FOK)

        with self.assertRaises(Exception):
            builder.calculate_sell_market_price(
                [OrderSummary(price="0.4", size="10"), OrderSummary(price="0.5", size="10")],
                100,
                OrderType.FOK,
            )

        positions = [
            OrderSummary(price="0.3", size="100"),
            OrderSummary(price="0.4", size="100"),
            OrderSummary(price="0.5", size="100"),
        ]
        self.assertEqual(builder.calculate_sell_market_price(positions, 100, OrderType.FOK), 0.5)

        positions = [
            OrderSummary(price="0.3", size="100"),
            OrderSummary(price="0.4", size="300"),
            OrderSummary(price="0.5", size="10"),
        ]
        self.assertEqual(builder.calculate_sell_market_price(positions, 100, OrderType.FOK), 0.4)

        positions = [
            OrderSummary(price="0.3", size="334"),
            OrderSummary(price="0.4", size="100"),
            OrderSummary(price="0.5", size="100"),
        ]
        self.assertEqual(builder.calculate_sell_market_price(positions, 300, OrderType.FOK), 0.3)

    def test_calculate_buy_market_price_FAK(self):
        builder = OrderBuilder(signer)

        with self.assertRaises(Exception):
            builder.calculate_buy_market_price([], 100, OrderType.FAK)

        # FAK accepts partial fills — no exception on insufficient liquidity
        positions = [
            OrderSummary(price="0.5", size="100"),
            OrderSummary(price="0.4", size="100"),
        ]
        self.assertEqual(builder.calculate_buy_market_price(positions, 100, OrderType.FAK), 0.5)

        positions = [
            OrderSummary(price="0.5", size="100"),
            OrderSummary(price="0.4", size="200"),
            OrderSummary(price="0.3", size="100"),
        ]
        self.assertEqual(builder.calculate_buy_market_price(positions, 100, OrderType.FAK), 0.4)

    def test_calculate_sell_market_price_FAK(self):
        builder = OrderBuilder(signer)

        with self.assertRaises(Exception):
            builder.calculate_sell_market_price([], 100, OrderType.FAK)

        # FAK accepts partial fills — returns positions[0].price (lowest bid) on insufficient liquidity
        positions = [
            OrderSummary(price="0.3", size="10"),
            OrderSummary(price="0.4", size="10"),
        ]
        self.assertEqual(builder.calculate_sell_market_price(positions, 100, OrderType.FAK), 0.3)

        positions = [
            OrderSummary(price="0.3", size="100"),
            OrderSummary(price="0.4", size="300"),
            OrderSummary(price="0.5", size="10"),
        ]
        self.assertEqual(builder.calculate_sell_market_price(positions, 100, OrderType.FAK), 0.4)

    def test_get_market_order_amounts_buy_0_1(self):
        builder = OrderBuilder(signer)
        delta_price = 0.1
        delta_size = 0.01
        amount = 0.01
        while amount <= 1000:
            price = 0.1
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    BUY, amount, price, ROUNDING_CONFIG["0.1"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 2), round_normal(price, 2)
                )
                price = round_normal(price + delta_price, 1)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_buy_0_01(self):
        builder = OrderBuilder(signer)
        delta_price = 0.01
        delta_size = 0.01
        amount = 0.01
        while amount <= 100:
            price = 0.01
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    BUY, amount, price, ROUNDING_CONFIG["0.01"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                # V2 uses round_down for raw_price; compare against round_down(price, 2)
                # to match the actual price used in computation (avoids float drift issues)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 4), round_down(price, 2)
                )
                price = round_normal(price + delta_price, 2)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_buy_0_001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.001
        delta_size = 0.01
        amount = 0.01
        while amount <= 10:
            price = 0.001
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    BUY, amount, price, ROUNDING_CONFIG["0.001"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 6), round_normal(price, 6)
                )
                price = round_normal(price + delta_price, 3)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_buy_0_0001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.0001
        delta_size = 0.01
        amount = 0.01
        while amount <= 1:
            price = 0.0001
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    BUY, amount, price, ROUNDING_CONFIG["0.0001"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                # V2 uses round_down for raw_price; compare against round_down(price, 4)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 8), round_down(price, 4)
                )
                price = round_normal(price + delta_price, 4)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_sell_0_1(self):
        builder = OrderBuilder(signer)
        delta_price = 0.1
        delta_size = 0.01
        amount = 0.01
        while amount <= 1000:
            price = 0.1
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    SELL, amount, price, ROUNDING_CONFIG["0.1"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 2), round_normal(price, 2)
                )
                price = round_normal(price + delta_price, 1)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_sell_0_01(self):
        builder = OrderBuilder(signer)
        delta_price = 0.01
        delta_size = 0.01
        amount = 0.01
        while amount <= 100:
            price = 0.01
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    SELL, amount, price, ROUNDING_CONFIG["0.01"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 4), round_normal(price, 4)
                )
                price = round_normal(price + delta_price, 2)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_sell_0_001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.001
        delta_size = 0.01
        amount = 0.01
        while amount <= 10:
            price = 0.001
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    SELL, amount, price, ROUNDING_CONFIG["0.001"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 6), round_normal(price, 6)
                )
                price = round_normal(price + delta_price, 3)
            amount = round_normal(amount + delta_size, 2)

    def test_get_market_order_amounts_sell_0_0001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.0001
        delta_size = 0.01
        amount = 0.01
        while amount <= 1:
            price = 0.0001
            while price <= 1:
                side, maker, taker = builder.get_market_order_amounts(
                    SELL, amount, price, ROUNDING_CONFIG["0.0001"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                # V2 uses round_down for raw_price; compare against round_down(price, 4)
                self.assertGreaterEqual(
                    round_normal(taker / maker, 8), round_down(price, 4)
                )
                price = round_normal(price + delta_price, 4)
            amount = round_normal(amount + delta_size, 2)

    def test_get_order_amounts_buy_0_1(self):
        builder = OrderBuilder(signer)
        delta_price = 0.1
        delta_size = 0.01
        size = 0.01
        while size <= 1000:
            price = 0.1
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    BUY, size, price, ROUNDING_CONFIG["0.1"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 2), round_normal(price, 2)
                )
                price = round_normal(price + delta_price, 1)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_buy_0_01(self):
        builder = OrderBuilder(signer)
        delta_price = 0.01
        delta_size = 0.01
        size = 0.01
        while size <= 100:
            price = 0.01
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    BUY, size, price, ROUNDING_CONFIG["0.01"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 4), round_normal(price, 4)
                )
                price = round_normal(price + delta_price, 2)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_buy_0_001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.001
        delta_size = 0.01
        size = 0.01
        while size <= 10:
            price = 0.001
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    BUY, size, price, ROUNDING_CONFIG["0.001"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 6), round_normal(price, 6)
                )
                price = round_normal(price + delta_price, 3)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_buy_0_0001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.0001
        delta_size = 0.01
        size = 0.01
        while size <= 1:
            price = 0.0001
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    BUY, size, price, ROUNDING_CONFIG["0.0001"]
                )
                self.assertEqual(side, Side.BUY)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                self.assertGreaterEqual(
                    round_normal(maker / taker, 8), round_normal(price, 8)
                )
                price = round_normal(price + delta_price, 4)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_sell_0_1(self):
        builder = OrderBuilder(signer)
        delta_price = 0.1
        delta_size = 0.01
        size = 0.01
        while size <= 1000:
            price = 0.1
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    SELL, size, price, ROUNDING_CONFIG["0.1"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                price = round_normal(price + delta_price, 1)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_sell_0_01(self):
        builder = OrderBuilder(signer)
        delta_price = 0.01
        delta_size = 0.01
        size = 0.01
        while size <= 100:
            price = 0.01
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    SELL, size, price, ROUNDING_CONFIG["0.01"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                price = round_normal(price + delta_price, 2)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_sell_0_001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.001
        delta_size = 0.01
        size = 0.01
        while size <= 10:
            price = 0.001
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    SELL, size, price, ROUNDING_CONFIG["0.001"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                price = round_normal(price + delta_price, 3)
            size = round_normal(size + delta_size, 2)

    def test_get_order_amounts_sell_0_0001(self):
        builder = OrderBuilder(signer)
        delta_price = 0.0001
        delta_size = 0.01
        size = 0.01
        while size <= 1:
            price = 0.0001
            while price <= 1:
                side, maker, taker = builder.get_order_amounts(
                    SELL, size, price, ROUNDING_CONFIG["0.0001"]
                )
                self.assertEqual(side, Side.SELL)
                self.assertEqual(decimal_places(maker), 0)
                self.assertEqual(decimal_places(taker), 0)
                price = round_normal(price + delta_price, 4)
            size = round_normal(size + delta_size, 2)

    def _assert_signed_order_v1(self, order):
        self.assertIsNotNone(order.salt)
        self.assertIsNotNone(order.maker)
        self.assertIsNotNone(order.signer)
        self.assertIsNotNone(order.tokenId)
        self.assertIsNotNone(order.makerAmount)
        self.assertIsNotNone(order.takerAmount)
        self.assertIsNotNone(order.signature)
        self.assertIsNotNone(order.feeRateBps)
        self.assertIsNotNone(order.nonce)
        self.assertIsNotNone(order.taker)
        # V1 has no timestamp, metadata, or builder
        self.assertFalse(hasattr(order, "timestamp"))
        self.assertFalse(hasattr(order, "metadata"))
        self.assertFalse(hasattr(order, "builder"))

    def _assert_signed_order_v2(self, order):
        self.assertIsNotNone(order.salt)
        self.assertIsNotNone(order.maker)
        self.assertIsNotNone(order.signer)
        self.assertIsNotNone(order.tokenId)
        self.assertIsNotNone(order.makerAmount)
        self.assertIsNotNone(order.takerAmount)
        self.assertIsNotNone(order.signature)
        self.assertIsNotNone(order.timestamp)
        self.assertIsNotNone(order.metadata)
        self.assertIsNotNone(order.builder)
        # V2 has no nonce or feeRateBps
        self.assertFalse(hasattr(order, "nonce"))
        self.assertFalse(hasattr(order, "feeRateBps"))

    def test_build_order_buy_0_1(self):
        builder = OrderBuilder(signer)
        order = run_async(builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=100, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.makerAmount, "50000000")
        self.assertEqual(order.takerAmount, "100000000")

    def test_build_order_sell_0_1(self):
        builder = OrderBuilder(signer)
        order = run_async(builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=100, side=SELL),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.SELL)
        self.assertEqual(order.makerAmount, "100000000")
        self.assertEqual(order.takerAmount, "50000000")

    def test_build_order_0_01(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = run_async(builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.56, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
            ))
            self._assert_signed_order_v2(order)
            if side == BUY:
                self.assertEqual(order.makerAmount, "11782400")
                self.assertEqual(order.takerAmount, "21040000")
            else:
                self.assertEqual(order.makerAmount, "21040000")
                self.assertEqual(order.takerAmount, "11782400")

    def test_build_order_0_001(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = run_async(builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.056, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.001", neg_risk=False),
            ))
            self._assert_signed_order_v2(order)
            if side == BUY:
                self.assertEqual(order.makerAmount, "1178240")
                self.assertEqual(order.takerAmount, "21040000")
            else:
                self.assertEqual(order.makerAmount, "21040000")
                self.assertEqual(order.takerAmount, "1178240")

    def test_build_order_0_0001(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = run_async(builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.0056, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.0001", neg_risk=False),
            ))
            self._assert_signed_order_v2(order)
            if side == BUY:
                self.assertEqual(order.makerAmount, "117824")
                self.assertEqual(order.takerAmount, "21040000")
            else:
                self.assertEqual(order.makerAmount, "21040000")
                self.assertEqual(order.takerAmount, "117824")

    def test_build_order_precision(self):
        # price=0.82, size=20.0 — tests rounding precision at 0.01 tick
        builder = OrderBuilder(signer)
        order = run_async(builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.82, size=20.0, side=BUY),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.makerAmount, "16400000")
        self.assertEqual(order.takerAmount, "20000000")

    def test_build_order_neg_risk(self):
        builder = OrderBuilder(signer)
        for tick_size, price in [("0.1", 0.5), ("0.01", 0.56), ("0.001", 0.056), ("0.0001", 0.0056)]:
            for side in [BUY, SELL]:
                order = run_async(builder.build_order(
                    OrderArgsV2(token_id=TOKEN_ID, price=price, size=10, side=side),
                    CreateOrderOptions(tick_size=tick_size, neg_risk=True),
                ))
                self._assert_signed_order_v2(order)

    def test_build_order_with_builder_code(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "ab" * 32
        order = run_async(builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=100, side=BUY, builder_code=builder_code),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)

    def test_build_order_poly_proxy_signature_type(self):
        b = OrderBuilder(signer, signature_type=SignatureTypeV2.POLY_PROXY)
        order = run_async(b.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=10, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.signatureType, SignatureTypeV2.POLY_PROXY)

    def test_build_order_gnosis_safe_signature_type(self):
        b = OrderBuilder(signer, signature_type=SignatureTypeV2.POLY_GNOSIS_SAFE)
        order = run_async(b.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=10, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.signatureType, SignatureTypeV2.POLY_GNOSIS_SAFE)

    def test_build_market_order_buy_0_1(self):
        builder = OrderBuilder(signer)
        order = run_async(builder.build_market_order(
            MarketOrderArgsV2(token_id=TOKEN_ID, amount=50, side=BUY, price=0.5),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.BUY)

    def test_build_market_order_sell_0_1(self):
        builder = OrderBuilder(signer)
        order = run_async(builder.build_market_order(
            MarketOrderArgsV2(token_id=TOKEN_ID, amount=100, side=SELL, price=0.5),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.SELL)

    def test_build_market_order_0_01(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = run_async(builder.build_market_order(
                MarketOrderArgsV2(token_id=TOKEN_ID, amount=21.04, side=side, price=0.56),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
            ))
            self._assert_signed_order_v2(order)

    def test_build_market_order_0_001(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = run_async(builder.build_market_order(
                MarketOrderArgsV2(token_id=TOKEN_ID, amount=21.04, side=side, price=0.056),
                CreateOrderOptions(tick_size="0.001", neg_risk=False),
            ))
            self._assert_signed_order_v2(order)

    def test_build_market_order_0_0001(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = run_async(builder.build_market_order(
                MarketOrderArgsV2(token_id=TOKEN_ID, amount=10, side=side, price=0.0056),
                CreateOrderOptions(tick_size="0.0001", neg_risk=False),
            ))
            self._assert_signed_order_v2(order)

    def test_build_market_order_neg_risk(self):
        builder = OrderBuilder(signer)
        for tick_size, price in [("0.1", 0.5), ("0.01", 0.56), ("0.001", 0.056), ("0.0001", 0.0056)]:
            for side in [BUY, SELL]:
                order = run_async(builder.build_market_order(
                    MarketOrderArgsV2(token_id=TOKEN_ID, amount=10, side=side, price=price),
                    CreateOrderOptions(tick_size=tick_size, neg_risk=True),
                ))
                self._assert_signed_order_v2(order)

    def test_build_market_order_with_builder_code(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "cd" * 32
        order = run_async(builder.build_market_order(
            MarketOrderArgsV2(
                token_id=TOKEN_ID, amount=50, side=BUY, price=0.5, builder_code=builder_code
            ),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)

    def test_build_order_v1_has_fee_rate_bps_nonce_taker(self):
        builder = OrderBuilder(signer)
        order = run_async(builder.build_order(
            OrderArgsV1(token_id=TOKEN_ID, price=0.5, size=21.04, side=BUY, nonce=7),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=1,
            fee_rate_bps=1000,
        ))
        self._assert_signed_order_v1(order)
        self.assertEqual(order.feeRateBps, "1000")
        self.assertEqual(order.nonce, "7")
        self.assertEqual(order.taker, ZERO_ADDRESS)

    def test_build_order_v2_has_no_fee_rate_bps_nonce(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "ab" * 32
        order = run_async(builder.build_order(
            OrderArgsV2(
                token_id=TOKEN_ID, price=0.5, size=21.04, side=BUY,
                builder_code=builder_code, expiration=1234567,
            ),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=2,
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)
        self.assertEqual(order.expiration, "1234567")

    def test_build_market_order_v1_has_fee_rate_bps_nonce_taker(self):
        builder = OrderBuilder(signer)
        order = run_async(builder.build_market_order(
            MarketOrderArgsV1(token_id=TOKEN_ID, amount=21.04, side=BUY, price=0.5, nonce=3),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=1,
            fee_rate_bps=500,
        ))
        self._assert_signed_order_v1(order)
        self.assertEqual(order.feeRateBps, "500")
        self.assertEqual(order.nonce, "3")
        self.assertEqual(order.taker, ZERO_ADDRESS)

    def test_build_market_order_v2_has_no_fee_rate_bps_nonce(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "ef" * 32
        order = run_async(builder.build_market_order(
            MarketOrderArgsV2(
                token_id=TOKEN_ID, amount=21.04, side=BUY, price=0.5, builder_code=builder_code
            ),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=2,
        ))
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)


class TestAdjustMarketBuyAmount(TestCase):

    def _total_cost(
        self,
        amount: float,
        price: float,
        fee_rate: float,
        fee_exponent: int,
        builder_rate: float = 0,
    ) -> float:
        """Total cost of spending `amount` USD at `price`, including all fees."""
        platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
        platform_fee = (amount / price) * platform_fee_rate
        return amount + platform_fee + amount * builder_rate

    # --- conditional: no adjustment ---

    def test_no_adjustment_when_balance_well_above_cost(self):
        # balance far exceeds total cost — amount must come back unchanged
        result = adjust_market_buy_amount(50, 200, 0.5, 0.25, 2)
        self.assertEqual(result, 50)

    def test_no_adjustment_when_balance_just_above_cost(self):
        amount, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        total = self._total_cost(amount, price, fee_rate, fee_exponent)
        result = adjust_market_buy_amount(amount, total + 1e-9, price, fee_rate, fee_exponent)
        self.assertEqual(result, amount)

    def test_no_adjustment_with_builder_fee_when_balance_above_cost(self):
        amount, price, fee_rate, fee_exponent, builder_rate = 50, 0.5, 0.25, 2, 0.01
        total = self._total_cost(amount, price, fee_rate, fee_exponent, builder_rate)
        result = adjust_market_buy_amount(amount, total + 1e-9, price, fee_rate, fee_exponent, builder_rate)
        self.assertEqual(result, amount)

    # --- conditional: adjustment triggers ---

    def test_no_adjustment_when_balance_exactly_covers_cost(self):
        # when balance == total_cost, the adjustment formula algebraically recovers the
        # original amount — user can afford exactly amount + fees, so nothing changes
        amount, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        total = self._total_cost(amount, price, fee_rate, fee_exponent)
        result = adjust_market_buy_amount(amount, total, price, fee_rate, fee_exponent)
        self.assertAlmostEqual(result, amount, places=10)

    def test_adjusts_when_balance_below_total_cost(self):
        # balance < total_cost — must adjust downward
        amount, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        result = adjust_market_buy_amount(amount, 48.0, price, fee_rate, fee_exponent)
        self.assertLess(result, amount)

    # --- invariant: adjusted + fees(adjusted) == budget ---

    def test_invariant_platform_fee_only(self):
        budget, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent)
        self.assertAlmostEqual(
            self._total_cost(result, price, fee_rate, fee_exponent), budget, places=10
        )

    def test_invariant_builder_fee_only(self):
        budget, price, builder_rate = 50, 0.5, 0.01
        result = adjust_market_buy_amount(budget, budget, price, 0, 0, builder_rate)
        self.assertAlmostEqual(
            self._total_cost(result, price, 0, 0, builder_rate), budget, places=10
        )

    def test_invariant_combined_fees(self):
        budget, price, fee_rate, fee_exponent, builder_rate = 50, 0.5, 0.25, 2, 0.01
        result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent, builder_rate)
        self.assertAlmostEqual(
            self._total_cost(result, price, fee_rate, fee_exponent, builder_rate), budget, places=10
        )

    def test_invariant_various_prices(self):
        budget, fee_rate, fee_exponent = 50, 0.25, 2
        for price in [0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95]:
            result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent)
            self.assertAlmostEqual(
                self._total_cost(result, price, fee_rate, fee_exponent),
                budget,
                places=10,
                msg=f"invariant failed at price={price}",
            )

    def test_invariant_various_budgets(self):
        price, fee_rate, fee_exponent = 0.5, 0.25, 2
        for budget in [1.0, 10.0, 50.0, 100.0, 1000.0]:
            result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent)
            self.assertAlmostEqual(
                self._total_cost(result, price, fee_rate, fee_exponent),
                budget,
                places=10,
                msg=f"invariant failed at budget={budget}",
            )

    # --- edge cases ---

    def test_zero_fees_no_adjustment_to_amount(self):
        # with no fees, total_cost == amount == balance → triggers, but result == budget
        result = adjust_market_buy_amount(50, 50, 0.5, 0, 0)
        self.assertAlmostEqual(result, 50, places=10)

    def test_adjusted_amount_less_than_original_when_fees_positive(self):
        for fee_rate in [0.1, 0.25, 0.5]:
            result = adjust_market_buy_amount(50, 50, 0.5, fee_rate, 2)
            self.assertLess(result, 50, msg=f"expected downward adjustment for fee_rate={fee_rate}")

    def test_higher_fee_produces_lower_adjusted_amount(self):
        r_low = adjust_market_buy_amount(50, 50, 0.5, 0.10, 2)
        r_high = adjust_market_buy_amount(50, 50, 0.5, 0.50, 2)
        self.assertGreater(r_low, r_high)
