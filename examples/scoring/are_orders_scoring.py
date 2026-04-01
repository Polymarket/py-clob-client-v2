import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, OrdersScoringParams

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

    scoring = client.are_orders_scoring(OrdersScoringParams(orderIds=[
        "0x9355abd8ac2f9144ec19d31756ca92a8738a20c5ad65125cc2e8ea3f58d589aa",
        "0xde0c7c616190e34a81ce05adb3414d7f1e865bfea1f1cc40f6cc1d6fbd7b6345",
    ]))
    print(scoring)


if __name__ == "__main__":
    main()
