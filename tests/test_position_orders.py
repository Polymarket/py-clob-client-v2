import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from eth_account import Account
from eth_account.messages import encode_typed_data

from py_clob_client_v2 import (
    OrderArgs,
    MarketOrderArgs,
    PartialCreateOrderOptions,
    Side,
)
from py_clob_client_v2.clob_types import CreateOrderOptions, FeeInfo, OrderType
from py_clob_client_v2.config import get_contract_config
from py_clob_client_v2.order_utils.exchange_order_builder_v2 import (
    ExchangeOrderBuilderV2,
)
from tests.test_client_post_order_resolution import _make_client

POSITION_ID = "456"


class TestPositionOrderInputs(unittest.TestCase):
    def test_preserves_positional_token_constructors_and_replace(self):
        limit = OrderArgs("123", 0.5, 10, "BUY", 123)
        market = MarketOrderArgs("123", 5, "SELL", 0.5, OrderType.FAK)
        self.assertEqual(limit.expiration, 123)
        self.assertEqual(market.order_type, OrderType.FAK)
        self.assertEqual(replace(limit, size=20).token_id, "123")
        self.assertEqual(replace(market, amount=10).amount, 10)

    def test_position_inputs_preserve_dataclass_behavior(self):
        order = OrderArgs(position_id=POSITION_ID, price=0.5, size=10, side="BUY")
        self.assertIsNone(order.token_id)
        self.assertEqual(replace(order, size=20).position_id, POSITION_ID)
        self.assertEqual(order, replace(order))

    def test_rejects_missing_ambiguous_and_empty_identifiers(self):
        for cls, params in [
            (OrderArgs, dict(price=0.5, size=10, side="BUY")),
            (MarketOrderArgs, dict(amount=5, side="BUY")),
        ]:
            for ids in (
                {},
                dict(token_id="123", position_id=POSITION_ID),
                dict(position_id=""),
                dict(token_id=" "),
            ):
                with self.subTest(cls=cls, ids=ids), self.assertRaises(ValueError):
                    cls(**params, **ids)

    def test_trade_fields_remain_required(self):
        for cls, params, required in [
            (
                OrderArgs,
                dict(price=0.5, size=10, side="BUY"),
                ("price", "size", "side"),
            ),
            (MarketOrderArgs, dict(amount=5, side="BUY"), ("amount", "side")),
        ]:
            for field in required:
                args = dict(params)
                del args[field]
                with self.subTest(cls=cls, field=field), self.assertRaisesRegex(
                    TypeError, field
                ):
                    cls(position_id=POSITION_ID, **args)


class TestPositionOrders(unittest.TestCase):
    def setUp(self):
        self.client = _make_client()
        self.client._ClobClient__tick_sizes[POSITION_ID] = "0.01"
        self.client._ClobClient__fee_infos[POSITION_ID] = FeeInfo(rate=0.25, exponent=2)
        self.options = PartialCreateOrderOptions(
            tick_size="0.01", neg_risk=True, version=1
        )

    def assert_v3_signature(self, signed):
        # Reconstruct the on-chain domain independently of routing and recover the EOA.
        builder = ExchangeOrderBuilderV2(
            get_contract_config(self.client.chain_id).exchange_v3,
            self.client.chain_id,
            self.client.signer,
        )
        typed = builder.build_order_typed_data(signed)
        typed["domain"]["version"] = "3"
        self.assertEqual(
            Account.recover_message(
                encode_typed_data(full_message=typed), signature=signed.signature
            ),
            self.client.signer.address(),
        )
        self.assertEqual(signed.tokenId, POSITION_ID)

    def test_public_limit_order_forces_v3_and_adjusts_balance(self):
        order = OrderArgs(
            position_id=POSITION_ID,
            price=0.5,
            size=100,
            side=Side.BUY,
            user_usdc_balance=50,
        )
        with patch.object(self.client, "get_version") as version, patch.object(
            self.client, "get_neg_risk"
        ) as neg_risk:
            signed = self.client.create_order(order, self.options)
        version.assert_not_called()
        neg_risk.assert_not_called()
        self.assert_v3_signature(signed)
        self.assertEqual(signed.makerAmount, "48435000")
        self.assertEqual(order.size, 100)

    def test_public_market_order_uses_position_for_book_and_fees(self):
        order = MarketOrderArgs(
            position_id=POSITION_ID, amount=50, side="BUY", user_usdc_balance=50
        )
        with patch.object(
            self.client, "calculate_market_price", return_value=0.5
        ) as price, patch.object(self.client, "get_version") as version, patch.object(
            self.client, "get_neg_risk"
        ) as neg_risk:
            signed = self.client.create_market_order(order, self.options)
        price.assert_called_once_with(POSITION_ID, "BUY", 50, OrderType.FOK)
        version.assert_not_called()
        neg_risk.assert_not_called()
        self.assert_v3_signature(signed)
        self.assertEqual(signed.makerAmount, "48430000")
        self.assertEqual(order.amount, 50)
        self.assertEqual(order.price, 0)

    def test_uncached_position_flows_through_metadata_and_tick_requests(self):
        self.client._ClobClient__fee_infos.clear()
        self.client._ClobClient__tick_sizes.clear()
        order = MarketOrderArgs(
            position_id=POSITION_ID, amount=5, side="SELL", price=0.5
        )

        def get(url, **kwargs):
            if url.endswith("/markets-by-token/456"):
                return {"condition_id": "condition"}
            if url.endswith("/clob-markets/condition"):
                return {"t": [{"t": POSITION_ID}], "mts": "0.01"}
            self.fail(f"unexpected request: {url}")

        with patch.object(self.client, "_get", side_effect=get) as request:
            signed = self.client.create_market_order(order)
        self.assertEqual(request.call_count, 2)
        self.assert_v3_signature(signed)

    def test_direct_builder_routes_both_order_types_to_v3(self):
        for order, method in [
            (
                OrderArgs(position_id=POSITION_ID, price=0.5, size=10, side="SELL"),
                self.client.builder.build_order,
            ),
            (
                MarketOrderArgs(
                    position_id=POSITION_ID, price=0.5, amount=10, side="SELL"
                ),
                self.client.builder.build_market_order,
            ),
        ]:
            for version in (1, 2, 3):
                with self.subTest(method=method, version=version):
                    signed = method(
                        order, CreateOrderOptions("0.01", True), version=version
                    )
                    self.assert_v3_signature(signed)

    def test_public_methods_still_accept_full_create_order_options(self):
        for asset in ({"token_id": POSITION_ID}, {"position_id": POSITION_ID}):
            for market in (False, True):
                with self.subTest(asset=asset, market=market):
                    order = (
                        MarketOrderArgs(**asset, amount=5, price=0.5, side="BUY")
                        if market
                        else OrderArgs(**asset, size=10, price=0.5, side="BUY")
                    )
                    method = (
                        self.client.create_market_order
                        if market
                        else self.client.create_order
                    )
                    with patch.object(self.client, "get_version", return_value=2):
                        signed = method(order, CreateOrderOptions("0.01", False))
                    self.assertEqual(signed.tokenId, POSITION_ID)
                    if "position_id" in asset:
                        self.assert_v3_signature(signed)

    def test_mutated_ambiguous_inputs_fail_before_requests(self):
        order = OrderArgs(position_id=POSITION_ID, price=0.5, size=10, side="BUY")
        order.token_id = "123"
        with patch.object(self.client, "_get") as get, self.assertRaises(ValueError):
            self.client.create_order(order)
        get.assert_not_called()

    def test_token_order_keeps_server_version_and_neg_risk(self):
        order = OrderArgs(POSITION_ID, 0.5, 10, "BUY")
        with patch.object(
            self.client, "get_version", return_value=1
        ) as version, patch.object(
            self.client, "get_neg_risk", return_value=True
        ) as neg, patch.object(
            self.client, "get_fee_rate_bps", return_value=0
        ):
            signed = self.client.create_order(order)
        version.assert_called_once()
        neg.assert_called_once_with(POSITION_ID)
        self.assertTrue(hasattr(signed, "feeRateBps"))

    def test_create_and_post_keeps_wire_token_id_and_v2_schema(self):
        for market in (False, True):
            with self.subTest(market=market):
                order = (
                    MarketOrderArgs(
                        position_id=POSITION_ID, amount=5, price=0.5, side="BUY"
                    )
                    if market
                    else OrderArgs(
                        position_id=POSITION_ID, size=10, price=0.5, side="BUY"
                    )
                )
                method = (
                    self.client.create_and_post_market_order
                    if market
                    else self.client.create_and_post_order
                )
                with patch.object(
                    self.client, "get_version", return_value=2
                ), patch.object(
                    self.client, "_post", return_value={"success": True}
                ) as post:
                    self.assertEqual(method(order), {"success": True})
                payload = json.loads(post.call_args.kwargs["data"])["order"]
                self.assertEqual(payload["tokenId"], POSITION_ID)
                self.assertIn("timestamp", payload)
                self.assertNotIn("position_id", payload)
                self.assertNotIn("feeRateBps", payload)

    def test_deposit_wallet_signature_uses_v3_domain(self):
        self.client.builder.signature_type = 3
        self.client.builder.funder = "0x1111111111111111111111111111111111111111"
        signed = self.client.create_order(
            OrderArgs(position_id=POSITION_ID, size=10, price=0.5, side="BUY")
        )
        typed = ExchangeOrderBuilderV2(
            get_contract_config(self.client.chain_id).exchange_v3,
            self.client.chain_id,
            self.client.signer,
        ).build_order_typed_data(signed)
        typed["domain"]["version"] = "3"
        domain_separator = encode_typed_data(full_message=typed).header
        signature = bytes.fromhex(signed.signature[2:])
        self.assertEqual(signature[65:97], domain_separator)
        self.assertEqual(signed.signer, self.client.builder.funder)
        # Verify the nested ERC-7739 message using the generic EIP-712 encoder.
        nested = {
            "types": {
                **typed["types"],
                "TypedDataSign": [
                    {"name": "contents", "type": "Order"},
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                    {"name": "verifyingContract", "type": "address"},
                    {"name": "salt", "type": "bytes32"},
                ],
            },
            "primaryType": "TypedDataSign",
            "domain": typed["domain"],
            "message": {
                "contents": typed["message"],
                "name": "DepositWallet",
                "version": "1",
                "chainId": self.client.chain_id,
                "verifyingContract": signed.signer,
                "salt": bytes(32),
            },
        }
        self.assertEqual(
            Account.recover_message(
                encode_typed_data(full_message=nested), signature=signature[:65]
            ),
            self.client.signer.address(),
        )
