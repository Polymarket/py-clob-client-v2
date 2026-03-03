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
            collateral="0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174",
            conditional_tokens="0x4D97DCd97eC945f40cF65F87097ACe5EA0476045",
            exchange_v2="0xF60CA007115A47A11295F053156d913D83fed095",
            neg_risk_exchange_v2="0x93f0A57b6F7D1e765cA2674ab2Ecb6Ff6406B3C3",
        ),
        80002: ContractConfig(
            exchange="0xdFE02Eb6733538f8Ea35D585af8DE5958AD99E40",
            neg_risk_adapter="0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
            neg_risk_exchange="0xC5d563A36AE78145C45a50134d48A1215220f80a",
            collateral="0x9c4e1703476e875070ee25b56a58b008cfb8fa78",
            conditional_tokens="0x69308FB512518e39F9b16112fA8d994F4e2Bf8bB",
            exchange_v2="0x4CAAb20932751c6b4c8C4EB0baB741824d5478Ac",
            neg_risk_exchange_v2="0xfa7B8Aa8bC85c805E532Ec54E4557f6A92730E4b",
        ),
    }

    config = CONFIG.get(chain_id)
    if config is None:
        raise Exception("Invalid chain_id: {}".format(chain_id))

    return config
