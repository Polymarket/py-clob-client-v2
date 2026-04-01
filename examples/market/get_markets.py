import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient

load_dotenv()


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    print("market", client.get_market("condition_id"))
    print("markets", client.get_markets())
    print("simplified markets", client.get_simplified_markets())
    print("sampling markets", client.get_sampling_markets())
    print("sampling simplified markets", client.get_sampling_simplified_markets())


if __name__ == "__main__":
    main()
