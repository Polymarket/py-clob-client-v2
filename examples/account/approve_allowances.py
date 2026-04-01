import os
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

from py_clob_client_v2.config import get_contract_config
from examples.abi.usdc_abi import USDC_ABI
from examples.abi.ctf_abi import CTF_ABI

load_dotenv()

# --------------------------
# SET MAINNET OR AMOY HERE
IS_MAINNET = False
# --------------------------

GAS_PRICE = 100_000_000_000
GAS_LIMIT = 200_000
MAX_UINT256 = 2**256 - 1


def get_web3(is_mainnet: bool) -> Web3:
    rpc_token = os.environ["RPC_TOKEN"]
    if is_mainnet:
        rpc_url = f"https://polygon-mainnet.g.alchemy.com/v2/{rpc_token}"
    else:
        rpc_url = f"https://polygon-amoy.g.alchemy.com/v2/{rpc_token}"
    return Web3(Web3.HTTPProvider(rpc_url))


def main():
    pk = os.environ["PK"]
    account = Account.from_key(pk)
    chain_id = 137 if IS_MAINNET else 80002
    print(f"Address: {account.address}, chainId: {chain_id}")

    w3 = get_web3(IS_MAINNET)
    contract_config = get_contract_config(chain_id)

    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(contract_config.collateral),
        abi=USDC_ABI,
    )
    ctf = w3.eth.contract(
        address=Web3.to_checksum_address(contract_config.conditional_tokens),
        abi=CTF_ABI,
    )

    print(f"usdc: {usdc.address}")
    print(f"ctf: {ctf.address}")

    usdc_allowance_ctf = usdc.functions.allowance(
        account.address, ctf.address
    ).call()
    print(f"usdcAllowanceCtf: {usdc_allowance_ctf}")

    usdc_allowance_exchange = usdc.functions.allowance(
        account.address, contract_config.exchange
    ).call()

    ctf_allowance_exchange = ctf.functions.isApprovedForAll(
        account.address, contract_config.exchange
    ).call()

    nonce = w3.eth.get_transaction_count(account.address)

    if not usdc_allowance_ctf > 0:
        txn = usdc.functions.approve(
            contract_config.conditional_tokens, MAX_UINT256
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting USDC allowance for CTF: {tx_hash.hex()}")
        nonce += 1

    if not usdc_allowance_exchange > 0:
        txn = usdc.functions.approve(
            contract_config.exchange, MAX_UINT256
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting USDC allowance for Exchange: {tx_hash.hex()}")
        nonce += 1

    if not ctf_allowance_exchange:
        txn = ctf.functions.setApprovalForAll(
            contract_config.exchange, True
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting Conditional Tokens allowance for Exchange: {tx_hash.hex()}")

    print("Allowances set")


if __name__ == "__main__":
    main()
