import dataclasses
import time
from eth_abi import encode as abi_encode
from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import keccak as _keccak


def _hash_message(msg) -> bytes:
    return _keccak(primitive=b"\x19" + msg.version + msg.header + msg.body)


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


ORDER_TYPE_STRING = (
    "Order(uint256 salt,address maker,address signer,uint256 tokenId,"
    "uint256 makerAmount,uint256 takerAmount,uint8 side,uint8 signatureType,"
    "uint256 timestamp,bytes32 metadata,bytes32 builder)"
)
SOLADY_TYPE_STRING = (
    "TypedDataSign(Order contents,string name,string version,uint256 chainId,"
    "address verifyingContract,bytes32 salt)"
    f"{ORDER_TYPE_STRING}"
)
DOMAIN_TYPE_STRING = (
    "EIP712Domain(string name,string version,uint256 chainId,address verifyingContract)"
)

ORDER_TYPE_HASH = _keccak(text=ORDER_TYPE_STRING)
DOMAIN_TYPE_HASH = _keccak(text=DOMAIN_TYPE_STRING)
SOLADY_TYPE_HASH = _keccak(text=SOLADY_TYPE_STRING)
DEPOSIT_WALLET_NAME_HASH = _keccak(text="DepositWallet")
DEPOSIT_WALLET_VERSION_HASH = _keccak(text="1")
CTF_EXCHANGE_NAME_HASH = _keccak(text=CTF_EXCHANGE_V2_DOMAIN_NAME)
CTF_EXCHANGE_VERSION_HASH = _keccak(text=CTF_EXCHANGE_V2_DOMAIN_VERSION)
DEPOSIT_WALLET_DOMAIN_SALT = bytes.fromhex(BYTES32_ZERO.replace("0x", "").zfill(64))


def _hex_to_bytes32(hex_str: str) -> bytes:
    """Convert a 0x-prefixed hex string to a 32-byte value."""
    return bytes.fromhex(hex_str.replace("0x", "").zfill(64))


def _bytes32(value) -> bytes:
    if isinstance(value, bytes):
        return value
    return _hex_to_bytes32(value)


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
        self.app_domain_separator = _keccak(
            primitive=abi_encode(
                ["bytes32", "bytes32", "bytes32", "uint256", "address"],
                [
                    DOMAIN_TYPE_HASH,
                    CTF_EXCHANGE_NAME_HASH,
                    CTF_EXCHANGE_VERSION_HASH,
                    chain_id,
                    contract_address,
                ],
            )
        )

    def build_signed_order(self, order_data: OrderDataV2) -> SignedOrderV2:
        order = self.build_order(order_data)
        typed_data = self.build_order_typed_data(order)
        signature = self.build_order_signature(typed_data)
        return SignedOrderV2(**{**dataclasses.asdict(order), "signature": signature})

    def build_order(self, order_data: OrderDataV2) -> OrderV2:
        signer_addr = order_data.signer if order_data.signer else order_data.maker
        signature_type = (
            SignatureTypeV2(order_data.signatureType)
            if order_data.signatureType is not None
            else SignatureTypeV2.EOA
        )

        if (
            signature_type != SignatureTypeV2.POLY_1271
            and signer_addr != self.signer.address()
        ):
            raise ValueError("signer does not match")

        return OrderV2(
            salt=self.generate_salt(),
            maker=order_data.maker,
            signer=signer_addr,
            tokenId=order_data.tokenId,
            makerAmount=order_data.makerAmount,
            takerAmount=order_data.takerAmount,
            side=order_data.side,
            signatureType=signature_type,
            timestamp=(
                order_data.timestamp
                if order_data.timestamp
                else str(time.time_ns() // 1_000_000)
            ),
            metadata=order_data.metadata if order_data.metadata else BYTES32_ZERO,
            builder=order_data.builder if order_data.builder else BYTES32_ZERO,
            expiration=order_data.expiration if order_data.expiration else "0",
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
        if typed_data["message"]["signatureType"] == int(SignatureTypeV2.POLY_1271):
            return self._build_poly_1271_order_signature(typed_data)

        encoded = encode_typed_data(full_message=typed_data)
        signed = Account.sign_message(encoded, private_key=self.signer.private_key)
        return "0x" + signed.signature.hex()

    def _build_poly_1271_order_signature(self, typed_data: dict) -> str:
        message = typed_data["message"]
        contents_hash = _keccak(
            primitive=abi_encode(
                [
                    "bytes32",
                    "uint256",
                    "address",
                    "address",
                    "uint256",
                    "uint256",
                    "uint256",
                    "uint8",
                    "uint8",
                    "uint256",
                    "bytes32",
                    "bytes32",
                ],
                [
                    ORDER_TYPE_HASH,
                    int(message["salt"]),
                    message["maker"],
                    message["signer"],
                    int(message["tokenId"]),
                    int(message["makerAmount"]),
                    int(message["takerAmount"]),
                    int(message["side"]),
                    int(message["signatureType"]),
                    int(message["timestamp"]),
                    _bytes32(message["metadata"]),
                    _bytes32(message["builder"]),
                ],
            )
        )
        typed_data_sign_struct_hash = _keccak(
            primitive=abi_encode(
                [
                    "bytes32",
                    "bytes32",
                    "bytes32",
                    "bytes32",
                    "uint256",
                    "address",
                    "bytes32",
                ],
                [
                    SOLADY_TYPE_HASH,
                    contents_hash,
                    DEPOSIT_WALLET_NAME_HASH,
                    DEPOSIT_WALLET_VERSION_HASH,
                    self.chain_id,
                    message["signer"],
                    DEPOSIT_WALLET_DOMAIN_SALT,
                ],
            )
        )
        digest = _keccak(
            primitive=(
                b"\x19\x01" + self.app_domain_separator + typed_data_sign_struct_hash
            )
        )
        signed = Account._sign_hash(digest, private_key=self.signer.private_key)
        inner_signature = signed.signature.hex()
        if inner_signature.startswith("0x"):
            inner_signature = inner_signature[2:]

        contents_type = ORDER_TYPE_STRING.encode("utf-8").hex()
        contents_type_len = len(ORDER_TYPE_STRING).to_bytes(2, "big").hex()

        return (
            "0x"
            + inner_signature
            + self.app_domain_separator.hex()
            + contents_hash.hex()
            + contents_type
            + contents_type_len
        )

    def build_order_hash(self, typed_data: dict) -> str:
        encoded = encode_typed_data(full_message=typed_data)
        return "0x" + _hash_message(encoded).hex()
