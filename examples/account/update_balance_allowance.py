import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds, BalanceAllowanceParams, AssetType

load_dotenv()

YES = os.environ.get(
    "YES_TOKEN_ID",
    "71321045679252212594626385532706912750332728571942532289631379312455583992563",
)
NO = os.environ.get(
    "NO_TOKEN_ID",
    "52114319501245915516055106046884209969926127482827954674443846427813813222426",
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

    # USDC
    client.update_balance_allowance(BalanceAllowanceParams(asset_type=AssetType.COLLATERAL))

    # YES
    client.update_balance_allowance(BalanceAllowanceParams(
        asset_type=AssetType.CONDITIONAL,
        token_id=YES,
    ))

    # NO
    client.update_balance_allowance(BalanceAllowanceParams(
        asset_type=AssetType.CONDITIONAL,
        token_id=NO,
    ))


if __name__ == "__main__":
    main()
