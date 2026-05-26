import os

from dotenv import load_dotenv

from py_clob_client_v2 import (
    ApiCreds,
    ClobClient,
    OrderArgs,
    OrderType,
    PartialCreateOrderOptions,
    Side,
    SignatureTypeV2,
)

load_dotenv()

YES = os.environ.get(
    "YES_TOKEN_ID",
    "71321045679252212594626385532706912750332728571942532289631379312455583992563",
)


def main():
    pk = os.environ["PK"]
    deposit_wallet = os.environ["DEPOSIT_WALLET"]
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    creds = ApiCreds(
        api_key=os.environ["CLOB_API_KEY"],
        api_secret=os.environ["CLOB_SECRET"],
        api_passphrase=os.environ["CLOB_PASS_PHRASE"],
    )

    client = ClobClient(
        host=host,
        chain_id=chain_id,
        key=pk,
        creds=creds,
        signature_type=SignatureTypeV2.POLY_1271,
        funder=deposit_wallet,
    )

    # Requires the deposit wallet to be deployed, funded, and approved.
    resp = client.create_and_post_order(
        order_args=OrderArgs(token_id=YES, price=0.4, side=Side.BUY, size=100),
        options=PartialCreateOrderOptions(tick_size="0.01"),
        order_type=OrderType.GTC,
    )
    print(resp)


if __name__ == "__main__":
    main()
