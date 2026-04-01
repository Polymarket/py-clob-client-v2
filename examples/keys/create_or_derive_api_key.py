import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient

load_dotenv()


def main():
    pk = os.environ["PK"]
    account = Account.from_key(pk)
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    print(f"Address: {account.address}, chainId: {chain_id}")

    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    client = ClobClient(host=host, chain_id=chain_id, key=pk)

    print("Response:")
    resp = client.create_or_derive_api_key()
    print(resp)
    print("Complete!")


if __name__ == "__main__":
    main()
