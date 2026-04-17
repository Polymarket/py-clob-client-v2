import unittest
from py_clob_client_v2.utilities import adjust_market_buy_amount


def calculate_platform_fee(amount_usd: float, price: float, fee_rate: float, fee_exponent: float) -> float:
    platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
    return (amount_usd / price) * platform_fee_rate


def calculate_builder_fee(amount_usd: float, builder_taker_fee_rate: float) -> float:
    return amount_usd * builder_taker_fee_rate


class TestPlatformFee(unittest.TestCase):
    fee_rate = 0.25
    fee_exponent = 2
    contracts = 100

    def test_price_0_5(self):
        price = 0.5
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 1.5625, delta=1e-6)

    def test_price_0_3(self):
        price = 0.3
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 1.1025, delta=1e-6)

    def test_price_0_1(self):
        price = 0.1
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 0.2025, delta=1e-6)

    def test_price_0_05(self):
        price = 0.05
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 0.05640625, delta=1e-6)

    def test_price_0_01(self):
        price = 0.01
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 0.00245025, delta=1e-6)

    def test_price_0_7_symmetric_with_0_3(self):
        price = 0.7
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 1.1025, delta=1e-6)

    def test_price_0_9_symmetric_with_0_1(self):
        price = 0.9
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 0.2025, delta=1e-6)

    def test_price_0_95_symmetric_with_0_05(self):
        price = 0.95
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 0.05640625, delta=1e-6)

    def test_price_0_99_symmetric_with_0_01(self):
        price = 0.99
        self.assertAlmostEqual(calculate_platform_fee(self.contracts * price, price, self.fee_rate, self.fee_exponent), 0.00245025, delta=1e-6)

    def test_price_0_5_c_125_5(self):
        price = 0.5
        c = 125.5
        self.assertAlmostEqual(calculate_platform_fee(c * price, price, self.fee_rate, self.fee_exponent), 1.9609375, delta=1e-6)


class TestBuilderFee(unittest.TestCase):
    def test_1pct_100_tokens_at_50c(self):
        price = 0.5
        contracts = 100
        builder_taker_fee_rate = 0.01
        self.assertAlmostEqual(calculate_builder_fee(contracts * price, builder_taker_fee_rate), 0.5, delta=1e-6)

    def test_5pct_200_tokens_at_75c(self):
        price = 0.75
        contracts = 200
        builder_taker_fee_rate = 0.05
        self.assertAlmostEqual(calculate_builder_fee(contracts * price, builder_taker_fee_rate), 7.5, delta=1e-6)


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

        self.assertAlmostEqual(platform_fee, 1.5625, delta=1e-6)
        self.assertAlmostEqual(builder_fee, 0.5, delta=1e-6)
        self.assertAlmostEqual(platform_fee + builder_fee, 2.0625, delta=1e-6)


class TestAdjustBuyAmountForFees(unittest.TestCase):
    fee_rate = 0.25
    fee_exponent = 2

    def test_no_adjustment_zero_fees(self):
        amount = 50
        result = adjust_market_buy_amount(amount, amount, 0.5, 0, 0, 0)
        self.assertEqual(result, amount)

    def test_no_adjustment_balance_above_total_cost(self):
        amount = 50
        price = 0.5
        platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        total_cost = amount + platform_fee
        balance = total_cost + 1
        result = adjust_market_buy_amount(amount, balance, price, self.fee_rate, self.fee_exponent, 0)
        self.assertEqual(result, amount)

    def test_boundary_balance_equals_total_cost(self):
        amount = 50
        price = 0.5
        platform_fee = calculate_platform_fee(amount, price, self.fee_rate, self.fee_exponent)
        total_cost = amount + platform_fee
        result = adjust_market_buy_amount(amount, total_cost, price, self.fee_rate, self.fee_exponent, 0)
        platform_fee_rate = self.fee_rate * (price * (1 - price)) ** self.fee_exponent
        expected = total_cost / (1 + platform_fee_rate / price)
        self.assertAlmostEqual(result, expected, places=9)

    def test_platform_fee_only_adjusted_plus_fee_equals_amount(self):
        amount = 50
        price = 0.5
        adjusted = adjust_market_buy_amount(amount, amount, price, self.fee_rate, self.fee_exponent, 0)
        fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent)
        self.assertAlmostEqual(adjusted + fee, amount, places=9)

    def test_builder_fee_only_adjusted_plus_fee_equals_amount(self):
        amount = 50
        price = 0.5
        builder_taker_fee_rate = 0.01
        adjusted = adjust_market_buy_amount(amount, amount, price, 0, 0, builder_taker_fee_rate)
        fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertAlmostEqual(adjusted + fee, amount, places=9)

    def test_platform_and_builder_fee_adjusted_plus_fees_equals_amount(self):
        amount = 50
        price = 0.5
        builder_taker_fee_rate = 0.01
        adjusted = adjust_market_buy_amount(amount, amount, price, self.fee_rate, self.fee_exponent, builder_taker_fee_rate)
        platform_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent)
        builder_fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertAlmostEqual(adjusted + platform_fee + builder_fee, amount, places=9)

    def test_adjusted_less_than_original(self):
        amount = 50
        adjusted = adjust_market_buy_amount(amount, amount, 0.5, self.fee_rate, self.fee_exponent, 0)
        self.assertLess(adjusted, amount)

    def test_price_0_3_platform_and_builder_adjusted_plus_fees_equals_amount(self):
        amount = 30
        price = 0.3
        builder_taker_fee_rate = 0.02
        adjusted = adjust_market_buy_amount(amount, amount, price, self.fee_rate, self.fee_exponent, builder_taker_fee_rate)
        platform_fee = calculate_platform_fee(adjusted, price, self.fee_rate, self.fee_exponent)
        builder_fee = calculate_builder_fee(adjusted, builder_taker_fee_rate)
        self.assertAlmostEqual(adjusted + platform_fee + builder_fee, amount, places=9)


class TestProductionFeeRatesV2(unittest.TestCase):
    amount = 100

    def test_sports_v2_rate_0_03_exp_1_price_0_5(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.5, 0.03, 1), 1.5, delta=1e-6)

    def test_sports_v2_rate_0_03_exp_1_price_0_3(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.3, 0.03, 1), 2.1, delta=1e-6)

    def test_sports_v2_rate_0_03_exp_1_price_0_7(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.7, 0.03, 1), 0.9, delta=1e-6)

    def test_politics_rate_0_04_exp_1_price_0_5(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.5, 0.04, 1), 2.0, delta=1e-6)

    def test_politics_rate_0_04_exp_1_price_0_3(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.3, 0.04, 1), 2.8, delta=1e-6)

    def test_politics_rate_0_04_exp_1_price_0_7(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.7, 0.04, 1), 1.2, delta=1e-6)

    def test_culture_rate_0_05_exp_1_price_0_5(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.5, 0.05, 1), 2.5, delta=1e-6)

    def test_culture_rate_0_05_exp_1_price_0_3(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.3, 0.05, 1), 3.5, delta=1e-6)

    def test_culture_rate_0_05_exp_1_price_0_7(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.7, 0.05, 1), 1.5, delta=1e-6)

    def test_crypto_rate_0_072_exp_1_price_0_5(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.5, 0.072, 1), 3.6, delta=1e-6)

    def test_crypto_rate_0_072_exp_1_price_0_3(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.3, 0.072, 1), 5.04, delta=1e-6)

    def test_crypto_rate_0_072_exp_1_price_0_7(self):
        self.assertAlmostEqual(calculate_platform_fee(self.amount, 0.7, 0.072, 1), 2.16, delta=1e-6)

    def test_balance_adjusted_plus_fee_equals_amount_all_rates(self):
        cases = [
            (0.03, 1, 0.3), (0.03, 1, 0.5), (0.03, 1, 0.7),
            (0.04, 1, 0.3), (0.04, 1, 0.5), (0.04, 1, 0.7),
            (0.05, 1, 0.3), (0.05, 1, 0.5), (0.05, 1, 0.7),
            (0.072, 1, 0.3), (0.072, 1, 0.5), (0.072, 1, 0.7),
        ]
        for rate, exponent, price in cases:
            with self.subTest(rate=rate, exponent=exponent, price=price):
                amount = 100
                adjusted = adjust_market_buy_amount(amount, amount, price, rate, exponent, 0)
                fee = calculate_platform_fee(adjusted, price, rate, exponent)
                self.assertAlmostEqual(adjusted + fee, amount, places=9)
