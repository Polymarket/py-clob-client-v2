import os
import time
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient, PricesHistoryParams, PriceHistoryInterval

load_dotenv()

YES = os.environ.get(
    "YES_TOKEN_ID",
    "78433024518676680431174478322854148606578065650008220678402966840627347604025",
)
NO = os.environ.get(
    "NO_TOKEN_ID",
    "50346565575310273995396997144874891836871065259829083228393044602519086496922",
)


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    now = int(time.time())

    # By time range
    print(client.get_prices_history(PricesHistoryParams(
        market=YES, start_ts=now - 1000, end_ts=now,
    )))
    print(client.get_prices_history(PricesHistoryParams(
        market=NO, start_ts=now - 1000, end_ts=now,
    )))

    # By interval
    print(client.get_prices_history(PricesHistoryParams(
        market=YES, interval=PriceHistoryInterval.ONE_HOUR, fidelity=1,
    )))
    print(client.get_prices_history(PricesHistoryParams(
        market=YES, interval=PriceHistoryInterval.SIX_HOURS, fidelity=3,
    )))
    print(client.get_prices_history(PricesHistoryParams(
        market=YES, interval=PriceHistoryInterval.ONE_DAY, fidelity=5,
    )))
    print(client.get_prices_history(PricesHistoryParams(
        market=YES, interval=PriceHistoryInterval.ONE_WEEK, fidelity=10,
    )))


if __name__ == "__main__":
    main()
