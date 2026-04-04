from .clob_types import ContractConfig

COLLATERAL_TOKEN_DECIMALS = 6
CONDITIONAL_TOKEN_DECIMALS = 6


def get_contract_config(chain_id: int) -> ContractConfig:
    """
    Get the contract configuration for the given chain.
    """
    CONFIG = {
        137: ContractConfig(
            exchange="0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
            neg_risk_adapter="0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
            neg_risk_exchange="0xC5d563A36AE78145C45a50134d48A1215220f80a",
            collateral="0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB",
            conditional_tokens="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
            exchange_v2="0xE111180000d2663C0091e4f400237545B87B996B",
            neg_risk_exchange_v2="0xe2222d279d744050d28e00520010520000310F59",
        ),
        80002: ContractConfig(
            exchange="0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40",
            neg_risk_adapter="0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
            neg_risk_exchange="0xC5d563A36AE78145C45a50134d48A1215220f80a",
            collateral="0xC011a7E12a19f7B1f670d46F03B03f3342E82DFB",
            conditional_tokens="0x69308FB512518e39F9b16112fA8d994F4e2Bf8bB",
            exchange_v2="0xE111180000d2663C0091e4f400237545B87B996B",
            neg_risk_exchange_v2="0xe2222d279d744050d28e00520010520000310F59",
        ),
    }

    config = CONFIG.get(chain_id)
    if config is None:
        raise Exception("Invalid chain_id: {}".format(chain_id))

    return config
