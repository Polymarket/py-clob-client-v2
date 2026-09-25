from math import floor, ceil
from decimal import Decimal
from typing import Optional, Tuple, Union

from ..clob_types import (
    OrderArgsV1,
    OrderArgsV2,
    MarketOrderArgsV1,
    MarketOrderArgsV2,
    _resolve_order_asset,
)


def round_down(x: float, sig_digits: int) -> float:
    return floor(x * (10**sig_digits)) / (10**sig_digits)


def round_normal(x: float, sig_digits: int) -> float:
    return round(x * (10**sig_digits)) / (10**sig_digits)


def round_up(x: float, sig_digits: int) -> float:
    return ceil(x * (10**sig_digits)) / (10**sig_digits)


def to_token_decimals(x: float) -> int:
    f = (10**6) * x
    if decimal_places(f) > 0:
        f = round_normal(f, 0)
    return int(f)


def decimal_places(x: float) -> int:
    return abs(Decimal(x.__str__()).as_tuple().exponent)


def _resolve_order_routing(
    order_args: Union[OrderArgsV1, OrderArgsV2, MarketOrderArgsV1, MarketOrderArgsV2],
    version: Optional[int] = None,
) -> Tuple[str, Optional[int]]:
    position_id = getattr(order_args, "position_id", None)
    asset_id = _resolve_order_asset(order_args.token_id, position_id)
    return asset_id, 3 if position_id is not None else version
