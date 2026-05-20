from unittest import TestCase

from py_clob_client_v2.order_builder.builder import OrderBuilder, ROUNDING_CONFIG
from py_clob_client_v2.order_builder.constants import BUY, SELL
from py_clob_client_v2.order_utils.model import Side


class TestDecimalOrderAmounts(TestCase):
    def setUp(self):
        self.builder = OrderBuilder(signer=None, funder="0x" + "0" * 40)

    def test_limit_buy_preserves_cent_boundary_sizes(self):
        cases = [
            (16.90, 0.30, 5_070_000, 16_900_000),
            (33.30, 0.30, 9_990_000, 33_300_000),
            (66.60, 0.15, 9_990_000, 66_600_000),
        ]

        for size, price, expected_maker, expected_taker in cases:
            with self.subTest(size=size, price=price):
                side, maker, taker = self.builder.get_order_amounts(
                    BUY, size, price, ROUNDING_CONFIG["0.01"]
                )

                self.assertEqual(side, Side.BUY)
                self.assertEqual(maker, expected_maker)
                self.assertEqual(taker, expected_taker)

    def test_limit_sell_preserves_cent_boundary_sizes(self):
        cases = [
            (16.90, 0.30, 16_900_000, 5_070_000),
            (33.30, 0.30, 33_300_000, 9_990_000),
            (66.60, 0.15, 66_600_000, 9_990_000),
        ]

        for size, price, expected_maker, expected_taker in cases:
            with self.subTest(size=size, price=price):
                side, maker, taker = self.builder.get_order_amounts(
                    SELL, size, price, ROUNDING_CONFIG["0.01"]
                )

                self.assertEqual(side, Side.SELL)
                self.assertEqual(maker, expected_maker)
                self.assertEqual(taker, expected_taker)
