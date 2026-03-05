import base64
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import httpx
from dotenv import load_dotenv
from eth_account import Account
from eth_account.messages import encode_defunct
from web3 import Web3
from web3.middleware import ExtraDataToPOAMiddleware

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    AssetType,
    BalanceAllowanceParams,
    BuilderConfig,
    BuilderTradeParams,
    OrderArgsV2,
    OrderType,
    PartialCreateOrderOptions,
)
from py_clob_client_v2.constants import AMOY, POLYGON

load_dotenv()

AMOY_CONTRACTS = {
    "collateral": "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
    "conditionalTokens": "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
    "exchangeV2": "0xF60CA007115A47A11295F053156d913D83fed095",
    "negRiskAdapter": "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
    "negRiskExchangeV2": "0x93f0A57b6F7D1e765cA2674ab2Ecb6Ff6406B3C3",
}

ERC20_ABI = [
    {
        "name": "balanceOf",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "allowance",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}, {"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
    },
    {
        "name": "approve",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}, {"name": "", "type": "uint256"}],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
    {
        "name": "mint",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}, {"name": "", "type": "uint256"}],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
    },
]

CTF_ABI = [
    {
        "name": "isApprovedForAll",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}, {"name": "", "type": "address"}],
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
    },
    {
        "name": "setApprovalForAll",
        "type": "function",
        "inputs": [{"name": "", "type": "address"}, {"name": "", "type": "bool"}],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
]

WRAPPER_ABI = [
    {
        "name": "wrap",
        "type": "function",
        "inputs": [
            {"name": "from", "type": "address"},
            {"name": "to", "type": "address"},
            {"name": "amount", "type": "uint256"},
        ],
        "outputs": [],
        "stateMutability": "nonpayable",
    },
]


def _env(name: str) -> str:
    v = os.getenv(name)
    if not v:
        print(f"FATAL: Missing env var {name}", file=sys.stderr)
        sys.exit(1)
    return v


RPC_URL = _env("RPC_URL")
CLOB_API_URL = _env("CLOB_API_URL")
CLOB_AUTH_URL = _env("CLOB_AUTH_URL")
GAMMA_API_URL = _env("GAMMA_API_URL")
BALANCE_UPDATER_URL = os.getenv("BALANCE_UPDATER_URL", "")
BUILDER_SERVICE_URL = os.getenv("BUILDER_SERVICE_URL", "")
DOMAIN = os.getenv("DOMAIN", "polymarket.com")
CHAIN_ID = POLYGON
CONDITION_ID = os.getenv(
    "CONDITION_ID",
    "0xbd5e4a45c3d9db4acae940913ec32a89fb6402c0475170e58b90fb499b73d7af",
)
YES_TOKEN_ID = os.getenv(
    "YES_TOKEN_ID",
    "102200530570339469387764365697342150521708074903735836831685780223982723092914",
)
NO_TOKEN_ID = os.getenv(
    "NO_TOKEN_ID",
    "15871154585880608648532107628464183779895785213830018178010423617714102767076",
)
BUILDER_MAKER_FEE_BPS = int(os.getenv("BUILDER_MAKER_FEE_BPS", "50"))
BUILDER_TAKER_FEE_BPS = int(os.getenv("BUILDER_TAKER_FEE_BPS", "200"))
FALLBACK_PRICE = float(os.getenv("ORDER_PRICE", "0.5"))
ORDER_SIZE = float(os.getenv("ORDER_SIZE", "100"))
COLLATERAL_TOKEN_ADDRESS = _env("COLLATERAL_TOKEN_ADDRESS")
WRAPPER_ADDRESS = _env("WRAPPER_ADDRESS")

MIN_COLLATERAL = 9 * 10**6
WRAP_AMOUNT = 9 * 10**6
MAX_UINT256 = 2**256 - 1
GAS_PRICE = Web3.to_wei(200, "gwei")
GAS_LIMIT = 500_000

_any_key_freshly_created = False


def log(step: str, msg: str, data=None):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"\n[{ts}] [{step}] {msg}")
    if data is not None:
        print(data if isinstance(data, str) else json.dumps(data, indent=2, default=str))


def _build_tx(w3: Web3, from_addr: str, **kwargs) -> dict:
    gas_price = int(w3.eth.gas_price * 1.3)  # 30% buffer over current network price
    return {
        "from": from_addr,
        "nonce": w3.eth.get_transaction_count(from_addr, "pending"),
        "gasPrice": gas_price,
        "gas": GAS_LIMIT,
        **kwargs,
    }


def _send_tx(w3: Web3, private_key: str, tx: dict):
    signed = Account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)


def gamma_login(private_key: str) -> str:
    account = Account.from_key(private_key)
    address = account.address

    with httpx.Client() as client:
        nonce_res = client.get(f"{GAMMA_API_URL}/nonce")
        nonce_res.raise_for_status()
        nonce = nonce_res.json()["nonce"]
        nonce_cookie = nonce_res.headers.get("set-cookie", "").split(";")[0]

        issued_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        expiration = (
            (datetime.now(timezone.utc) + timedelta(days=7))
            .isoformat()
            .replace("+00:00", "Z")
        )

        siwe_text = "\n".join([
            f"{DOMAIN} wants you to sign in with your Ethereum account:",
            address,
            "",
            "Welcome to Polymarket! Sign to connect.",
            "",
            f"URI: https://{DOMAIN}",
            "Version: 1",
            "Chain ID: 137",
            f"Nonce: {nonce}",
            f"Issued At: {issued_at}",
            f"Expiration Time: {expiration}",
        ])

        msg = encode_defunct(text=siwe_text)
        signed_msg = account.sign_message(msg)
        signature = "0x" + signed_msg.signature.hex()

        json_payload = json.dumps(
            {
                "domain": DOMAIN,
                "address": address,
                "statement": "Welcome to Polymarket! Sign to connect.",
                "uri": f"https://{DOMAIN}",
                "version": "1",
                "chainId": 137,
                "nonce": nonce,
                "issuedAt": issued_at,
                "expirationTime": expiration,
            },
            separators=(",", ":"),
        )
        auth_token = base64.b64encode(
            f"{json_payload}:::{signature}".encode()
        ).decode()

        login_res = client.get(
            f"{GAMMA_API_URL}/login",
            headers={
                "Authorization": f"Bearer {auth_token}",
                "Cookie": nonce_cookie,
            },
        )
        if not login_res.is_success:
            raise RuntimeError(f"/login {login_res.status_code}: {login_res.text}")

    return auth_token


def gamma_api(method: str, path: str, auth_token: str, body=None) -> dict:
    with httpx.Client() as client:
        kwargs = {
            "headers": {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {auth_token}",
            }
        }
        if body is not None:
            kwargs["content"] = json.dumps(body, separators=(",", ":")).encode()

        res = getattr(client, method.lower())(f"{GAMMA_API_URL}{path}", **kwargs)
        try:
            parsed = res.json()
        except Exception:
            parsed = None
        return {"status": res.status_code, "json": parsed, "text": res.text}


def ensure_collateral(w3: Web3, private_key: str, label: str):
    account = Account.from_key(private_key)
    address = account.address

    pmct = w3.eth.contract(
        address=Web3.to_checksum_address(COLLATERAL_TOKEN_ADDRESS), abi=ERC20_ABI
    )
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(AMOY_CONTRACTS["collateral"]), abi=ERC20_ABI
    )
    wrapper = w3.eth.contract(
        address=Web3.to_checksum_address(WRAPPER_ADDRESS), abi=WRAPPER_ABI
    )

    pmct_bal = pmct.functions.balanceOf(address).call()
    log(label, f"PMCT balance: {pmct_bal / 10**6:.6f}")
    if pmct_bal >= MIN_COLLATERAL:
        return

    needed = WRAP_AMOUNT - pmct_bal  # how much more PMCT we need
    usdc_bal = usdc.functions.balanceOf(address).call()
    log(label, f"USDC balance: {usdc_bal / 10**6:.6f}")
    to_wrap = min(needed, usdc_bal)
    if to_wrap <= 0:
        raise RuntimeError(f"{label}: no USDC available to wrap")

    wrapper_allow = usdc.functions.allowance(
        address, Web3.to_checksum_address(WRAPPER_ADDRESS)
    ).call()
    if wrapper_allow < to_wrap:
        log(label, f"Approving USDC -> Wrapper ...")
        tx = usdc.functions.approve(
            Web3.to_checksum_address(WRAPPER_ADDRESS), MAX_UINT256
        ).build_transaction(_build_tx(w3, address))
        _send_tx(w3, private_key, tx)

    log(label, f"Wrapping {to_wrap / 10**6:.2f} USDC -> PMCT ...")
    tx = wrapper.functions.wrap(
        Web3.to_checksum_address(AMOY_CONTRACTS["collateral"]),
        address,
        to_wrap,
    ).build_transaction(_build_tx(w3, address))
    _send_tx(w3, private_key, tx)

    new_bal = pmct.functions.balanceOf(address).call()
    log(label, f"PMCT balance after wrap: {new_bal / 10**6:.6f}")


def ensure_approvals(w3: Web3, private_key: str, label: str):
    account = Account.from_key(private_key)
    address = account.address

    pmct = w3.eth.contract(
        address=Web3.to_checksum_address(COLLATERAL_TOKEN_ADDRESS), abi=ERC20_ABI
    )
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(AMOY_CONTRACTS["conditionalTokens"]),
        abi=CTF_ABI,
    )

    erc20_spenders = [
        (AMOY_CONTRACTS["conditionalTokens"], "CTF"),
        (AMOY_CONTRACTS["exchangeV2"], "ExchangeV2"),
        (AMOY_CONTRACTS["negRiskAdapter"], "NegRiskAdapter"),
        (AMOY_CONTRACTS["negRiskExchangeV2"], "NegRiskExchangeV2"),
    ]
    for spender_addr, name in erc20_spenders:
        checksum = Web3.to_checksum_address(spender_addr)
        allow = pmct.functions.allowance(address, checksum).call()
        if allow == 0:
            log(label, f"Approving PMCT -> {name} ...")
            tx = pmct.functions.approve(checksum, MAX_UINT256).build_transaction(
                _build_tx(w3, address)
            )
            _send_tx(w3, private_key, tx)

    ctf_operators = [
        (AMOY_CONTRACTS["exchangeV2"], "ExchangeV2"),
        (AMOY_CONTRACTS["negRiskAdapter"], "NegRiskAdapter"),
        (AMOY_CONTRACTS["negRiskExchangeV2"], "NegRiskExchangeV2"),
    ]
    for operator_addr, name in ctf_operators:
        checksum = Web3.to_checksum_address(operator_addr)
        approved = ctf.functions.isApprovedForAll(address, checksum).call()
        if not approved:
            log(label, f"CTF setApprovalForAll -> {name} ...")
            tx = ctf.functions.setApprovalForAll(checksum, True).build_transaction(
                _build_tx(w3, address)
            )
            _send_tx(w3, private_key, tx)


def init_clob_client(
    key: str,
    label: str,
    builder_code: Optional[str] = None,
) -> Tuple[ClobClient, ApiCreds]:
    global _any_key_freshly_created

    auth_client = ClobClient(host=CLOB_AUTH_URL, chain_id=CHAIN_ID, key=key)
    try:
        creds = auth_client.derive_api_key()
        if creds and creds.api_key:
            log(label, f"Derived API key: {creds.api_key}")
        else:
            raise ValueError("empty key")
    except Exception:
        creds = auth_client.create_api_key()
        log(label, f"Created API key: {creds.api_key}")
        _any_key_freshly_created = True

    builder_cfg = (
        BuilderConfig(builder_address="", builder_code=builder_code)
        if builder_code
        else None
    )
    client = ClobClient(
        host=CLOB_API_URL,
        chain_id=CHAIN_ID,
        key=key,
        creds=creds,
        builder_config=builder_cfg,
    )
    return client, creds


def main():
    global _any_key_freshly_created

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    builder_key = _env("BUILDER_PK")
    user_a_key = _env("USER_A_PK")
    user_b_key = _env("USER_B_PK")

    builder_addr = Account.from_key(builder_key).address
    user_a_addr = Account.from_key(user_a_key).address
    user_b_addr = Account.from_key(user_b_key).address

    log("INIT", f"Builder : {builder_addr}")
    log("INIT", f"User A  : {user_a_addr} (maker)")
    log("INIT", f"User B  : {user_b_addr} (taker)")
    log("INIT", f"CLOB    : {CLOB_API_URL} | Auth: {CLOB_AUTH_URL}")

    # STEP 1 — Builder profile + fees on Gamma
    log("STEP 1", "Builder profile setup (Gamma)")
    auth_token = gamma_login(builder_key)
    addr_lower = builder_addr.lower()
    gamma_api(
        "POST",
        "/profiles",
        auth_token,
        {
            "name": f"builder-{addr_lower[2:10]}-{int(time.time() * 1000)}",
            "confirmed": True,
            "users": [{"address": addr_lower, "proxyWallet": addr_lower}],
        },
    )

    builder_name = "e2ebuilder" + hex(int(time.time() * 1000))[2:10]
    bp_res = gamma_api("POST", "/builder-profiles", auth_token, {"name": builder_name})

    builder_profile_id = None
    builder_code = None

    if bp_res["status"] == 201:
        builder_profile_id = bp_res["json"]["id"]
        bc = bp_res["json"].get("builderCode")
        builder_code = bc.get("code") if isinstance(bc, dict) else bc
        log("STEP 1", "Builder profile created", bp_res["json"])
    else:
        log("STEP 1", f"Creation returned {bp_res['status']} — looking for existing profile")
        existing = gamma_api("GET", "/builder-profiles", auth_token)
        profiles = (
            existing["json"]
            if isinstance(existing["json"], list)
            else [existing["json"]]
        )
        if profiles and profiles[0] and profiles[0].get("id"):
            builder_profile_id = profiles[0]["id"]
            bc = profiles[0].get("builderCode")
            builder_code = bc.get("code") if isinstance(bc, dict) else bc
            log("STEP 1", "Using existing builder profile", profiles[0])
        else:
            raise RuntimeError("Could not create or find builder profile")

    log("STEP 1", f"Profile ID: {builder_profile_id}  Builder Code: {builder_code}")
    log("STEP 1", f"Setting fees: maker={BUILDER_MAKER_FEE_BPS}bps taker={BUILDER_TAKER_FEE_BPS}bps")

    fee_res = gamma_api(
        "PUT",
        f"/builder-profiles/{builder_profile_id}/fees",
        auth_token,
        {
            "takerFeeRateBps": BUILDER_TAKER_FEE_BPS,
            "makerFeeRateBps": BUILDER_MAKER_FEE_BPS,
        },
    )
    if fee_res["status"] == 200:
        log("STEP 1", "Fees applied", fee_res["json"])
    elif fee_res["status"] == 422:
        log("STEP 1", "Fee update rejected (cooldown) — existing fees in effect")
    else:
        log("STEP 1", f"Fee update returned {fee_res['status']}", fee_res["json"])

    if not builder_code:
        raise RuntimeError("builderCode is empty — cannot continue")

    # STEP 2 — CLOB clients + builder API key
    log("STEP 2", "CLOB client setup")
    _, builder_creds = init_clob_client(builder_key, "STEP 2 (Builder)", builder_code)
    # builder_code = None
    user_a_client, user_a_creds = init_clob_client(user_a_key, "STEP 2 (User A)", builder_code)
    user_b_client, user_b_creds = init_clob_client(user_b_key, "STEP 2 (User B)", builder_code)

    if _any_key_freshly_created:
        cooldown = int(os.getenv("API_KEY_COOLDOWN_SEC", "30"))
        log("STEP 2", f"Waiting {cooldown}s for API key cooldown ...")
        time.sleep(cooldown)

    builder_cfg = BuilderConfig(builder_address=builder_addr, builder_code=builder_code)
    builder_auth_client = ClobClient(
        host=CLOB_AUTH_URL,
        chain_id=CHAIN_ID,
        key=builder_key,
        creds=builder_creds,
        builder_config=builder_cfg,
    )
    try:
        keys = builder_auth_client.get_builder_api_keys()
        key_list = keys if isinstance(keys, list) else []
        if not key_list:
            bak = builder_auth_client.create_builder_api_key()
            log("STEP 2", "Builder API key created", bak)
    except Exception as e:
        log("STEP 2", f"Builder API key check/create: {e}")

    # STEP 3 — Fund both users with PMCT + approvals
    log("STEP 3", "Funding")
    ensure_collateral(w3, user_a_key, "STEP 3 (User A)")
    ensure_approvals(w3, user_a_key, "STEP 3 (User A)")
    ensure_collateral(w3, user_b_key, "STEP 3 (User B)")
    ensure_approvals(w3, user_b_key, "STEP 3 (User B)")

    if BALANCE_UPDATER_URL:
        for key, creds, label in [
            (user_a_key, user_a_creds, "User A"),
            (user_b_key, user_b_creds, "User B"),
        ]:
            bal_client = ClobClient(
                host=BALANCE_UPDATER_URL,
                chain_id=CHAIN_ID,
                key=key,
                creds=creds,
            )
            try:
                bal_client.update_balance_allowance(
                    BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
                )
                log("STEP 3", f"{label} balance updated")
            except Exception as e:
                log("STEP 3", f"{label} balance update failed: {e}")

    # STEP 4 — Fetch orderbook, derive prices
    log("STEP 4", "Orderbook state")
    tick_size = "0.01"
    neg_risk = False
    try:
        yes_book = user_a_client.get_order_book(YES_TOKEN_ID)
        if yes_book and yes_book.get("tick_size"):
            tick_size = yes_book["tick_size"]
        if yes_book and yes_book.get("neg_risk") is not None:
            neg_risk = yes_book["neg_risk"]
    except Exception as e:
        log("STEP 4", f"YES orderbook fetch failed: {e}")

    try:
        user_a_client.get_order_book(NO_TOKEN_ID)
    except Exception as e:
        log("STEP 4", f"NO orderbook fetch failed: {e}")

    yes_mid = None
    try:
        resp = user_a_client.get_midpoint(YES_TOKEN_ID)
        yes_mid = float(resp.get("mid") if isinstance(resp, dict) else resp)
    except Exception:
        pass

    tick_num = float(tick_size)
    if yes_mid and tick_num < yes_mid < 1 - tick_num:
        yes_price = round(round(yes_mid / tick_num) * tick_num, 4)
    else:
        yes_price = FALLBACK_PRICE

    no_price = round(1 - yes_price, 4)
    log("STEP 4", f"YES @ {yes_price} | NO @ {no_price} | tickSize={tick_size} negRisk={neg_risk}")

    # STEP 5 — User A: BUY YES (maker, resting GTC)
    log("STEP 5", "Maker order — User A buys YES")
    try:
        user_a_client.cancel_all()
    except Exception:
        pass

    maker_signed = user_a_client.create_order(
        OrderArgsV2(
            token_id=YES_TOKEN_ID,
            price=yes_price,
            size=ORDER_SIZE,
            side="BUY",
            # builder_code=builder_code,
        ),
        PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk),
    )
    maker_resp = user_a_client.post_order(maker_signed, OrderType.GTC)
    if not maker_resp or (
        not maker_resp.get("orderID") and not maker_resp.get("success")
    ):
        raise RuntimeError(f"Maker order failed: {json.dumps(maker_resp, default=str)}")

    log("STEP 5", f"Maker order ID: {maker_resp.get('orderID')}")
    time.sleep(3)

    # STEP 6 — User B: BUY NO -> matches maker
    log("STEP 6", "Taker order — User B buys NO")
    try:
        user_b_client.cancel_all()
    except Exception:
        pass

    taker_signed = user_b_client.create_order(
        OrderArgsV2(
            token_id=NO_TOKEN_ID,
            price=no_price,
            size=ORDER_SIZE,
            side="BUY",
            # builder_code=builder_code,
        ),
        PartialCreateOrderOptions(tick_size=tick_size, neg_risk=neg_risk),
    )
    taker_resp = user_b_client.post_order(taker_signed, OrderType.GTC)
    log("STEP 6", f"Taker order ID: {taker_resp.get('orderID') if taker_resp else None}")

    # Summary
    log(
        "DONE",
        "\n".join([
            f"Builder : {builder_addr}  code={builder_code}",
            f"User A (maker) : {user_a_addr}  order={maker_resp.get('orderID')}",
            f"User B (taker) : {user_b_addr}  order={taker_resp.get('orderID') if taker_resp else None}",
            f"Market : {CONDITION_ID}",
            f"YES @ {yes_price} / NO @ {no_price} / size={ORDER_SIZE}",
            f"Fees   : maker={BUILDER_MAKER_FEE_BPS}bps  taker={BUILDER_TAKER_FEE_BPS}bps",
        ]),
    )

    # STEP 7 — Query builder trades
    log("STEP 7", "Fetching builder trades")
    try:
        result = user_a_client.get_builder_trades(
            BuilderTradeParams(builder_code=builder_code)
        )
        log("STEP 7", f"Builder trades ({result['count']} total)", result)
    except Exception as e:
        log("STEP 7", f"Builder trades fetch failed: {e}")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"\n\nFATAL: {e}", file=sys.stderr)
        raise
