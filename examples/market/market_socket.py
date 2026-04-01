import os
import json
import threading
import websocket
from dotenv import load_dotenv

load_dotenv()

YES_TOKEN_ID = "71321045679252212594626385532706912750332728571942532289631379312455583992563"
NO_TOKEN_ID = "52114319501245915516055106046884209969926127482827954674443846427813813222426"


def main():
    host = os.environ.get("WS_URL", "ws://localhost:8081")
    url = f"{host}/ws/market"
    print(url)

    subscription_message = {
        "type": "market",
        "markets": [],
        "assets_ids": [NO_TOKEN_ID, YES_TOKEN_ID],
        "initial_dump": True,
    }

    def on_open(ws):
        ws.send(json.dumps(subscription_message))

        def ping():
            import time
            while True:
                time.sleep(50)
                print("PINGING")
                ws.send("PING")

        t = threading.Thread(target=ping, daemon=True)
        t.start()

    def on_message(ws, message):
        print(message)

    def on_error(ws, error):
        print("error SOCKET", error)

    def on_close(ws, code, reason):
        print(f"disconnected SOCKET code={code} reason={reason}")

    ws = websocket.WebSocketApp(
        url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close,
    )
    ws.run_forever()


if __name__ == "__main__":
    main()
