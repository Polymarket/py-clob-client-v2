from decimal import Decimal, ROUND_DOWN
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
from py_clob_client_v2.exceptions import PolyException
from py_clob_client_v2.order_builder.builder import (
    MIN_MARKET_BUY_AMOUNT,
    OrderBuilder,
    ROUNDING_CONFIG,
)
from py_clob_client_v2.order_builder.constants import BUY, SELL
from py_clob_client_v2.order_builder.helpers import decimal_places, round_down, round_normal
from py_clob_client_v2.order_utils.exchange_order_builder_v2 import ORDER_TYPE_STRING
from py_clob_client_v2.order_utils.model import Side, SignatureTypeV2
from py_clob_client_v2.signer import Signer
from py_clob_client_v2.utilities import adjust_market_buy_amount

# publicly known private key
private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
chain_id = AMOY
signer = Signer(private_key=private_key, chain_id=chain_id)

TOKEN_ID = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
DEPOSIT_WALLET = "0x1111111111111111111111111111111111111111"

TICK_SIZES = ["0.1", "0.01", "0.005", "0.0025", "0.001", "0.0001"]


def _exact_buy_amounts_by_search(amount: Decimal, price: Decimal, round_config):
    """Brute-force oracle for a market BUY: the largest (collateral, shares) pair
    within amount whose ratio is exactly price, both in whole amount-precision
    units. Walks the share count down one unit at a time from the most the budget
    could buy."""
    unit = 10 ** (6 - round_config.amount)
    budget = int(
        amount.quantize(Decimal(1).scaleb(-round_config.amount), rounding=ROUND_DOWN)
        * 10**6
    )
    numerator, denominator = price.as_integer_ratio()
    shares = budget * denominator // numerator // unit * unit
    while shares > 0:
        collateral, remainder = divmod(shares * numerator, denominator)
        if remainder == 0 and collateral % unit == 0 and collateral <= budget:
            return collateral, shares
        shares -= unit
    return 0, 0


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

    # Market BUY amounts. The exchange reads a BUY's price as maker / taker and
    # requires that ratio to be exactly the on-tick price, with collateral and
    # shares both in whole units of the market's amount precision.

    def test_get_market_order_amounts_buy_spends_the_most_an_exact_price_allows(self):
        builder = OrderBuilder(signer)
        amounts = [
            "0.5", "0.99", "0.9999", "1", "1.01", "3.33", "10", "21.04",
            "25.5", "48.125", "99.99", "250", "1000",
        ]
        for tick_size in TICK_SIZES:
            round_config = ROUNDING_CONFIG[tick_size]
            tick = Decimal(tick_size)
            ticks = int(1 / tick)
            prices = [tick * i for i in range(1, ticks, max(1, ticks // 97))]
            for price in prices:
                for amount in amounts:
                    with self.subTest(tick_size=tick_size, price=price, amount=amount):
                        expected = _exact_buy_amounts_by_search(
                            Decimal(amount), price, round_config
                        )
                        if expected[0] < MIN_MARKET_BUY_AMOUNT:
                            with self.assertRaisesRegex(
                                PolyException, "cannot be spent exactly"
                            ):
                                builder.get_market_order_amounts(
                                    BUY, float(amount), float(price), round_config
                                )
                            continue
                        side, maker, taker = builder.get_market_order_amounts(
                            BUY, float(amount), float(price), round_config
                        )
                        self.assertEqual(side, Side.BUY)
                        self.assertEqual((maker, taker), expected)
                        self._assert_exact_buy_amounts(
                            maker, taker, Decimal(amount), price, tick_size
                        )

    def test_get_market_order_amounts_buy_of_one_usdc_at_every_tick(self):
        # Every on-tick price at every tick size: 1 USDC always lands at or above
        # the 0.99 USDC minimum.
        builder = OrderBuilder(signer)
        for tick_size in TICK_SIZES:
            tick = Decimal(tick_size)
            for i in range(1, int(1 / tick)):
                price = tick * i
                side, maker, taker = builder.get_market_order_amounts(
                    BUY, 1, float(price), ROUNDING_CONFIG[tick_size]
                )
                self.assertGreaterEqual(
                    maker, MIN_MARKET_BUY_AMOUNT, (tick_size, price)
                )
                self._assert_exact_buy_amounts(
                    maker, taker, Decimal(1), price, tick_size
                )

    def test_get_market_order_amounts_buy_of_one_usdc(self):
        builder = OrderBuilder(signer)
        cases = [
            # (price, tick_size, (maker, taker))
            ("0.7", "0.1", (994_000, 1_420_000)),
            ("0.65", "0.01", (999_700, 1_538_000)),
            ("0.07", "0.01", (999_600, 14_280_000)),
            ("0.335", "0.005", (999_640, 2_984_000)),
            ("0.4325", "0.0025", (999_940, 2_312_000)),
            ("0.962", "0.001", (995_670, 1_035_000)),
            ("0.9999", "0.0001", (999_900, 1_000_000)),
        ]
        for price, tick_size, expected in cases:
            with self.subTest(price=price, tick_size=tick_size):
                _, maker, taker = builder.get_market_order_amounts(
                    BUY, 1, float(price), ROUNDING_CONFIG[tick_size]
                )
                self.assertEqual((maker, taker), expected)

    def test_get_market_order_amounts_buy_steps_by_the_smallest_exact_share_count(self):
        # At 0.65 on a 0.01 tick, 0.0013 USDC buys exactly 0.002 shares; 10 USDC
        # holds 7692 such steps.
        builder = OrderBuilder(signer)
        side, maker, taker = builder.get_market_order_amounts(
            BUY, 10, 0.65, ROUNDING_CONFIG["0.01"]
        )
        self.assertEqual(side, Side.BUY)
        self.assertEqual((maker, taker), (9_999_600, 15_384_000))

    def test_get_market_order_amounts_buy_accepts_side_enum(self):
        builder = OrderBuilder(signer)
        side, maker, taker = builder.get_market_order_amounts(
            Side.BUY, 10, 0.65, ROUNDING_CONFIG["0.01"]
        )
        self.assertEqual((side, maker, taker), (Side.BUY, 9_999_600, 15_384_000))

    def test_get_market_order_amounts_buy_exact_division_is_unchanged(self):
        builder = OrderBuilder(signer)
        _, maker, taker = builder.get_market_order_amounts(
            BUY, 1, 0.1, ROUNDING_CONFIG["0.01"]
        )
        self.assertEqual((maker, taker), (1_000_000, 10_000_000))

    def test_get_market_order_amounts_buy_uses_the_tick_rounded_price(self):
        # 0.29 * 100 is 28.999... in binary floating point; the price must still
        # be 0.29, and a price between ticks rounds down to the tick below.
        builder = OrderBuilder(signer)
        _, maker, taker = builder.get_market_order_amounts(
            BUY, 10, 0.29, ROUNDING_CONFIG["0.01"]
        )
        self.assertEqual(Decimal(maker) / Decimal(taker), Decimal("0.29"))
        _, maker, taker = builder.get_market_order_amounts(
            BUY, 10, 0.659, ROUNDING_CONFIG["0.01"]
        )
        self.assertEqual((maker, taker), (9_999_600, 15_384_000))

    def test_get_market_order_amounts_buy_at_exactly_the_minimum_is_accepted(self):
        builder = OrderBuilder(signer)
        _, maker, taker = builder.get_market_order_amounts(
            BUY, 0.99, 0.5, ROUNDING_CONFIG["0.01"]
        )
        self.assertEqual((maker, taker), (990_000, 1_980_000))

    def test_get_market_order_amounts_buy_stepping_below_minimum_is_rejected(self):
        # 0.99 USDC at 0.65 holds 761 steps of 0.0013, which is 0.9893 and under
        # the 0.99 USDC minimum; 762 steps is 0.9906.
        builder = OrderBuilder(signer)
        with self.assertRaisesRegex(
            PolyException, r"steps of 0\.0013; use at least 0\.9906"
        ):
            builder.get_market_order_amounts(BUY, 0.99, 0.65, ROUNDING_CONFIG["0.01"])

    def test_get_market_order_amounts_buy_just_below_the_minimum_is_rejected(self):
        # 0.9899 USDC at 0.5 is one 0.0001 step under the 0.99 USDC minimum.
        builder = OrderBuilder(signer)
        with self.assertRaisesRegex(
            PolyException, r"steps of 0\.0001; use at least 0\.99\."
        ):
            builder.get_market_order_amounts(BUY, 0.9899, 0.5, ROUNDING_CONFIG["0.01"])

    def test_get_market_order_amounts_buy_small_amounts_are_rejected(self):
        builder = OrderBuilder(signer)
        for amount in [0.001, 0.5, 0]:
            with self.subTest(amount=amount):
                with self.assertRaisesRegex(
                    PolyException,
                    r"BUY amount .* cannot be spent exactly at price 0\.65\. "
                    r"At this price the amount is used in steps of 0\.0013; "
                    r"use at least 0\.9906\.",
                ):
                    builder.get_market_order_amounts(
                        BUY, amount, 0.65, ROUNDING_CONFIG["0.01"]
                    )

    def test_build_market_order_buy_rejects_small_amount_before_signing(self):
        builder = OrderBuilder(signer)
        for version in (1, 2):
            with self.subTest(version=version):
                with self.assertRaisesRegex(PolyException, "cannot be spent exactly"):
                    builder.build_market_order(
                        MarketOrderArgsV2(
                            token_id=TOKEN_ID, amount=0.5, side=BUY, price=0.65
                        ),
                        CreateOrderOptions(tick_size="0.01", neg_risk=False),
                        version=version,
                    )

    def test_build_market_order_buy_signs_exactly_the_order_price(self):
        builder = OrderBuilder(signer)
        for version in (1, 2):
            with self.subTest(version=version):
                order = builder.build_market_order(
                    MarketOrderArgsV2(
                        token_id=TOKEN_ID, amount=10, side=BUY, price=0.65
                    ),
                    CreateOrderOptions(tick_size="0.01", neg_risk=False),
                    version=version,
                )
                self.assertEqual(order.makerAmount, "9999600")
                self.assertEqual(order.takerAmount, "15384000")

    def _assert_exact_buy_amounts(self, maker, taker, amount, price, tick_size):
        unit = 10 ** (6 - ROUNDING_CONFIG[tick_size].amount)
        self.assertEqual(Decimal(maker) / Decimal(taker), price)
        self.assertLessEqual(maker, amount * 10**6)
        self.assertEqual(maker % unit, 0)
        self.assertEqual(taker % unit, 0)

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

    def _assert_poly_1271_order(self, order):
        self._assert_signed_order_v2(order)
        self.assertEqual(order.maker, DEPOSIT_WALLET)
        self.assertEqual(order.signer, DEPOSIT_WALLET)
        self.assertEqual(order.signatureType, SignatureTypeV2.POLY_1271)
        self.assertTrue(order.signature.startswith("0x"))
        expected_signature_len = 2 + 130 + 64 + 64 + (len(ORDER_TYPE_STRING) * 2) + 4
        self.assertEqual(len(order.signature), expected_signature_len)

    def test_build_order_buy_0_1(self):
        builder = OrderBuilder(signer)
        order = builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=100, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.makerAmount, "50000000")
        self.assertEqual(order.takerAmount, "100000000")

    def test_build_order_sell_0_1(self):
        builder = OrderBuilder(signer)
        order = builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=100, side=SELL),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.SELL)
        self.assertEqual(order.makerAmount, "100000000")
        self.assertEqual(order.takerAmount, "50000000")

    def test_build_order_0_01(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.56, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
            )
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
            order = builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.056, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.001", neg_risk=False),
            )
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
            order = builder.build_order(
                OrderArgsV2(token_id=TOKEN_ID, price=0.0056, size=21.04, side=side),
                CreateOrderOptions(tick_size="0.0001", neg_risk=False),
            )
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
        order = builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.82, size=20.0, side=BUY),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.makerAmount, "16400000")
        self.assertEqual(order.takerAmount, "20000000")

    def test_build_order_neg_risk(self):
        builder = OrderBuilder(signer)
        for tick_size, price in [("0.1", 0.5), ("0.01", 0.56), ("0.001", 0.056), ("0.0001", 0.0056)]:
            for side in [BUY, SELL]:
                order = builder.build_order(
                    OrderArgsV2(token_id=TOKEN_ID, price=price, size=10, side=side),
                    CreateOrderOptions(tick_size=tick_size, neg_risk=True),
                )
                self._assert_signed_order_v2(order)

    def test_build_order_with_builder_code(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "ab" * 32
        order = builder.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=100, side=BUY, builder_code=builder_code),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)

    def test_build_order_poly_proxy_signature_type(self):
        b = OrderBuilder(signer, signature_type=SignatureTypeV2.POLY_PROXY)
        order = b.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=10, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.signatureType, SignatureTypeV2.POLY_PROXY)

    def test_build_order_gnosis_safe_signature_type(self):
        b = OrderBuilder(signer, signature_type=SignatureTypeV2.POLY_GNOSIS_SAFE)
        order = b.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=10, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.signatureType, SignatureTypeV2.POLY_GNOSIS_SAFE)

    def test_build_order_poly_1271_signature_type(self):
        b = OrderBuilder(
            signer,
            signature_type=SignatureTypeV2.POLY_1271,
            funder=DEPOSIT_WALLET,
        )
        order = b.build_order(
            OrderArgsV2(token_id=TOKEN_ID, price=0.5, size=10, side=BUY),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_poly_1271_order(order)

    def test_build_market_order_buy_0_1(self):
        builder = OrderBuilder(signer)
        order = builder.build_market_order(
            MarketOrderArgsV2(token_id=TOKEN_ID, amount=50, side=BUY, price=0.5),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.BUY)

    def test_build_market_order_sell_0_1(self):
        builder = OrderBuilder(signer)
        order = builder.build_market_order(
            MarketOrderArgsV2(token_id=TOKEN_ID, amount=100, side=SELL, price=0.5),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.side, Side.SELL)

    def test_build_market_order_0_01(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = builder.build_market_order(
                MarketOrderArgsV2(token_id=TOKEN_ID, amount=21.04, side=side, price=0.56),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
            )
            self._assert_signed_order_v2(order)

    def test_build_market_order_0_001(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = builder.build_market_order(
                MarketOrderArgsV2(token_id=TOKEN_ID, amount=21.04, side=side, price=0.056),
                CreateOrderOptions(tick_size="0.001", neg_risk=False),
            )
            self._assert_signed_order_v2(order)

    def test_build_market_order_0_0001(self):
        builder = OrderBuilder(signer)
        for side in [BUY, SELL]:
            order = builder.build_market_order(
                MarketOrderArgsV2(token_id=TOKEN_ID, amount=10, side=side, price=0.0056),
                CreateOrderOptions(tick_size="0.0001", neg_risk=False),
            )
            self._assert_signed_order_v2(order)

    def test_build_market_order_neg_risk(self):
        builder = OrderBuilder(signer)
        for tick_size, price in [("0.1", 0.5), ("0.01", 0.56), ("0.001", 0.056), ("0.0001", 0.0056)]:
            for side in [BUY, SELL]:
                order = builder.build_market_order(
                    MarketOrderArgsV2(token_id=TOKEN_ID, amount=10, side=side, price=price),
                    CreateOrderOptions(tick_size=tick_size, neg_risk=True),
                )
                self._assert_signed_order_v2(order)

    def test_build_market_order_with_builder_code(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "cd" * 32
        order = builder.build_market_order(
            MarketOrderArgsV2(
                token_id=TOKEN_ID, amount=50, side=BUY, price=0.5, builder_code=builder_code
            ),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)

    def test_build_market_order_poly_1271_signature_type(self):
        b = OrderBuilder(
            signer,
            signature_type=SignatureTypeV2.POLY_1271,
            funder=DEPOSIT_WALLET,
        )
        order = b.build_market_order(
            MarketOrderArgsV2(token_id=TOKEN_ID, amount=50, side=BUY, price=0.5),
            CreateOrderOptions(tick_size="0.1", neg_risk=False),
        )
        self._assert_poly_1271_order(order)

    def test_build_order_v1_has_fee_rate_bps_nonce_taker(self):
        builder = OrderBuilder(signer)
        order = builder.build_order(
            OrderArgsV1(token_id=TOKEN_ID, price=0.5, size=21.04, side=BUY, nonce=7),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=1,
            fee_rate_bps=1000,
        )
        self._assert_signed_order_v1(order)
        self.assertEqual(order.feeRateBps, "1000")
        self.assertEqual(order.nonce, "7")
        self.assertEqual(order.taker, ZERO_ADDRESS)

    def test_build_order_v2_has_no_fee_rate_bps_nonce(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "ab" * 32
        order = builder.build_order(
            OrderArgsV2(
                token_id=TOKEN_ID, price=0.5, size=21.04, side=BUY,
                builder_code=builder_code, expiration=1234567,
            ),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=2,
        )
        self._assert_signed_order_v2(order)
        self.assertEqual(order.builder, builder_code)
        self.assertEqual(order.expiration, "1234567")

    def test_build_market_order_v1_has_fee_rate_bps_nonce_taker(self):
        builder = OrderBuilder(signer)
        order = builder.build_market_order(
            MarketOrderArgsV1(token_id=TOKEN_ID, amount=21.04, side=BUY, price=0.5, nonce=3),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=1,
            fee_rate_bps=500,
        )
        self._assert_signed_order_v1(order)
        self.assertEqual(order.feeRateBps, "500")
        self.assertEqual(order.nonce, "3")
        self.assertEqual(order.taker, ZERO_ADDRESS)

    def test_build_order_v1_rejects_poly_1271(self):
        builder = OrderBuilder(
            signer,
            signature_type=SignatureTypeV2.POLY_1271,
            funder=DEPOSIT_WALLET,
        )
        with self.assertRaises(ValueError):
            builder.build_order(
                OrderArgsV1(token_id=TOKEN_ID, price=0.5, size=21.04, side=BUY),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
                version=1,
            )

    def test_build_market_order_v1_rejects_poly_1271(self):
        builder = OrderBuilder(
            signer,
            signature_type=SignatureTypeV2.POLY_1271,
            funder=DEPOSIT_WALLET,
        )
        with self.assertRaises(ValueError):
            builder.build_market_order(
                MarketOrderArgsV1(
                    token_id=TOKEN_ID,
                    amount=21.04,
                    side=BUY,
                    price=0.5,
                ),
                CreateOrderOptions(tick_size="0.01", neg_risk=False),
                version=1,
            )

    def test_build_market_order_v2_has_no_fee_rate_bps_nonce(self):
        builder = OrderBuilder(signer)
        builder_code = "0x" + "ef" * 32
        order = builder.build_market_order(
            MarketOrderArgsV2(
                token_id=TOKEN_ID, amount=21.04, side=BUY, price=0.5, builder_code=builder_code
            ),
            CreateOrderOptions(tick_size="0.01", neg_risk=False),
            version=2,
        )
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

    def test_balance_equals_total_cost_returns_amount(self):
        # balance = amount + fee(amount): enters branch but result == amount
        amount, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        total = self._total_cost(amount, price, fee_rate, fee_exponent)
        result = adjust_market_buy_amount(amount, total, price, fee_rate, fee_exponent)
        self.assertAlmostEqual(result, amount, places=10)

    def test_adjusts_when_balance_below_total_cost(self):
        # balance < total_cost — must adjust downward
        amount, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        result = adjust_market_buy_amount(amount, 48.0, price, fee_rate, fee_exponent)
        self.assertLess(result, amount)

    # --- invariant: adjusted = balance - reserved_fee ---

    def test_platform_fee_only_reserves_original_fee(self):
        # reserved_fee = fee(amount), adjusted = balance - reserved_fee
        budget, price, fee_rate, fee_exponent = 50, 0.5, 0.25, 2
        result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent)
        reserved_fee = self._total_cost(budget, price, fee_rate, fee_exponent) - budget
        self.assertAlmostEqual(result, budget - reserved_fee, places=10)

    def test_builder_fee_only_reserves_original_fee(self):
        budget, price, builder_rate = 50, 0.5, 0.01
        result = adjust_market_buy_amount(budget, budget, price, 0, 0, builder_rate)
        reserved_fee = self._total_cost(budget, price, 0, 0, builder_rate) - budget
        self.assertAlmostEqual(result, budget - reserved_fee, places=10)

    def test_combined_fees_reserves_original_fee(self):
        budget, price, fee_rate, fee_exponent, builder_rate = 50, 0.5, 0.25, 2, 0.01
        result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent, builder_rate)
        reserved_fee = self._total_cost(budget, price, fee_rate, fee_exponent, builder_rate) - budget
        self.assertAlmostEqual(result, budget - reserved_fee, places=10)

    def test_reserves_original_fee_at_various_prices(self):
        budget, fee_rate, fee_exponent = 50, 0.25, 2
        for price in [0.05, 0.1, 0.3, 0.5, 0.7, 0.9, 0.95]:
            result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent)
            reserved_fee = self._total_cost(budget, price, fee_rate, fee_exponent) - budget
            self.assertAlmostEqual(
                result,
                budget - reserved_fee,
                places=10,
                msg=f"fee reservation failed at price={price}",
            )

    def test_reserves_original_fee_at_various_budgets(self):
        price, fee_rate, fee_exponent = 0.5, 0.25, 2
        for budget in [1.0, 10.0, 50.0, 100.0, 1000.0]:
            result = adjust_market_buy_amount(budget, budget, price, fee_rate, fee_exponent)
            reserved_fee = self._total_cost(budget, price, fee_rate, fee_exponent) - budget
            self.assertAlmostEqual(
                result,
                budget - reserved_fee,
                places=10,
                msg=f"fee reservation failed at budget={budget}",
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
