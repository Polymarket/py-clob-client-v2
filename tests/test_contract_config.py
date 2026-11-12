import unittest
from unittest.mock import patch

from eth_account import Account
from eth_account.messages import encode_typed_data

from py_clob_client_v2 import OrderArgs, PartialCreateOrderOptions
from py_clob_client_v2.config import get_contract_config
from py_clob_client_v2.order_utils.exchange_order_builder_v2 import ExchangeOrderBuilderV2
from tests.test_client_post_order_resolution import _make_client


EXCHANGE_V3 = "0xe3333700cA9d93003F00f0F71f8515005F6c00Aa"
POSITION_MANAGER = "0x006F54F7f9A22e0000CC2AB60031000000ae9fEF"


class TestContractConfig(unittest.TestCase):
    def test_position_manager_proxy_on_supported_chains(self):
        for chain_id in (137, 80002):
            with self.subTest(chain_id=chain_id):
                self.assertEqual(
                    get_contract_config(chain_id).position_manager, POSITION_MANAGER
                )

    def test_amoy_position_order_recovers_under_deployed_v3_domain(self):
        client = _make_client()
        with patch.object(client, "get_version", return_value=2), patch.object(
            client, "get_tick_size", return_value="0.01"
        ), patch.object(client, "_get", side_effect=AssertionError("unexpected request")):
            signed = client.create_order(
                OrderArgs(position_id="456", price=0.5, size=10, side="SELL"),
                PartialCreateOrderOptions(tick_size="0.01"),
            )

        # Pin the deployment independently of the SDK configuration used to sign.
        typed = ExchangeOrderBuilderV2(
            EXCHANGE_V3, 80002, client.signer, domain_version="3"
        ).build_order_typed_data(signed)
        self.assertEqual(
            Account.recover_message(
                encode_typed_data(full_message=typed), signature=signed.signature
            ),
            client.signer.address(),
        )
