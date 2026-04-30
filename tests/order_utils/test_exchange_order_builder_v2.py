from unittest import TestCase

from py_clob_client_v2.config import get_contract_config
from py_clob_client_v2.constants import AMOY, BYTES32_ZERO
from py_clob_client_v2.order_utils.exchange_order_builder_v2 import (
    ORDER_TYPE_STRING,
    ExchangeOrderBuilderV2,
)
from py_clob_client_v2.order_utils.model.order_data_v2 import OrderDataV2
from py_clob_client_v2.order_utils.model.side import Side
from py_clob_client_v2.order_utils.model.signature_type_v2 import SignatureTypeV2
from py_clob_client_v2.signer import Signer

# Publicly known private key used by local Ethereum dev chains.
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
CHAIN_ID = AMOY
SIGNER = Signer(private_key=PRIVATE_KEY, chain_id=CHAIN_ID)
CONTRACT_CONFIG = get_contract_config(CHAIN_ID)

FIXED_SALT = "479249096354"
FIXED_TIMESTAMP = "1710000000000"
DEPOSIT_WALLET = "0x1111111111111111111111111111111111111111"

EXPECTED_POLY_1271_SIGNATURE = (
    "0xa3a093c83b6c20c83355c16ce94c92e6e9fcbdeb840618cc74f6c57a42ad145b"
    "2b98db73d2c73cbf1f2b6af288566ae81960ddbc3a13921027358a8bff3be6ff1c"
    "a440cbd865bc0c6243d7a8df9a8bf48a8827b0a4abbb61c30e96d305423af148"
    "d23d42d3ad94e65d78258cecaf8dcbaddac0f73dc085040f2c12bb595dd83804"
    "4f726465722875696e743235362073616c742c61646472657373206d616b65722c"
    "61646472657373207369676e65722c75696e7432353620746f6b656e49642c75"
    "696e74323536206d616b6572416d6f756e742c75696e743235362074616b6572"
    "416d6f756e742c75696e743820736964652c75696e7438207369676e61747572"
    "65547970652c75696e743235362074696d657374616d702c6279746573333220"
    "6d657461646174612c62797465733332206275696c6465722900ba"
)


def _poly_1271_order_data() -> OrderDataV2:
    return OrderDataV2(
        maker=DEPOSIT_WALLET,
        signer=DEPOSIT_WALLET,
        tokenId="1234",
        makerAmount="100000000",
        takerAmount="50000000",
        side=Side.BUY,
        signatureType=SignatureTypeV2.POLY_1271,
        timestamp=FIXED_TIMESTAMP,
        metadata=BYTES32_ZERO,
        builder=BYTES32_ZERO,
    )


class TestExchangeOrderBuilderV2CTF(TestCase):
    def setUp(self):
        self.builder = ExchangeOrderBuilderV2(
            CONTRACT_CONFIG.exchange_v2,
            CHAIN_ID,
            SIGNER,
            generate_salt=lambda: FIXED_SALT,
        )

    def test_build_order_poly_1271_allows_deposit_wallet_signer(self):
        order = self.builder.build_order(_poly_1271_order_data())

        self.assertEqual(order.salt, FIXED_SALT)
        self.assertEqual(order.maker, DEPOSIT_WALLET)
        self.assertEqual(order.signer, DEPOSIT_WALLET)
        self.assertEqual(order.tokenId, "1234")
        self.assertEqual(order.makerAmount, "100000000")
        self.assertEqual(order.takerAmount, "50000000")
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.signatureType, SignatureTypeV2.POLY_1271)
        self.assertEqual(order.timestamp, FIXED_TIMESTAMP)
        self.assertEqual(order.metadata, BYTES32_ZERO)
        self.assertEqual(order.builder, BYTES32_ZERO)
        self.assertEqual(order.expiration, "0")

    def test_build_order_eoa_rejects_mismatched_signer(self):
        order_data = _poly_1271_order_data()
        order_data.signatureType = SignatureTypeV2.EOA

        with self.assertRaises(ValueError):
            self.builder.build_order(order_data)

    def test_build_order_typed_data_poly_1271(self):
        order = self.builder.build_order(_poly_1271_order_data())
        typed_data = self.builder.build_order_typed_data(order)

        self.assertEqual(typed_data["primaryType"], "Order")
        self.assertEqual(typed_data["domain"]["name"], "Polymarket CTF Exchange")
        self.assertEqual(typed_data["domain"]["version"], "2")
        self.assertEqual(typed_data["domain"]["chainId"], CHAIN_ID)
        self.assertEqual(
            typed_data["domain"]["verifyingContract"],
            CONTRACT_CONFIG.exchange_v2,
        )
        self.assertEqual(
            typed_data["message"],
            {
                "salt": int(FIXED_SALT),
                "maker": DEPOSIT_WALLET,
                "signer": DEPOSIT_WALLET,
                "tokenId": 1234,
                "makerAmount": 100000000,
                "takerAmount": 50000000,
                "side": 0,
                "signatureType": 3,
                "timestamp": int(FIXED_TIMESTAMP),
                "metadata": bytes.fromhex(BYTES32_ZERO[2:]),
                "builder": bytes.fromhex(BYTES32_ZERO[2:]),
            },
        )

    def test_build_order_signature_poly_1271_matches_expected_signature(self):
        order = self.builder.build_order(_poly_1271_order_data())
        typed_data = self.builder.build_order_typed_data(order)
        signature = self.builder.build_order_signature(typed_data)

        expected_length = 2 + 130 + 64 + 64 + (len(ORDER_TYPE_STRING) * 2) + 4
        self.assertEqual(signature, EXPECTED_POLY_1271_SIGNATURE)
        self.assertEqual(len(signature), expected_length)

    def test_build_signed_order_poly_1271_matches_expected_signature(self):
        signed = self.builder.build_signed_order(_poly_1271_order_data())

        self.assertEqual(signed.maker, DEPOSIT_WALLET)
        self.assertEqual(signed.signer, DEPOSIT_WALLET)
        self.assertEqual(signed.signatureType, SignatureTypeV2.POLY_1271)
        self.assertEqual(signed.signature, EXPECTED_POLY_1271_SIGNATURE)
