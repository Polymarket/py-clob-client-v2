import math

MIN_FEE_SLIPPAGE_PERCENTAGE = 1
MAX_FEE_SLIPPAGE_PERCENTAGE = 100


def validate_fee_slippage(fee_slippage: float) -> None:
    try:
        is_finite = math.isfinite(fee_slippage)
    except (TypeError, ValueError):
        is_finite = False
    if (
        not is_finite
        or fee_slippage < 0
        or fee_slippage > MAX_FEE_SLIPPAGE_PERCENTAGE
        or (fee_slippage > 0 and fee_slippage < MIN_FEE_SLIPPAGE_PERCENTAGE)
    ):
        raise ValueError("fee_slippage must be 0 or a percentage between 1 and 100")


def adjust_buy_amount_for_fees(
    amount: float,
    price: float,
    user_usdc_balance: float,
    fee_rate: float,
    fee_exponent: float,
    builder_taker_fee_rate: float,
    fee_slippage: float = 0,
) -> float:
    validate_fee_slippage(fee_slippage)
    platform_fee_rate = fee_rate * (price * (1 - price)) ** fee_exponent
    effective_platform_fee_rate = platform_fee_rate * (1 + fee_slippage / 100)
    fee_base_amount = min(amount, user_usdc_balance)
    platform_fee = (fee_base_amount / price) * effective_platform_fee_rate
    builder_fee = fee_base_amount * builder_taker_fee_rate
    total_cost = amount + platform_fee + builder_fee

    if user_usdc_balance <= total_cost:
        return max(user_usdc_balance - platform_fee - builder_fee, 0)
    return amount
