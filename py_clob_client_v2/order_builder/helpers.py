from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR, ROUND_HALF_UP


TOKEN_DECIMAL_SCALE = Decimal("1000000")


def _as_decimal(x: float) -> Decimal:
    return Decimal(str(x))


def _quantum(sig_digits: int) -> Decimal:
    return Decimal(1).scaleb(-sig_digits)


def round_down(x: float, sig_digits: int) -> float:
    return float(_as_decimal(x).quantize(_quantum(sig_digits), rounding=ROUND_FLOOR))


def round_normal(x: float, sig_digits: int) -> float:
    return float(_as_decimal(x).quantize(_quantum(sig_digits), rounding=ROUND_HALF_UP))


def round_up(x: float, sig_digits: int) -> float:
    return float(_as_decimal(x).quantize(_quantum(sig_digits), rounding=ROUND_CEILING))


def to_token_decimals(x: float) -> int:
    return int(
        (_as_decimal(x) * TOKEN_DECIMAL_SCALE).quantize(
            Decimal("1"), rounding=ROUND_HALF_UP
        )
    )


def decimal_places(x: float) -> int:
    exponent = _as_decimal(x).as_tuple().exponent
    return abs(exponent) if exponent < 0 else 0
