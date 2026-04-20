import asyncio
from unittest import TestCase

from py_clob_client_v2.constants import AMOY, ZERO_ADDRESS
from py_clob_client_v2.config import get_contract_config
from py_clob_client_v2.order_utils.exchange_order_builder_v1 import ExchangeOrderBuilderV1
from py_clob_client_v2.order_utils.model.order_data_v1 import OrderDataV1
from py_clob_client_v2.order_utils.model.ctf_exchange_v1_typed_data import (
    CTF_EXCHANGE_V1_DOMAIN_NAME,
    CTF_EXCHANGE_V1_DOMAIN_VERSION,
    CTF_EXCHANGE_V1_ORDER_STRUCT,
    EIP712_DOMAIN,
)
from py_clob_client_v2.order_utils.model.side import Side
from py_clob_client_v2.order_utils.model.signature_type_v1 import SignatureTypeV1
from py_clob_client_v2.signer import Signer

# publicly known private key
private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
chain_id = AMOY
signer = Signer(private_key=private_key, chain_id=chain_id)
contract_config = get_contract_config(chain_id)

FIXED_SALT = "479249096354"

_ORDER_DATA = OrderDataV1(
    maker=signer.address(),
    taker=ZERO_ADDRESS,
    tokenId="1234",
    makerAmount="100000000",
    takerAmount="50000000",
    side=Side.BUY,
    feeRateBps="100",
    nonce="0",
    signer=signer.address(),
    expiration="0",
    signatureType=SignatureTypeV1.EOA,
)


def run_async(coro):
    return asyncio.run(coro)


async def sign_callback_override(message_hash):
    return await signer.sign(message_hash)


callback_signer = Signer(
    chain_id=chain_id,
    address_override=signer.address(),
    sign_callback_override=sign_callback_override,
)

class TestExchangeOrderBuilderV1CTF(TestCase):
    """Tests against the CTF Exchange (Polymarket CTF Exchange v1)."""

    def setUp(self):
        self.builder = ExchangeOrderBuilderV1(
            contract_config.exchange, chain_id, signer
        )

    def test_build_order_random_salt(self):
        order = self.builder.build_order(_ORDER_DATA)
        self.assertIsNotNone(order)
        self.assertNotEqual(order.salt, "")
        self.assertEqual(order.maker, signer.address())
        self.assertEqual(order.signer, signer.address())
        self.assertEqual(order.taker, ZERO_ADDRESS)
        self.assertEqual(order.tokenId, "1234")
        self.assertEqual(order.makerAmount, "100000000")
        self.assertEqual(order.takerAmount, "50000000")
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.expiration, "0")
        self.assertEqual(order.nonce, "0")
        self.assertEqual(order.feeRateBps, "100")
        self.assertEqual(order.signatureType, SignatureTypeV1.EOA)

    def test_build_order_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        self.assertEqual(order.salt, FIXED_SALT)
        self.assertEqual(order.maker, signer.address())
        self.assertEqual(order.signer, signer.address())
        self.assertEqual(order.taker, ZERO_ADDRESS)
        self.assertEqual(order.tokenId, "1234")
        self.assertEqual(order.makerAmount, "100000000")
        self.assertEqual(order.takerAmount, "50000000")
        self.assertEqual(order.side, Side.BUY)
        self.assertEqual(order.expiration, "0")
        self.assertEqual(order.nonce, "0")
        self.assertEqual(order.feeRateBps, "100")
        self.assertEqual(order.signatureType, SignatureTypeV1.EOA)

    def test_build_order_typed_data_random_salt(self):
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        self.assertIsNotNone(typed_data)
        self.assertEqual(typed_data["primaryType"], "Order")
        self.assertEqual(typed_data["types"]["EIP712Domain"], EIP712_DOMAIN)
        self.assertEqual(typed_data["types"]["Order"], CTF_EXCHANGE_V1_ORDER_STRUCT)
        self.assertEqual(typed_data["domain"]["name"], CTF_EXCHANGE_V1_DOMAIN_NAME)
        self.assertEqual(typed_data["domain"]["version"], CTF_EXCHANGE_V1_DOMAIN_VERSION)
        self.assertEqual(typed_data["domain"]["chainId"], chain_id)
        self.assertEqual(typed_data["domain"]["verifyingContract"], contract_config.exchange)
        msg = typed_data["message"]
        self.assertEqual(msg["maker"], signer.address())
        self.assertEqual(msg["signer"], signer.address())
        self.assertEqual(msg["taker"], ZERO_ADDRESS)
        self.assertEqual(msg["tokenId"], 1234)
        self.assertEqual(msg["makerAmount"], 100000000)
        self.assertEqual(msg["takerAmount"], 50000000)
        self.assertEqual(msg["expiration"], 0)
        self.assertEqual(msg["nonce"], 0)
        self.assertEqual(msg["feeRateBps"], 100)
        self.assertEqual(msg["side"], 0)
        self.assertEqual(msg["signatureType"], 0)

    def test_build_order_typed_data_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        self.assertEqual(typed_data["message"]["salt"], int(FIXED_SALT))
        self.assertEqual(
            typed_data,
            {
                "primaryType": "Order",
                "types": {
                    "EIP712Domain": EIP712_DOMAIN,
                    "Order": CTF_EXCHANGE_V1_ORDER_STRUCT,
                },
                "domain": {
                    "name": CTF_EXCHANGE_V1_DOMAIN_NAME,
                    "version": CTF_EXCHANGE_V1_DOMAIN_VERSION,
                    "chainId": chain_id,
                    "verifyingContract": contract_config.exchange,
                },
                "message": {
                    "salt": int(FIXED_SALT),
                    "maker": signer.address(),
                    "signer": signer.address(),
                    "taker": ZERO_ADDRESS,
                    "tokenId": 1234,
                    "makerAmount": 100000000,
                    "takerAmount": 50000000,
                    "expiration": 0,
                    "nonce": 0,
                    "feeRateBps": 100,
                    "side": 0,
                    "signatureType": 0,
                },
            },
        )

    def test_build_order_signature_random_salt(self):
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        sig = run_async(self.builder.build_order_signature(typed_data))
        self.assertIsNotNone(sig)
        self.assertNotEqual(sig, "")

    def test_build_order_signature_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        sig = run_async(self.builder.build_order_signature(typed_data))
        self.assertEqual(
            sig,
            "0x302cd9abd0b5fcaa202a344437ec0b6660da984e24ae9ad915a592a90facf5a51bb8a873cd8d270f070217fea1986531d5eec66f1162a81f66e026db653bf7ce1c",
        )

    def test_build_order_signature_specific_salt_with_sign_callback_override(self):
        callback_builder = ExchangeOrderBuilderV1(
            contract_config.exchange, chain_id, callback_signer
        )
        callback_builder.generate_salt = lambda: FIXED_SALT
        order = callback_builder.build_order(_ORDER_DATA)
        typed_data = callback_builder.build_order_typed_data(order)
        sig = run_async(callback_builder.build_order_signature(typed_data))
        self.assertEqual(
            sig,
            "0x302cd9abd0b5fcaa202a344437ec0b6660da984e24ae9ad915a592a90facf5a51bb8a873cd8d270f070217fea1986531d5eec66f1162a81f66e026db653bf7ce1c",
        )

    def test_build_order_hash_random_salt(self):
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        order_hash = self.builder.build_order_hash(typed_data)
        self.assertIsNotNone(order_hash)
        self.assertTrue(order_hash.startswith("0x"))

    def test_build_order_hash_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        order_hash = self.builder.build_order_hash(typed_data)
        self.assertEqual(
            order_hash,
            "0x02ca1d1aa31103804173ad1acd70066cb6c1258a4be6dada055111f9a7ea4e55",
        )

    def test_build_signed_order_random_salt(self):
        signed = run_async(self.builder.build_signed_order(_ORDER_DATA))
        self.assertIsNotNone(signed)
        self.assertNotEqual(signed.salt, "")
        self.assertEqual(signed.maker, signer.address())
        self.assertEqual(signed.signer, signer.address())
        self.assertEqual(signed.taker, ZERO_ADDRESS)
        self.assertEqual(signed.tokenId, "1234")
        self.assertEqual(signed.makerAmount, "100000000")
        self.assertEqual(signed.takerAmount, "50000000")
        self.assertEqual(signed.side, Side.BUY)
        self.assertEqual(signed.expiration, "0")
        self.assertEqual(signed.nonce, "0")
        self.assertEqual(signed.feeRateBps, "100")
        self.assertEqual(signed.signatureType, SignatureTypeV1.EOA)
        self.assertNotEqual(signed.signature, "")

    def test_build_signed_order_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        signed = run_async(self.builder.build_signed_order(_ORDER_DATA))
        self.assertEqual(signed.salt, FIXED_SALT)
        self.assertEqual(signed.maker, signer.address())
        self.assertEqual(signed.signer, signer.address())
        self.assertEqual(signed.taker, ZERO_ADDRESS)
        self.assertEqual(signed.tokenId, "1234")
        self.assertEqual(signed.makerAmount, "100000000")
        self.assertEqual(signed.takerAmount, "50000000")
        self.assertEqual(signed.side, Side.BUY)
        self.assertEqual(signed.expiration, "0")
        self.assertEqual(signed.nonce, "0")
        self.assertEqual(signed.feeRateBps, "100")
        self.assertEqual(signed.signatureType, SignatureTypeV1.EOA)
        self.assertEqual(
            signed.signature,
            "0x302cd9abd0b5fcaa202a344437ec0b6660da984e24ae9ad915a592a90facf5a51bb8a873cd8d270f070217fea1986531d5eec66f1162a81f66e026db653bf7ce1c",
        )

class TestExchangeOrderBuilderV1NegRisk(TestCase):
    """Tests against the Neg Risk CTF Exchange."""

    def setUp(self):
        self.builder = ExchangeOrderBuilderV1(
            contract_config.neg_risk_exchange, chain_id, signer
        )

    def test_build_order_random_salt(self):
        order = self.builder.build_order(_ORDER_DATA)
        self.assertNotEqual(order.salt, "")
        self.assertEqual(order.maker, signer.address())
        self.assertEqual(order.tokenId, "1234")

    def test_build_order_typed_data_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        self.assertEqual(
            typed_data["domain"]["verifyingContract"],
            contract_config.neg_risk_exchange,
        )
        self.assertEqual(typed_data["message"]["salt"], int(FIXED_SALT))

    def test_build_order_signature_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        sig = run_async(self.builder.build_order_signature(typed_data))
        self.assertEqual(
            sig,
            "0x1b3646ef347e5bd144c65bd3357ba19c12c12abaeedae733cf8579bc51a2752c0454c3bc6b236957e393637982c769b8dc0706c0f5c399983d933850afd1cbcd1c",
        )

    def test_build_order_hash_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        order = self.builder.build_order(_ORDER_DATA)
        typed_data = self.builder.build_order_typed_data(order)
        order_hash = self.builder.build_order_hash(typed_data)
        self.assertEqual(
            order_hash,
            "0xf15790d3edc4b5aed427b0b543a9206fcf4b1a13dfed016d33bfb313076263b8",
        )

    def test_build_signed_order_specific_salt(self):
        self.builder.generate_salt = lambda: FIXED_SALT
        signed = run_async(self.builder.build_signed_order(_ORDER_DATA))
        self.assertEqual(signed.salt, FIXED_SALT)
        self.assertEqual(
            signed.signature,
            "0x1b3646ef347e5bd144c65bd3357ba19c12c12abaeedae733cf8579bc51a2752c0454c3bc6b236957e393637982c769b8dc0706c0f5c399983d933850afd1cbcd1c",
        )
