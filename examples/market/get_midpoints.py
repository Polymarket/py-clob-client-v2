import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient, BookParams

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

    midpoints = client.get_midpoints([
        BookParams(token_id=YES),
        BookParams(token_id=NO),
    ])
    print(midpoints)


if __name__ == "__main__":
    main()
