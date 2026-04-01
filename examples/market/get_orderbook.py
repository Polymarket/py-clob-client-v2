import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient

load_dotenv()

YES = "71321045679252212594626385532706912750332728571942532289631379312455583992563"


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    orderbook = client.get_order_book(YES)
    print("orderbook", orderbook)

    hash_ = client.get_order_book_hash(orderbook)
    print("orderbook hash", hash_)


if __name__ == "__main__":
    main()
