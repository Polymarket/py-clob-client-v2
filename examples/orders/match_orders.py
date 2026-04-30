import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, OrderArgs, PartialCreateOrderOptions
from py_clob_client_v2 import Side

load_dotenv()

# CLOB blocks self-trading: a bid and ask from the same address will never match.
# This example uses two separate wallets (PK and PK2) with their own API credentials
# so the orders can actually fill against each other.

YES = os.environ.get(
    "YES_TOKEN_ID",
    "71321045679252212594626385532706912750332728571942532289631379312455583992563",
)


def main():
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")

    pk1 = os.environ["PK"]
    creds1 = ApiCreds(
        api_key=os.environ["CLOB_API_KEY"],
        api_secret=os.environ["CLOB_SECRET"],
        api_passphrase=os.environ["CLOB_PASS_PHRASE"],
    )
    client1 = ClobClient(host=host, chain_id=chain_id, key=pk1, creds=creds1)

    pk2 = os.environ["PK2"]
    creds2 = ApiCreds(
        api_key=os.environ["CLOB_API_KEY_2"],
        api_secret=os.environ["CLOB_SECRET_2"],
        api_passphrase=os.environ["CLOB_PASS_PHRASE_2"],
    )
    client2 = ClobClient(host=host, chain_id=chain_id, key=pk2, creds=creds2)

    print(f"Wallet 1: {Account.from_key(pk1).address}")
    print(f"Wallet 2: {Account.from_key(pk2).address}")

    options = PartialCreateOrderOptions(tick_size="0.01")

    yes_bid = client1.create_order(
        order_args=OrderArgs(token_id=YES, price=0.5, side=Side.BUY, size=100),
        options=options,
    )
    print("posting bid from wallet1", yes_bid)
    client1.post_order(yes_bid)

    yes_ask = client2.create_order(
        order_args=OrderArgs(token_id=YES, price=0.5, side=Side.SELL, size=100),
        options=options,
    )
    print("posting ask from wallet2", yes_ask)
    client2.post_order(yes_ask)

    print("Done!")


if __name__ == "__main__":
    main()
