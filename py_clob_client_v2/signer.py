from eth_account import Account


class Signer:
    def __init__(self, private_key: str, chain_id: int):
        assert private_key is not None and chain_id is not None

        self.private_key = private_key
        self.account = Account.from_key(private_key)
        self.chain_id = chain_id

    def address(self):
        return self.account.address

    def get_chain_id(self):
        return self.chain_id

    def sign(self, message_hash):
        """Sign a 32-byte message hash and return a hex signature (no 0x prefix)."""
        # `Account.unsafe_sign_hash` is the public successor to the private
        # `Account._sign_hash`. Fall back to the legacy names on older
        # eth-account releases.
        signer = getattr(Account, "unsafe_sign_hash", None) or getattr(
            Account, "_sign_hash", None
        ) or getattr(Account, "signHash")
        return signer(message_hash, self.private_key).signature.hex()
