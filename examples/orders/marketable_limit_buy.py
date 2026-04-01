import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient, ApiCreds, OrderType, OrderArgs, PartialCreateOrderOptions
from py_clob_client_v2 import Side

load_dotenv()

# A marketable limit buy crosses the spread and fills immediately against resting asks.
# CLOB blocks self-trading, so a second wallet seeds the ask that wallet1 will fill against.

YES = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
PRICE = 0.5
SIZE = 100


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

    # Wallet2 seeds a resting ask at PRICE
    ask = client2.create_and_post_order(
        order_args=OrderArgs(token_id=YES, price=PRICE, side=Side.SELL, size=SIZE),
        options=PartialCreateOrderOptions(tick_size="0.01"),
        order_type=OrderType.GTC,
    )
    print("seeded ask", ask)

    # Wallet1 buys at the same price — crosses the spread and matches immediately
    resp = client1.create_and_post_order(
        order_args=OrderArgs(token_id=YES, price=PRICE, side=Side.BUY, size=SIZE),
        options=PartialCreateOrderOptions(tick_size="0.01"),
        order_type=OrderType.GTC,
    )
    print(resp)


if __name__ == "__main__":
    main()
