from py_clob_client_v2.order_builder.builder import OrderBuilder, ROUNDING_CONFIG
from py_clob_client_v2.order_builder.constants import BUY, SELL
from py_clob_client_v2.order_builder.helpers import (
    round_down,
    to_token_decimals,
    price_to_fraction,
)


def test_round_down_avoids_float_artifacts():
    assert round_down(0.29, 2) == 0.29
    assert round_down(0.936000936000936, 3) == 0.936


def test_to_token_decimals_avoids_float_artifacts():
    assert to_token_decimals(0.51) == 510000
    assert to_token_decimals(0.53) == 530000
    assert to_token_decimals(0.47) == 470000
    assert to_token_decimals(0.49) == 490000


def test_price_to_fraction_reduces_tick_price():
    assert price_to_fraction(0.936, 3) == (117, 125)
    assert price_to_fraction(0.51, 2) == (51, 100)


def test_market_buy_amounts_preserve_tick_price_001():
    builder = OrderBuilder(None)

    _, maker_amount, taker_amount = builder.get_market_order_amounts(
        BUY,
        amount=2,
        price=0.936,
        round_config=ROUNDING_CONFIG["0.001"],
    )

    assert maker_amount == 1_999_998
    assert taker_amount == 2_136_750
    assert maker_amount * 1000 == taker_amount * 936


def test_market_buy_amounts_preserve_tick_price_01():
    builder = OrderBuilder(None)

    _, maker_amount, taker_amount = builder.get_market_order_amounts(
        BUY,
        amount=1.06,
        price=0.51,
        round_config=ROUNDING_CONFIG["0.01"],
    )

    assert maker_amount == 1_059_984
    assert taker_amount == 2_078_400
    assert maker_amount * 100 == taker_amount * 51


def test_market_sell_amounts_preserve_tick_price_001():
    builder = OrderBuilder(None)

    _, maker_amount, taker_amount = builder.get_market_order_amounts(
        SELL,
        amount=2,
        price=0.936,
        round_config=ROUNDING_CONFIG["0.001"],
    )

    assert maker_amount == 2_000_000
    assert taker_amount == 1_872_000
    assert taker_amount * 1000 == maker_amount * 936
