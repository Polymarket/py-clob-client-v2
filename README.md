# PY Polymarket CLOB Client V2

Python client for the Polymarket CLOB (v2)

### Usage

```python
# pip install py_clob_client_v2

import os
from py_clob_client_v2 import ApiCreds, ClobClient, OrderArgs, OrderType, PartialCreateOrderOptions, Side

host = "<polymarket-clob-host>"
chain_id = 137  # or 80002 for Amoy testnet

# Step 1: obtain API credentials using your wallet (L1 auth)
client = ClobClient(host=host, chain_id=chain_id, key=os.environ["PK"])
creds = client.create_or_derive_api_key()

# Step 2: initialize a fully-authenticated client (L1 + L2)
client = ClobClient(host=host, chain_id=chain_id, key=os.environ["PK"], creds=creds)

# Place a resting limit buy (GTC)
resp = client.create_and_post_order(
    order_args=OrderArgs(
        token_id="",  # token ID of the market outcome — get from https://docs.polymarket.com
        price=0.4,
        side=Side.BUY,
        size=100,
    ),
    options=PartialCreateOrderOptions(tick_size="0.01"),
    order_type=OrderType.GTC,
)
print(resp)
```

See [examples](examples/) for more information.

### Market Orders

```python
from py_clob_client_v2 import MarketOrderArgs

# Market buy — amount is in USDC
# OrderType.FOK: entire order must fill immediately or it is cancelled
# OrderType.FAK: fills as much as possible, remainder is cancelled
resp = client.create_and_post_market_order(
    order_args=MarketOrderArgs(
        token_id="",
        amount=100,  # USDC
        side=Side.BUY,
        order_type=OrderType.FOK,
    ),
    options=PartialCreateOrderOptions(tick_size="0.01"),
    order_type=OrderType.FOK,
)
print(resp)
```

### Authentication

The client has two authentication levels:

**L1** — wallet signature (EIP-712). Required to create or derive API keys.

```python
client = ClobClient(host=host, chain_id=chain_id, key=os.environ["PK"])
creds = client.create_or_derive_api_key()
```

**L2** — HMAC with API credentials. Required for order placement, cancellation, and account data.

```python
creds = ApiCreds(
    api_key=os.environ["CLOB_API_KEY"],
    api_secret=os.environ["CLOB_SECRET"],
    api_passphrase=os.environ["CLOB_PASS_PHRASE"],
)
client = ClobClient(host=host, chain_id=chain_id, key=os.environ["PK"], creds=creds)
```
