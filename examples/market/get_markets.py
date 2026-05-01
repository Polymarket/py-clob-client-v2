import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient

load_dotenv()

CONDITION_ID = os.environ.get(
    "CONDITION_ID",
    "0x384e2707bbb95da4bfa6f330fe7d5ccbec1c0a85e20be900cbf599987588e1a4",
)


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    print("market", client.get_market(CONDITION_ID))
    print("markets", client.get_markets())
    print("simplified markets", client.get_simplified_markets())
    print("sampling markets", client.get_sampling_markets())
    print("sampling simplified markets", client.get_sampling_simplified_markets())


if __name__ == "__main__":
    main()
