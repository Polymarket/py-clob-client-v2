import os
from dotenv import load_dotenv

from py_clob_client_v2 import (
    ClobClient, ApiCreds, OrderType, OrderArgs, MarketOrderArgs, PartialCreateOrderOptions,
)
from py_clob_client_v2 import Side

load_dotenv()

# Market sell — amount is in shares. Requires resting bids in the book to fill against.
# CLOB blocks self-trading, so a second wallet seeds the bid.
#
# OrderType.FOK (Fill Or Kill): the entire order must fill immediately or it is cancelled.
# OrderType.FAK (Fill And Kill): fills as much as possible immediately, remainder is cancelled.
# Swap FOK for FAK in create_and_post_market_order to use FAK instead.

YES = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
AMOUNT_SHARES = 100
SEED_PRICE = 0.5
SEED_SIZE = 150


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

    # Wallet2 seeds a resting bid for wallet1 to fill against
    bid = client2.create_and_post_order(
        order_args=OrderArgs(token_id=YES, price=SEED_PRICE, side=Side.BUY, size=SEED_SIZE),
        options=PartialCreateOrderOptions(tick_size="0.01"),
        order_type=OrderType.GTC,
    )
    print("seeded bid", bid)

    resp = client1.create_and_post_market_order(
        order_args=MarketOrderArgs(
            token_id=YES,
            amount=AMOUNT_SHARES,
            side=Side.SELL,
            order_type=OrderType.FOK,
            # user_usdc_balance=500,  # optional
            # builder_code=os.environ.get("BUILDER_CODE"),  # optional
        ),
        options=PartialCreateOrderOptions(tick_size="0.01"),
        order_type=OrderType.FOK,
    )
    print(resp)


if __name__ == "__main__":
    main()
