import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, TradeParams

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

    # only first page
    print(client.get_trades_paginated(TradeParams(
        market="0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
        maker_address=account.address,
    )))

    # fetch only second page
    print(client.get_trades_paginated(
        TradeParams(
            market="0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
            maker_address=account.address,
        ),
        next_cursor="MzAw",
    ))


if __name__ == "__main__":
    main()
