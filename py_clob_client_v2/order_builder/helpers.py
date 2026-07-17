from math import gcd
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_EVEN, ROUND_UP


def _round_decimal(x: float, sig_digits: int, rounding) -> float:
    scale = Decimal(10) ** sig_digits
    rounded = (Decimal(str(x)) * scale).to_integral_value(rounding=rounding)
    return float(rounded / scale)


def round_down(x: float, sig_digits: int) -> float:
    return _round_decimal(x, sig_digits, ROUND_DOWN)


def round_normal(x: float, sig_digits: int) -> float:
    return _round_decimal(x, sig_digits, ROUND_HALF_EVEN)


def round_up(x: float, sig_digits: int) -> float:
    return _round_decimal(x, sig_digits, ROUND_UP)


def to_token_decimals(x: float) -> int:
    return int(
        (Decimal(str(x)) * Decimal("1000000")).to_integral_value(
            rounding=ROUND_HALF_EVEN
        )
    )


def price_to_fraction(price: float, sig_digits: int) -> tuple[int, int]:
    scale = 10**sig_digits
    price_units = int(
        (Decimal(str(price)) * Decimal(scale)).to_integral_value(
            rounding=ROUND_DOWN
        )
    )

    if price_units <= 0:
        raise ValueError("price must be greater than zero")

    divisor = gcd(price_units, scale)
    return price_units // divisor, scale // divisor


def decimal_places(x: float) -> int:
    return abs(Decimal(x.__str__()).as_tuple().exponent)
