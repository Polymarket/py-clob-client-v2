import os
from dotenv import load_dotenv

from py_clob_client_v2 import ClobClient, BookParams

load_dotenv()

YES = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
NO = "52114319501245915516055106046884209969926127482827954674443846427813813222426"


def main():
    host = os.environ.get("CLOB_API_URL", "http://localhost:8080")
    chain_id = int(os.environ.get("CHAIN_ID", 80002))
    client = ClobClient(host=host, chain_id=chain_id)

    last_trades_prices = client.get_last_trades_prices([
        BookParams(token_id=YES),
        BookParams(token_id=NO),
    ])
    print(last_trades_prices)


if __name__ == "__main__":
    main()
