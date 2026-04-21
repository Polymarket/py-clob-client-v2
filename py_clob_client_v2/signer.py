from typing import Awaitable, Callable, Optional, Union

from eth_account import Account

SignatureValue = Union[str, bytes]
SignCallback = Callable[[str], Awaitable[SignatureValue]]


class Signer:
    def __init__(
        self,
        private_key: str = None,
        chain_id: int = None,
        address_override: str = None,
        sign_callback_override: Optional[SignCallback] = None,
    ):
        if chain_id is None:
            raise ValueError("chain_id is required")
        if private_key is None and (
            address_override is None or sign_callback_override is None
        ):
            raise ValueError(
                "Signer requires a private_key or both address_override and "
                "sign_callback_override"
            )

        self.private_key = private_key
        self.chain_id = chain_id
        self.address_override = address_override
        self.sign_callback_override = sign_callback_override
        self.account = Account.from_key(private_key) if private_key else None

    def address(self):
        if self.address_override is not None:
            return self.address_override
        return self.account.address

    def get_chain_id(self):
        return self.chain_id

    async def sign(self, message_hash):
        """
        Signs a 32-byte message hash.
        """
        if self.sign_callback_override is not None:
            signature = await self.sign_callback_override(message_hash)
            return self._normalize_signature(signature)

        signed = Account._sign_hash(
            self._normalize_message_hash(message_hash),
            private_key=self.private_key,
        )
        return signed.signature.hex()

    def _normalize_message_hash(self, message_hash) -> bytes:
        if isinstance(message_hash, str):
            normalized = (
                message_hash[2:] if message_hash.startswith("0x") else message_hash
            )
            return bytes.fromhex(normalized)
        if isinstance(message_hash, (bytes, bytearray)):
            return bytes(message_hash)
        raise TypeError("message_hash must be a hex string or bytes")

    def _normalize_signature(self, signature: SignatureValue) -> str:
        if isinstance(signature, str):
            return signature[2:] if signature.startswith("0x") else signature
        if isinstance(signature, (bytes, bytearray)):
            return bytes(signature).hex()
        if hasattr(signature, "hex"):
            return signature.hex()
        raise TypeError("signature must be a hex string or bytes")
