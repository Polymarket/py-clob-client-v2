import dataclasses
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak as _keccak


def __hash_message(msg) -> bytes:
    return _keccak(primitive=msg.version + msg.header + msg.body)

from ..signer import Signer
from ..constants import ZERO_ADDRESS
from .model.order_data_v1 import OrderDataV1, OrderV1, SignedOrderV1
from .model.signature_type_v1 import SignatureTypeV1
from .model.ctf_exchange_v1_typed_data import (
    CTF_EXCHANGE_V1_DOMAIN_NAME,
    CTF_EXCHANGE_V1_DOMAIN_VERSION,
    CTF_EXCHANGE_V1_ORDER_STRUCT,
    EIP712_DOMAIN,
)
from .utils import generate_order_salt


class ExchangeOrderBuilderV1:
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

    def build_signed_order(self, order_data: OrderDataV1) -> SignedOrderV1:
        order = self.build_order(order_data)
        typed_data = self.build_order_typed_data(order)
        signature = self.build_order_signature(typed_data)
        return SignedOrderV1(**{**dataclasses.asdict(order), "signature": signature})

    def build_order(self, order_data: OrderDataV1) -> OrderV1:
        signer_addr = order_data.signer if order_data.signer else order_data.maker

        if signer_addr != self.signer.address():
            raise ValueError("signer does not match")

        return OrderV1(
            salt=self.generate_salt(),
            maker=order_data.maker,
            signer=signer_addr,
            taker=order_data.taker if order_data.taker else ZERO_ADDRESS,
            tokenId=order_data.tokenId,
            makerAmount=order_data.makerAmount,
            takerAmount=order_data.takerAmount,
            expiration=order_data.expiration if order_data.expiration else "0",
            nonce=order_data.nonce if order_data.nonce else "0",
            feeRateBps=order_data.feeRateBps if order_data.feeRateBps else "0",
            side=order_data.side,
            signatureType=(
                order_data.signatureType
                if order_data.signatureType is not None
                else SignatureTypeV1.EOA
            ),
        )

    def build_order_typed_data(self, order: OrderV1) -> dict:
        return {
            "primaryType": "Order",
            "types": {
                "EIP712Domain": EIP712_DOMAIN,
                "Order": CTF_EXCHANGE_V1_ORDER_STRUCT,
            },
            "domain": {
                "name": CTF_EXCHANGE_V1_DOMAIN_NAME,
                "version": CTF_EXCHANGE_V1_DOMAIN_VERSION,
                "chainId": self.chain_id,
                "verifyingContract": self.contract_address,
            },
            "message": {
                "salt": int(order.salt),
                "maker": order.maker,
                "signer": order.signer,
                "taker": order.taker,
                "tokenId": int(order.tokenId),
                "makerAmount": int(order.makerAmount),
                "takerAmount": int(order.takerAmount),
                "expiration": int(order.expiration),
                "nonce": int(order.nonce),
                "feeRateBps": int(order.feeRateBps),
                "side": int(order.side),
                "signatureType": int(order.signatureType),
            },
        }

    def build_order_signature(self, typed_data: dict) -> str:
        encoded = encode_typed_data(full_message=typed_data)
        signed = Account.sign_message(encoded, private_key=self.signer.private_key)
        return "0x" + signed.signature.hex()

    def build_order_hash(self, typed_data: dict) -> str:
        encoded = encode_typed_data(full_message=typed_data)
        return "0x" + _hash_message(encoded).hex()
