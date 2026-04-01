import os
from dotenv import load_dotenv
from web3 import Web3
from eth_account import Account

from py_clob_client_v2.config import get_contract_config
from examples.abi.usdc_abi import USDC_ABI
from examples.abi.ctf_abi import CTF_ABI

load_dotenv()

# NegRisk markets require separate allowances
# for the NegRiskCtfExchange and the NegRiskAdapter.

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

    usdc_allowance_neg_risk_adapter = usdc.functions.allowance(
        account.address, contract_config.neg_risk_adapter
    ).call()
    print(f"usdcAllowanceNegRiskAdapter: {usdc_allowance_neg_risk_adapter}")

    usdc_allowance_neg_risk_exchange = usdc.functions.allowance(
        account.address, contract_config.neg_risk_exchange
    ).call()

    ctf_allowance_neg_risk_exchange = ctf.functions.isApprovedForAll(
        account.address, contract_config.neg_risk_exchange
    ).call()

    ctf_allowance_neg_risk_adapter = ctf.functions.isApprovedForAll(
        account.address, contract_config.neg_risk_adapter
    ).call()

    nonce = w3.eth.get_transaction_count(account.address)

    # for splitting through the NegRiskAdapter
    if not usdc_allowance_neg_risk_adapter > 0:
        txn = usdc.functions.approve(
            contract_config.neg_risk_adapter, MAX_UINT256
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting USDC allowance for NegRiskAdapter: {tx_hash.hex()}")
        nonce += 1

    if not usdc_allowance_neg_risk_exchange > 0:
        txn = usdc.functions.approve(
            contract_config.neg_risk_exchange, MAX_UINT256
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting USDC allowance for NegRiskExchange: {tx_hash.hex()}")
        nonce += 1

    if not ctf_allowance_neg_risk_exchange:
        txn = ctf.functions.setApprovalForAll(
            contract_config.neg_risk_exchange, True
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting Conditional Tokens allowance for NegRiskExchange: {tx_hash.hex()}")
        nonce += 1

    if not ctf_allowance_neg_risk_adapter:
        txn = ctf.functions.setApprovalForAll(
            contract_config.neg_risk_adapter, True
        ).build_transaction({
            "from": account.address,
            "gasPrice": GAS_PRICE,
            "gas": GAS_LIMIT,
            "nonce": nonce,
        })
        signed = account.sign_transaction(txn)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Setting Conditional Tokens allowance for NegRiskAdapter: {tx_hash.hex()}")

    print("Allowances set")


if __name__ == "__main__":
    main()
