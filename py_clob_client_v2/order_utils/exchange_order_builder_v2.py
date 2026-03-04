import dataclasses
import time
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak as _keccak


def __hash_message(msg) -> bytes:
    return _keccak(primitive=msg.version + msg.header + msg.body)

from ..signer import Signer
from ..constants import BYTES32_ZERO
from .model.order_data_v2 import OrderDataV2, OrderV2, SignedOrderV2
from .model.signature_type_v2 import SignatureTypeV2
from .model.ctf_exchange_v2_typed_data import (
    CTF_EXCHANGE_V2_DOMAIN_NAME,
    CTF_EXCHANGE_V2_DOMAIN_VERSION,
    CTF_EXCHANGE_V2_ORDER_STRUCT,
    EIP712_DOMAIN,
)
from .utils import generate_order_salt


def _hex_to_bytes32(hex_str: str) -> bytes:
    """Convert a 0x-prefixed hex string to a 32-byte value."""
    return bytes.fromhex(hex_str.replace("0x", "").zfill(64))


class ExchangeOrderBuilderV2:
    def __init__(
        self,
        contract_address: str,
        chain_id: int,
        signer: Signer,
        generate_salt=generate_order_salt,
    ):
        self.contract_address = contract_address
        self.chain_id = chain_id
        self.signer = signer
        self.generate_salt = generate_salt

    def build_signed_order(self, order_data: OrderDataV2) -> SignedOrderV2:
        order = self.build_order(order_data)
        typed_data = self.build_order_typed_data(order)
        signature = self.build_order_signature(typed_data)
        return SignedOrderV2(**{**dataclasses.asdict(order), "signature": signature})

    def build_order(self, order_data: OrderDataV2) -> OrderV2:
        signer_addr = order_data.signer if order_data.signer else order_data.maker

        if signer_addr != self.signer.address():
            raise ValueError("signer does not match")

        return OrderV2(
            salt=self.generate_salt(),
            maker=order_data.maker,
            signer=signer_addr,
            tokenId=order_data.tokenId,
            makerAmount=order_data.makerAmount,
            takerAmount=order_data.takerAmount,
            side=order_data.side,
            signatureType=(
                order_data.signatureType
                if order_data.signatureType is not None
                else SignatureTypeV2.EOA
            ),
            expiration=order_data.expiration if order_data.expiration else "0",
            timestamp=(
                order_data.timestamp
                if order_data.timestamp
                else str(int(time.time()))
            ),
            metadata=order_data.metadata if order_data.metadata else BYTES32_ZERO,
            builder=order_data.builder if order_data.builder else BYTES32_ZERO,
        )

    def build_order_typed_data(self, order: OrderV2) -> dict:
        return {
            "primaryType": "Order",
            "types": {
                "EIP712Domain": EIP712_DOMAIN,
                "Order": CTF_EXCHANGE_V2_ORDER_STRUCT,
            },
            "domain": {
                "name": CTF_EXCHANGE_V2_DOMAIN_NAME,
                "version": CTF_EXCHANGE_V2_DOMAIN_VERSION,
                "chainId": self.chain_id,
                "verifyingContract": self.contract_address,
            },
            "message": {
                "salt": int(order.salt),
                "maker": order.maker,
                "signer": order.signer,
                "tokenId": int(order.tokenId),
                "makerAmount": int(order.makerAmount),
                "takerAmount": int(order.takerAmount),
                "side": int(order.side),
                "signatureType": int(order.signatureType),
                "timestamp": int(order.timestamp),
                "metadata": _hex_to_bytes32(order.metadata),
                "builder": _hex_to_bytes32(order.builder),
            },
        }

    def build_order_signature(self, typed_data: dict) -> str:
        encoded = encode_typed_data(full_message=typed_data)
        signed = Account.sign_message(encoded, private_key=self.signer.private_key)
        return "0x" + signed.signature.hex()

    def build_order_hash(self, typed_data: dict) -> str:
        encoded = encode_typed_data(full_message=typed_data)
        return "0x" + _hash_message(encoded).hex()
