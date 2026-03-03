import hashlib
import json

from .clob_types import OrderBookSummary, OrderSummary, TickSize
from .order_utils.model.side import Side, SideString
from .order_utils.model.order_data_v1 import SignedOrderV1
from .order_utils.model.order_data_v2 import SignedOrderV2


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


def order_to_json_v1(
    order: SignedOrderV1,
    owner: str,
    order_type: str,
    defer_exec: bool = False,
) -> dict:
    side = SideString.BUY if order.side == Side.BUY else SideString.SELL
    return {
        "order": {
            "salt": int(order.salt),
            "maker": order.maker,
            "signer": order.signer,
            "taker": order.taker,
            "tokenId": order.tokenId,
            "makerAmount": order.makerAmount,
            "takerAmount": order.takerAmount,
            "side": side,
            "expiration": order.expiration,
            "nonce": order.nonce,
            "feeRateBps": order.feeRateBps,
            "signatureType": int(order.signatureType),
            "signature": order.signature,
        },
        "owner": owner,
        "orderType": order_type,
        "deferExec": defer_exec,
    }


def order_to_json_v2(
    order: SignedOrderV2,
    owner: str,
    order_type: str,
    defer_exec: bool = False,
) -> dict:
    side = SideString.BUY if order.side == Side.BUY else SideString.SELL
    return {
        "order": {
            "salt": int(order.salt),
            "maker": order.maker,
            "signer": order.signer,
            "tokenId": order.tokenId,
            "makerAmount": order.makerAmount,
            "takerAmount": order.takerAmount,
            "side": side,
            "expiration": order.expiration,
            "signatureType": int(order.signatureType),
            "timestamp": order.timestamp,
            "metadata": order.metadata,
            "builder": order.builder,
            "signature": order.signature,
        },
        "owner": owner,
        "orderType": order_type,
        "deferExec": defer_exec,
    }


def is_tick_size_smaller(a: TickSize, b: TickSize) -> bool:
    return float(a) < float(b)


def price_valid(price: float, tick_size: TickSize) -> bool:
    return float(tick_size) <= price <= 1 - float(tick_size)
