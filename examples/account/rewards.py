import os
from dotenv import load_dotenv
from eth_account import Account

from py_clob_client_v2 import ClobClient, ApiCreds

load_dotenv()

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

    print("today earnings", client.get_earnings_for_user_for_day("2024-04-09"))  # UTC date
    print("total earnings", client.get_total_earnings_for_user_for_day("2024-04-09"))
    print("rewards percentages", client.get_reward_percentages())
    print("current rewards", client.get_current_rewards())
    print("rewards for market", client.get_raw_rewards_for_market(
        CONDITION_ID,
    ))
    print("rewards", client.get_user_earnings_and_markets_config(
        "2025-01-31",  # UTC date
        "earnings",
        "DESC",
        True,
    ))


if __name__ == "__main__":
    main()
