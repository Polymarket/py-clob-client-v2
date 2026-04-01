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

    order = client.get_order("0x831680cb77da95792af5a052c87c8abf9d2ae5cb21f275670bc0ff58f2823c5c")
    print(order)


if __name__ == "__main__":
    main()
