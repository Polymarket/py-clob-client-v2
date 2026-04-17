import hashlib
import json
from decimal import Decimal

from .clob_types import OrderBookSummary, OrderSummary, TickSize


def parse_raw_orderbook_summary(raw_obs: dict) -> OrderBookSummary:
    bids = [OrderSummary(size=b["size"], price=b["price"]) for b in raw_obs["bids"]]
    asks = [OrderSummary(size=a["size"], price=a["price"]) for a in raw_obs["asks"]]

    return OrderBookSummary(
        market=raw_obs["market"],
        asset_id=raw_obs["asset_id"],
        timestamp=raw_obs["timestamp"],
        last_trade_price=raw_obs["last_trade_price"],
        min_order_size=raw_obs["min_order_size"],
        neg_risk=raw_obs["neg_risk"],
        tick_size=raw_obs["tick_size"],
        bids=bids,
        asks=asks,
        hash=raw_obs["hash"],
    )


def generate_orderbook_summary_hash(orderbook: OrderBookSummary) -> str:
    """
    Server-compatible orderbook hash.

    The server computes SHA1 over a compact JSON payload with a specific key order,
    and with the "hash" field set to an empty string while hashing.
    """
    payload = {
        "market": orderbook.market,
        "asset_id": orderbook.asset_id,
        "timestamp": orderbook.timestamp,
        "hash": "",
        "bids": [{"price": o.price, "size": o.size} for o in (orderbook.bids or [])],
        "asks": [{"price": o.price, "size": o.size} for o in (orderbook.asks or [])],
        "min_order_size": orderbook.min_order_size,
        "tick_size": orderbook.tick_size,
        "neg_risk": orderbook.neg_risk,
        "last_trade_price": orderbook.last_trade_price,
    }
    serialized = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    h = hashlib.sha1(serialized.encode("utf-8")).hexdigest()
    orderbook.hash = h
    return h


def adjust_market_buy_amount(
    amount: float,
    user_usdc_balance: float,
    price: float,
    fee_rate: float,
    fee_exponent: float,
    builder_taker_fee_rate: float = 0,
) -> float:
    """Return fee-adjusted amount for a market buy, or the original amount if balance is sufficient."""
    d_amount = Decimal(str(amount))
    d_price = Decimal(str(price))
    d_balance = Decimal(str(user_usdc_balance))
    d_fee_rate = Decimal(str(fee_rate))
    d_fee_exponent = Decimal(str(fee_exponent))
    d_btr = Decimal(str(builder_taker_fee_rate))

    base = d_price * (Decimal("1") - d_price)
    # Production fee exponents are integer (e.g. 1 or 2). Keep the whole
    # calculation in Decimal when possible; only fall back to a float pow
    # for the (unusual) non-integer case.
    if d_fee_exponent == d_fee_exponent.to_integral_value():
        base_pow = base ** int(d_fee_exponent)
    else:
        base_pow = Decimal(str(float(base) ** float(d_fee_exponent)))
    d_pfr = d_fee_rate * base_pow

    platform_fee = d_amount / d_price * d_pfr
    total_cost = d_amount + platform_fee + d_amount * d_btr
    if d_balance <= total_cost:
        divisor = Decimal("1") + d_pfr / d_price + d_btr
        return float(d_balance / divisor)
    return amount


def is_tick_size_smaller(a: TickSize, b: TickSize) -> bool:
    return float(a) < float(b)


def price_valid(price: float, tick_size: TickSize) -> bool:
    return float(tick_size) <= price <= 1 - float(tick_size)
