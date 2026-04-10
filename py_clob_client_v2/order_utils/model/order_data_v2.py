from dataclasses import dataclass
from typing import Optional

from .side import Side, SideString
from .signature_type_v2 import SignatureTypeV2


@dataclass
class OrderDataV2:
    """Input data for building a V2 order."""

    maker: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    side: Side
    signer: Optional[str] = None
    signatureType: Optional[SignatureTypeV2] = None
    timestamp: Optional[str] = None
    metadata: Optional[str] = None
    builder: Optional[str] = None
    expiration: Optional[str] = None


@dataclass
class OrderV2:
    """An unsigned V2 order ready for EIP712 signing."""

    salt: str
    maker: str
    signer: str
    tokenId: str
    makerAmount: str
    takerAmount: str
    side: Side
    signatureType: SignatureTypeV2
    timestamp: str
    metadata: str
    builder: str
    expiration: str = "0"


@dataclass
class SignedOrderV2(OrderV2):
    """A signed V2 order including the EIP712 signature."""

    signature: str = ""


def order_to_json_v2(
    order: "SignedOrderV2",
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
        "postOnly": post_only,
    }
