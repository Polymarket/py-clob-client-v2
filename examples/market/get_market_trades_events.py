import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient

load_dotenv()


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    print("events", client.get_market_trades_events("condition_id"))


if __name__ == "__main__":
    main()
