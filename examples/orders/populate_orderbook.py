import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, OrderArgs, PartialCreateOrderOptions
from py_clob_client_v2 import Side

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

    options = PartialCreateOrderOptions(tick_size="0.01")

    YES = os.environ.get(
        "YES_TOKEN_ID",
        "71321045679252212594626385532706912750332728571942532289631379312455583992563",
    )
    yes_bid = client.create_order(OrderArgs(token_id=YES, price=0.4, side=Side.BUY, size=100), options)
    print("creating order", yes_bid)
    client.post_order(yes_bid)

    yes_ask = client.create_order(OrderArgs(token_id=YES, price=0.6, side=Side.SELL, size=100), options)
    print("creating order", yes_ask)
    client.post_order(yes_ask)

    NO = os.environ.get(
        "NO_TOKEN_ID",
        "52114319501245915516055106046884209969926127482827954674443846427813813222426",
    )
    no_bid = client.create_order(OrderArgs(token_id=NO, price=0.4, side=Side.BUY, size=100), options)
    print("creating order", no_bid)
    client.post_order(no_bid)

    no_ask = client.create_order(OrderArgs(token_id=NO, price=0.6, side=Side.SELL, size=100), options)
    print("creating order", no_ask)
    client.post_order(no_ask)

    print("Done!")


if __name__ == "__main__":
    main()
