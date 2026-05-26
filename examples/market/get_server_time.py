import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient

load_dotenv()

def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    print(f"Server time: {client.get_server_time()}")


if __name__ == "__main__":
    main()
