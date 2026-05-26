import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, OrderMarketCancelParams

load_dotenv()

YES_TOKEN_ID = os.environ.get(
    "YES_TOKEN_ID",
    "71321045679252212594626385532706912750332728571942532289631379312455583992563",
)
NO_TOKEN_ID = os.environ.get(
    "NO_TOKEN_ID",
    "52114319501245915516055106046884209969926127482827954674443846427813813222426",
)
CONDITION_ID = os.environ.get(
    "CONDITION_ID",
    "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
)


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

    print(client.cancel_market_orders(OrderMarketCancelParams(market=CONDITION_ID)))
    print(client.cancel_market_orders(OrderMarketCancelParams(asset_id=YES_TOKEN_ID)))
    print(client.cancel_market_orders(OrderMarketCancelParams(asset_id=NO_TOKEN_ID)))


if __name__ == "__main__":
    main()
