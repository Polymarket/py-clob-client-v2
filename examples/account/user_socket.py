import os
import json
import threading
import websocket
from dotenv import load_dotenv

load_dotenv()

CONDITION_ID = os.environ.get(
    "CONDITION_ID",
    "0x5f65177b394277fd294cd75650044e32ba009a95022d88a0c1d565897d72f8f1",
)


def main():
    host = os.environ.get("WS_URL", "ws://localhost:8081")
    url = f"{host}/ws/user"
    print(url)

    subscription_message = {
        "auth": {
            "apiKey": os.environ["CLOB_API_KEY"],
            "secret": os.environ["CLOB_SECRET"],
            "passphrase": os.environ["CLOB_PASS_PHRASE"],
        },
        "type": "user",
        "markets": [CONDITION_ID],
        "assets_ids": [],
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
