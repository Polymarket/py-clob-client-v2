import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, SignatureTypeV2

load_dotenv()


def main():
    pk = os.environ["PK"]
    account = Account.from_key(pk)
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    print(f"Address: {account.address}, chainId: {chain_id}")

    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    creds = ApiCreds(
        api_key=os.environ["CLOB_API_KEY"],
        api_secret=os.environ["CLOB_SECRET"],
        api_passphrase=os.environ["CLOB_PASS_PHRASE"],
    )

    # Client used with an EOA: Signature type 0
    client = ClobClient(host=host, chain_id=chain_id, key=pk, creds=creds)

    # Client used with a Polymarket Proxy Wallet: Signature type 1
    proxy_wallet_address = "0x..."
    poly_proxy_client = ClobClient(
        host=host,
        chain_id=chain_id,
        key=pk,
        creds=creds,
        signature_type=SignatureTypeV2.POLY_PROXY,
        funder=proxy_wallet_address,
    )

    # Client used with a Polymarket Gnosis Safe: Signature type 2
    gnosis_safe_address = "0x..."
    poly_gnosis_safe_client = ClobClient(
        host=host,
        chain_id=chain_id,
        key=pk,
        creds=creds,
        signature_type=SignatureTypeV2.POLY_GNOSIS_SAFE,
        funder=gnosis_safe_address,
    )

    # Client used with a Polymarket Deposit Wallet: Signature type 3
    deposit_wallet_address = "0x..."
    deposit_wallet_client = ClobClient(
        host=host,
        chain_id=chain_id,
        key=pk,
        creds=creds,
        signature_type=SignatureTypeV2.POLY_1271,
        funder=deposit_wallet_address,
    )


if __name__ == "__main__":
    main()
