import unittest

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import FeeInfo, MarketOrderArgsV2, OrderArgsV2
from py_clob_client_v2.constants import AMOY
from py_clob_client_v2.order_utils.model.side import Side

# publicly known private key
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
TOKEN_ID = "123"
FEE_RATE = 0.25
FEE_EXPONENT = 2


def _make_cached_client(fee_slippage: float = 0) -> ClobClient:
    client = ClobClient(
        host="https://clob.polymarket.com",
        chain_id=AMOY,
        key=PRIVATE_KEY,
        fee_slippage=fee_slippage,
    )
    client._ClobClient__tick_sizes[TOKEN_ID] = "0.01"
    client._ClobClient__neg_risk[TOKEN_ID] = False
    client._ClobClient__fee_infos[TOKEN_ID] = FeeInfo(rate=FEE_RATE, exponent=FEE_EXPONENT)
    client._ClobClient__cached_version = 2
    return client


class TestClobClientFeeSlippage(unittest.TestCase):
    def test_defaults_to_zero(self):
        client = ClobClient(host="https://clob.polymarket.com", chain_id=AMOY)
        self.assertEqual(client.fee_slippage, 0)

    def test_accepts_float_between_1_and_100(self):
        client = ClobClient(
            host="https://clob.polymarket.com",
            chain_id=AMOY,
            fee_slippage=12.5,
        )
        self.assertEqual(client.fee_slippage, 12.5)

    def test_rejects_invalid_values_at_init(self):
        def make(fee_slippage):
            ClobClient(
                host="https://clob.polymarket.com",
                chain_id=AMOY,
                fee_slippage=fee_slippage,
            )

        with self.assertRaises(ValueError):
            make(0.5)
        with self.assertRaises(ValueError):
            make(101)
        with self.assertRaises(ValueError):
            make(float("nan"))


class TestClientOrderFeeAdjustment(unittest.TestCase):
    def test_adjusts_v2_buy_limit_size_when_user_usdc_balance_provided(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            size=100,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        signed = client.create_order(order)
        # requestedNotional = 100 * 0.5 = 50
        # feeBaseAmount = min(50, 50) = 50
        # feeRateComponent = 0.25 * (0.5 * 0.5)^2 = 0.015625
        # paddedFee = (50 / 0.5) * 0.015625 * 1.2 = 1.875
        # adjustedNotional = 50 - 1.875 = 48.125
        # adjustedSize = 48.125 / 0.5 = 96.25
        # makerAmount = 96.25 * 0.5 * 1e6 = 48125000
        # takerAmount = 96.25 * 1e6 = 96250000
        self.assertEqual(signed.makerAmount, "48125000")
        self.assertEqual(signed.takerAmount, "96250000")
        self.assertEqual(order.size, 100)

    def test_adjusts_v2_buy_limit_when_price_rounds_up_to_tick(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.506,  # rounds to 0.51 for tick 0.01
            size=100,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        signed = client.create_order(order)
        signed_notional = int(signed.makerAmount) / 1_000_000
        signed_shares = int(signed.takerAmount) / 1_000_000
        # Input price 0.505 rounds to 0.51
        # requestedNotional = 100 * 0.51 = 51, balance = 50
        # feeBaseAmount = min(51, 50) = 50
        # feeRateComponent = 0.25 * (0.51 * 0.49)^2 = 0.0156125025
        # paddedFeeRate = 0.0156125025 * 1.2 = 0.018735003
        # paddedFee = (50 / 0.51) * 0.018735003 ≈ 1.836765
        # adjustedNotional = 50 - 1.836765 = 48.163235
        # adjustedSize = 48.163235 / 0.51 ≈ 94.437...
        # roundDown(94.437, 2) = 94.43
        # makerAmount = 94.43 * 0.51 * 1e6 = 48159300
        # takerAmount = 94.43 * 1e6 = 94430000
        self.assertEqual(signed.makerAmount, "48159300")
        self.assertEqual(signed.takerAmount, "94430000")
        self.assertAlmostEqual(signed_notional, 48.1593, places=4)
        self.assertAlmostEqual(signed_shares, 94.43, places=2)

    def test_adjusts_v2_buy_market_amount_when_user_usdc_balance_provided(self):
        client = _make_cached_client(fee_slippage=20)
        order = MarketOrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            amount=50,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        signed = client.create_market_order(order)
        # market BUY amount is already cash notional
        # feeBaseAmount = min(50, 50) = 50
        # paddedFee = (50 / 0.5) * 0.015625 * 1.2 = 1.875
        # adjustedAmount = 50 - 1.875 = 48.125
        # roundDown(48.125, 2) = 48.12
        # rawPrice = roundDown(0.5, 2) = 0.5
        # takerAmount = 48.12 / 0.5 = 96.24
        # makerAmount = 48.12 * 1e6 = 48120000
        # takerAmount = 96.24 * 1e6 = 96240000
        self.assertEqual(signed.makerAmount, "48120000")
        self.assertEqual(signed.takerAmount, "96240000")
        self.assertEqual(order.amount, 50)

    def test_v2_buy_limit_unchanged_without_user_usdc_balance(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            size=100,
            side=Side.BUY,
        )
        signed = client.create_order(order)
        self.assertEqual(signed.makerAmount, "50000000")
        self.assertEqual(signed.takerAmount, "100000000")

    def test_v2_sell_limit_unchanged_with_user_usdc_balance(self):
        client = _make_cached_client(fee_slippage=20)
        order = OrderArgsV2(
            token_id=TOKEN_ID,
            price=0.5,
            size=100,
            side=Side.SELL,
            user_usdc_balance=50,
        )
        signed = client.create_order(order)
        self.assertEqual(signed.makerAmount, "100000000")
        self.assertEqual(signed.takerAmount, "50000000")
