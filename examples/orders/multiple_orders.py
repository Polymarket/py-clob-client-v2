import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import (
    ClobClient, ApiCreds, OrderType, OrderArgs, PartialCreateOrderOptions,
    PostOrdersV2Args,
)
from py_clob_client_v2 import Side

load_dotenv()

YES = "71321045679252212594626385532706912750332728571942532289631379312455583992563"


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

    client.cancel_all()

    options = PartialCreateOrderOptions(tick_size="0.01")

    orders = [
        PostOrdersV2Args(
            order=client.create_order(OrderArgs(token_id=YES, price=0.4, side=Side.BUY, size=100), options),
            orderType=OrderType.GTC,
        ),
        PostOrdersV2Args(
            order=client.create_order(OrderArgs(token_id=YES, price=0.45, side=Side.BUY, size=100), options),
            orderType=OrderType.GTC,
        ),
        PostOrdersV2Args(
            order=client.create_order(OrderArgs(token_id=YES, price=0.55, side=Side.SELL, size=100), options),
            orderType=OrderType.GTC,
        ),
        PostOrdersV2Args(
            order=client.create_order(OrderArgs(token_id=YES, price=0.6, side=Side.SELL, size=100), options),
            orderType=OrderType.GTC,
        ),
    ]

    resp = client.post_orders(orders)
    print(resp)


if __name__ == "__main__":
    main()
