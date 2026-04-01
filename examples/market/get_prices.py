import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient, BookParams
from py_clob_client_v2 import Side

load_dotenv()

YES = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
NO = "52114319501245915516055106046884209969926127482827954674443846427813813222426"


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    prices = client.get_prices([
        BookParams(token_id=YES, side=Side.BUY),
        BookParams(token_id=YES, side=Side.SELL),
        BookParams(token_id=NO, side=Side.BUY),
        BookParams(token_id=NO, side=Side.SELL),
    ])
    print(prices)


if __name__ == "__main__":
    main()
