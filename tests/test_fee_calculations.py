import unittest
from py_clob_client_v2.fees import adjust_buy_amount_for_fees, validate_fee_slippage


def calculate_platform_fee(
    amount_usd: float,
    price: float,
    fee_rate: float,
    fee_exponent: float,
    fee_slippage: float = 0,
) -> float:
    platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
    return (amount_usd / price) * platform_fee_rate * (1 + fee_slippage / 100)


def calculate_builder_fee(amount_usd: float, builder_taker_fee_rate: float) -> float:
    return amount_usd * builder_taker_fee_rate


def round_to(value: float, decimals: int = 12) -> float:
    return round(value, decimals)


class TestPlatformFee(unittest.TestCase):
    fee_rate = 0.25
    fee_exponent = 2
    contracts = 100

    def test_price_0_5(self):
        price = 0.5
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            1.5625,
        )

    def test_price_0_3(self):
        price = 0.3
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            1.1025,
        )

    def test_price_0_1(self):
        price = 0.1
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            0.2025,
        )

    def test_price_0_05(self):
        price = 0.05
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            0.05640625,
        )

    def test_price_0_01(self):
        price = 0.01
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            0.00245025,
        )

    def test_price_0_7_symmetric_with_0_3(self):
        price = 0.7
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            1.1025,
        )

    def test_price_0_9_symmetric_with_0_1(self):
        price = 0.9
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            0.2025,
        )

    def test_price_0_95_symmetric_with_0_05(self):
        price = 0.95
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            0.05640625,
        )

    def test_price_0_99_symmetric_with_0_01(self):
        price = 0.99
        self.assertEqual(
            round_to(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent)),
            0.00245025,
        )

    def test_price_0_5_c_125_5(self):
        price = 0.5
        c = 125.5
        self.assertEqual(
            round_to(calculate_platform_fee(c * price, price, self.fee_rate, self.fee_exponent)),
            1.9609375,
        )


class TestBuilderFee(unittest.TestCase):
    def test_1pct_100_tokens_at_50c(self):
        self.assertEqual(calculate_builder_fee(100 * 0.5, 0.01), 0.5)

    def test_5pct_200_tokens_at_75c(self):
        self.assertEqual(calculate_builder_fee(200 * 0.75, 0.05), 7.5)


class TestCombinedFee(unittest.TestCase):
    def test_matches_sum_of_separate_fees(self):
        price = 0.5
        contracts = 100
        fee_rate = 0.25
        fee_exponent = 2
        builder_taker_fee_rate = 0.01
        amount_usd = contracts * price

        platform_fee = calculate_platform_fee(amount_usd, price, fee_rate, fee_exponent)
        builder_fee = calculate_builder_fee(amount_usd, builder_taker_fee_rate)

        self.assertEqual(platform_fee, 1.5625)
        self.assertEqual(builder_fee, 0.5)
        self.assertEqual(platform_fee + builder_fee, 2.0625)


class TestAdjustBuyAmountForFees(unittest.TestCase):
    fee_rate = 0.25
    fee_exponent = 2

    def test_no_adjustment_zero_fees(self):
        amount = 50
        result = adjust_buy_amount_for_fees(amount, 0.5, amount, 0, 0, 0)
        self.assertEqual(result, amount)

    def test_no_adjustment_balance_above_total_cost(self):
        amount = 50
        price = 0.5
        platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        total_cost = amount + platform_fee
        balance = total_cost + 1
        result = adjust_buy_amount_for_fees(amount, price, balance, self.fee_rate, self.fee_exponent, 0)
        self.assertEqual(result, amount)

    def test_balance_exactly_equal_to_amount_plus_reserved_fee_returns_amount(self):
        # balance = amount + fee(amount) triggers the branch but result == amount
        amount = 50
        price = 0.5
        platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        total_cost = amount + platform_fee
        result = adjust_buy_amount_for_fees(amount, price, total_cost, self.fee_rate, self.fee_exponent, 0)
        self.assertEqual(platform_fee, 1.5625)
        self.assertEqual(total_cost, 51.5625)
        self.assertEqual(result, 50)

    def test_platform_fee_only_reserves_original_fee(self):
        amount = 50
        price = 0.5
        adjusted = adjust_buy_amount_for_fees(amount, price, amount, self.fee_rate, self.fee_exponent, 0)
        original_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        adjusted_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent)
        self.assertEqual(original_fee, 1.5625)
        self.assertEqual(adjusted, 48.4375)
        self.assertEqual(adjusted_fee, 1.513671875)
        self.assertEqual(adjusted + adjusted_fee, 49.951171875)

    def test_builder_fee_only_reserves_original_fee(self):
        amount = 50
        price = 0.5
        builder_taker_fee_rate = 0.01
        adjusted = adjust_buy_amount_for_fees(amount, price, amount, 0, 0, builder_taker_fee_rate)
        original_fee = calculate_builder_fee(amount, builder_taker_fee_rate)
        adjusted_fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertEqual(original_fee, 0.5)
        self.assertEqual(adjusted, 49.5)
        self.assertEqual(adjusted_fee, 0.495)
        self.assertEqual(adjusted + adjusted_fee, 49.995)

    def test_platform_and_builder_fee_reserves_original_fees(self):
        amount = 50
        price = 0.5
        builder_taker_fee_rate = 0.01
        adjusted = adjust_buy_amount_for_fees(amount, price, amount, self.fee_rate, self.fee_exponent, builder_taker_fee_rate)
        original_platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        original_builder_fee = calculate_builder_fee(amount, builder_taker_fee_rate)
        adjusted_platform_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent)
        adjusted_builder_fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertEqual(original_platform_fee, 1.5625)
        self.assertEqual(original_builder_fee, 0.5)
        self.assertEqual(adjusted, 47.9375)
        self.assertEqual(adjusted_platform_fee, 1.498046875)
        self.assertEqual(adjusted_builder_fee, 0.479375)
        self.assertEqual(adjusted + adjusted_platform_fee + adjusted_builder_fee, 49.914921875)

    def test_adjusted_less_than_original(self):
        amount = 50
        adjusted = adjust_buy_amount_for_fees(amount, 0.5, amount, self.fee_rate, self.fee_exponent, 0)
        self.assertEqual(adjusted, 48.4375)

    def test_price_0_3_platform_and_builder_reserves_original_fees(self):
        amount = 30
        price = 0.3
        builder_taker_fee_rate = 0.02
        adjusted = adjust_buy_amount_for_fees(amount, price, amount, self.fee_rate, self.fee_exponent, builder_taker_fee_rate)
        original_platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        original_builder_fee = calculate_builder_fee(amount, builder_taker_fee_rate)
        adjusted_platform_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent)
        adjusted_builder_fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertEqual(round_to(original_platform_fee), 1.1025)
        self.assertEqual(original_builder_fee, 0.6)
        self.assertEqual(adjusted, 28.2975)
        self.assertEqual(round_to(adjusted_platform_fee), 1.039933125)
        self.assertEqual(adjusted_builder_fee, 0.56595)
        self.assertEqual(round_to(adjusted + adjusted_platform_fee + adjusted_builder_fee), 29.903383125)

    def test_uses_balance_as_fee_base_when_amount_exceeds_balance(self):
        # amount > balance: feeBaseAmount = min(amount, balance) = balance
        amount = 100
        price = 0.3
        user_usdc_balance = 1
        rate = 0.072
        exponent = 1
        adjusted = adjust_buy_amount_for_fees(amount, price, user_usdc_balance, rate, exponent, 0)
        reserved_fee = calculate_platform_fee(user_usdc_balance, price, rate, exponent)
        adjusted_fee = calculate_platform_fee(adjusted, price, rate, exponent)
        self.assertEqual(round_to(reserved_fee), 0.0504)
        self.assertEqual(adjusted, 0.9496)
        self.assertEqual(round_to(adjusted_fee), 0.04785984)
        self.assertEqual(round_to(adjusted + adjusted_fee), 0.99745984)


class TestFeeSlippage(unittest.TestCase):
    fee_rate = 0.25
    fee_exponent = 2

    def test_pads_only_platform_fee_by_percentage(self):
        amount = 50
        price = 0.5
        builder_taker_fee_rate = 0.01
        fee_slippage = 20
        adjusted = adjust_buy_amount_for_fees(amount, price, amount, self.fee_rate, self.fee_exponent, builder_taker_fee_rate, fee_slippage)
        original_platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent, fee_slippage)
        original_builder_fee = calculate_builder_fee(amount, builder_taker_fee_rate)
        adjusted_platform_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent, fee_slippage)
        adjusted_builder_fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertEqual(original_platform_fee, 1.875)
        self.assertEqual(original_builder_fee, 0.5)
        self.assertEqual(adjusted, 47.625)
        self.assertEqual(adjusted_platform_fee, 1.7859375)
        self.assertEqual(adjusted_builder_fee, 0.47625)
        self.assertEqual(adjusted + adjusted_platform_fee + adjusted_builder_fee, 49.8871875)

    def test_adjusts_when_balance_covers_unpadded_but_not_padded_fees(self):
        amount = 50
        price = 0.5
        platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        padded_platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent, 20)
        balance = amount + platform_fee + (padded_platform_fee - platform_fee) / 2

        adjusted = adjust_buy_amount_for_fees(amount, price, balance, self.fee_rate, self.fee_exponent, 0, 20)

        self.assertEqual(platform_fee, 1.5625)
        self.assertEqual(padded_platform_fee, 1.875)
        self.assertEqual(balance, 51.71875)
        self.assertEqual(adjusted, 49.84375)

    def test_accepts_float_percentages_between_1_and_100(self):
        amount = 50
        price = 0.5
        adjusted = adjust_buy_amount_for_fees(amount, price, amount, self.fee_rate, self.fee_exponent, 0, 1.5)
        original_platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent, 1.5)
        adjusted_platform_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent, 1.5)

        self.assertEqual(round_to(original_platform_fee), 1.5859375)
        self.assertEqual(adjusted, 48.4140625)
        self.assertEqual(round_to(adjusted_platform_fee), 1.535633544922)
        self.assertEqual(round_to(adjusted + adjusted_platform_fee), 49.949696044922)

    def test_rejects_fractional_below_1_and_values_over_100(self):
        with self.assertRaises(ValueError) as ctx:
            adjust_buy_amount_for_fees(50, 0.5, 50, self.fee_rate, self.fee_exponent, 0, 0.5)
        self.assertIn("fee_slippage must be 0 or a percentage between 1 and 100", str(ctx.exception))

        with self.assertRaises(ValueError) as ctx:
            adjust_buy_amount_for_fees(50, 0.5, 50, self.fee_rate, self.fee_exponent, 0, 101)
        self.assertIn("fee_slippage must be 0 or a percentage between 1 and 100", str(ctx.exception))


class TestValidateFeeSlippage(unittest.TestCase):
    def test_accepts_zero(self):
        validate_fee_slippage(0)  # no exception

    def test_accepts_100(self):
        validate_fee_slippage(100)  # no exception

    def test_accepts_float_between_1_and_100(self):
        validate_fee_slippage(12.5)  # no exception
        validate_fee_slippage(1.0)
        validate_fee_slippage(99.9)

    def test_rejects_below_1_but_above_0(self):
        with self.assertRaises(ValueError):
            validate_fee_slippage(0.5)

    def test_rejects_above_100(self):
        with self.assertRaises(ValueError):
            validate_fee_slippage(101)

    def test_rejects_negative(self):
        with self.assertRaises(ValueError):
            validate_fee_slippage(-1)

    def test_rejects_nan(self):
        with self.assertRaises(ValueError):
            validate_fee_slippage(float("nan"))

    def test_rejects_inf(self):
        with self.assertRaises(ValueError):
            validate_fee_slippage(float("inf"))


class TestProductionFeeRatesV2(unittest.TestCase):
    amount = 100

    def test_sports_v2_rate_0_03_exp_1_price_0_5(self):
        self.assertEqual(calculate_platform_fee(self.amount, 0.5, 0.03, 1), 1.5)

    def test_sports_v2_rate_0_03_exp_1_price_0_3(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.3, 0.03, 1)), 2.1)

    def test_sports_v2_rate_0_03_exp_1_price_0_7(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.7, 0.03, 1)), 0.9)

    def test_politics_rate_0_04_exp_1_price_0_5(self):
        self.assertEqual(calculate_platform_fee(self.amount, 0.5, 0.04, 1), 2.0)

    def test_politics_rate_0_04_exp_1_price_0_3(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.3, 0.04, 1)), 2.8)

    def test_politics_rate_0_04_exp_1_price_0_7(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.7, 0.04, 1)), 1.2)

    def test_culture_rate_0_05_exp_1_price_0_5(self):
        self.assertEqual(calculate_platform_fee(self.amount, 0.5, 0.05, 1), 2.5)

    def test_culture_rate_0_05_exp_1_price_0_3(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.3, 0.05, 1)), 3.5)

    def test_culture_rate_0_05_exp_1_price_0_7(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.7, 0.05, 1)), 1.5)

    def test_crypto_rate_0_072_exp_1_price_0_5(self):
        self.assertEqual(round_to(calculate_platform_fee(self.amount, 0.5, 0.072, 1)), 3.6)

    def test_crypto_rate_0_072_exp_1_price_0_3(self):
        self.assertEqual(calculate_platform_fee(self.amount, 0.3, 0.072, 1), 5.04)

    def test_crypto_rate_0_072_exp_1_price_0_7(self):
        self.assertEqual(calculate_platform_fee(self.amount, 0.7, 0.072, 1), 2.16)

    def test_balance_equals_amount_reserves_original_fee(self):
        cases = [
            ("sports_fees_v2", 0.03, 1, {
                0.3: {"original_fee": 2.1, "adjusted": 97.9, "adjusted_fee": 2.0559, "final": 99.9559},
                0.5: {"original_fee": 1.5, "adjusted": 98.5, "adjusted_fee": 1.4775, "final": 99.9775},
                0.7: {"original_fee": 0.9, "adjusted": 99.1, "adjusted_fee": 0.8919, "final": 99.9919},
            }),
            ("politics_fees", 0.04, 1, {
                0.3: {"original_fee": 2.8, "adjusted": 97.2, "adjusted_fee": 2.7216, "final": 99.9216},
                0.5: {"original_fee": 2.0, "adjusted": 98.0, "adjusted_fee": 1.96, "final": 99.96},
                0.7: {"original_fee": 1.2, "adjusted": 98.8, "adjusted_fee": 1.1856, "final": 99.9856},
            }),
            ("culture_fees", 0.05, 1, {
                0.3: {"original_fee": 3.5, "adjusted": 96.5, "adjusted_fee": 3.3775, "final": 99.8775},
                0.5: {"original_fee": 2.5, "adjusted": 97.5, "adjusted_fee": 2.4375, "final": 99.9375},
                0.7: {"original_fee": 1.5, "adjusted": 98.5, "adjusted_fee": 1.4775, "final": 99.9775},
            }),
            ("crypto_fees_v2", 0.072, 1, {
                0.3: {"original_fee": 5.04, "adjusted": 94.96, "adjusted_fee": 4.785984, "final": 99.745984},
                0.5: {"original_fee": 3.6, "adjusted": 96.4, "adjusted_fee": 3.4704, "final": 99.8704},
                0.7: {"original_fee": 2.16, "adjusted": 97.84, "adjusted_fee": 2.113344, "final": 99.953344},
            }),
        ]
        amount = 100
        for name, rate, exponent, expected_by_price in cases:
            for price in [0.3, 0.5, 0.7]:
                exp = expected_by_price[price]
                with self.subTest(name=name, price=price):
                    adjusted = adjust_buy_amount_for_fees(amount, price, amount, rate, exponent, 0)
                    original_fee = calculate_platform_fee(amount, price, rate, exponent)
                    adjusted_fee = calculate_platform_fee(adjusted, price, rate, exponent)
                    self.assertEqual(round_to(original_fee), exp["original_fee"])
                    self.assertEqual(round_to(adjusted), exp["adjusted"])
                    self.assertEqual(round_to(adjusted_fee), exp["adjusted_fee"])
                    self.assertEqual(round_to(adjusted + adjusted_fee), exp["final"])
