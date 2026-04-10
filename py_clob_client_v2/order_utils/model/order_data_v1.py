from dataclasses import dataclass
from typing import Optional

from .side import Side, SideString
from .signature_type_v1 import SignatureTypeV1


@dataclass
class OrderDataV1:
    """Input data for building a V1 order."""

    maker: str
    taker: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    side: Side
    feeRateBps: str = "0"
    nonce: str = "0"
    signer: Optional[str] = None
    expiration: Optional[str] = None
    signatureType: Optional[SignatureTypeV1] = None


@dataclass
class OrderV1:
    """An unsigned V1 order ready for EIP712 signing."""

    salt: str
    maker: str
    signer: str
    taker: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    expiration: str
    nonce: str
    feeRateBps: str
    side: Side
    signatureType: SignatureTypeV1


@dataclass
class SignedOrderV1(OrderV1):
    """A signed V1 order including the EIP712 signature."""

    signature: str = ""


def order_to_json_v1(
    order: "SignedOrderV1",
    owner: str,
    order_type: str,
    post_only: bool = False,
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
        "postOnly": post_only,
    }
