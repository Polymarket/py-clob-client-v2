import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds

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
    client = ClobClient(host=host, chain_id=chain_id, key=pk, creds=creds)

    resp = client.cancel_orders([
        "0x7ce769d075f4f1263603fde09862f5998f5e6ae4a39a16f3780f0bd708d3fc1c",
    ])
    print(resp)
    print("Done!")


if __name__ == "__main__":
    main()
