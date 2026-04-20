import asyncio
from datetime import datetime
from unittest import TestCase

from py_clob_client_v2.clob_types import ApiCreds, RequestArgs
from py_clob_client_v2.constants import AMOY
from py_clob_client_v2.headers.headers import (
    POLY_ADDRESS,
    POLY_API_KEY,
    POLY_NONCE,
    POLY_PASSPHRASE,
    POLY_SIGNATURE,
    POLY_TIMESTAMP,
    create_level_1_headers,
    create_level_2_headers,
)
from py_clob_client_v2.signer import Signer

# publicly known private key
private_key = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
chain_id = AMOY
signer = Signer(private_key=private_key, chain_id=chain_id)

creds = ApiCreds(
    api_key="000000000-0000-0000-0000-000000000000",
    api_passphrase="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    api_secret="AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=",
)


class TestHeaders(TestCase):
    def test_create_level_1_headers(self):
        # no nonce
        headers = asyncio.run(create_level_1_headers(signer))
        self.assertIsNotNone(headers)
        self.assertEqual(headers[POLY_ADDRESS], signer.address())
        self.assertIsNotNone(headers[POLY_SIGNATURE])
        self.assertIsNotNone(headers[POLY_TIMESTAMP])
        self.assertTrue(int(headers[POLY_TIMESTAMP]) <= int(datetime.now().timestamp()))
        self.assertEqual(headers[POLY_NONCE], "0")

        # with nonce
        headers = asyncio.run(create_level_1_headers(signer, nonce=1012))
        self.assertIsNotNone(headers)
        self.assertEqual(headers[POLY_ADDRESS], signer.address())
        self.assertIsNotNone(headers[POLY_SIGNATURE])
        self.assertIsNotNone(headers[POLY_TIMESTAMP])
        self.assertTrue(int(headers[POLY_TIMESTAMP]) <= int(datetime.now().timestamp()))
        self.assertEqual(headers[POLY_NONCE], "1012")

    def test_create_level_2_headers(self):
        # no body
        headers = create_level_2_headers(
            signer, creds, request_args=RequestArgs(method="get", request_path="/order")
        )
        self.assertIsNotNone(headers)
        self.assertEqual(headers[POLY_ADDRESS], signer.address())
        self.assertIsNotNone(headers[POLY_SIGNATURE])
        self.assertIsNotNone(headers[POLY_TIMESTAMP])
        self.assertTrue(int(headers[POLY_TIMESTAMP]) <= int(datetime.now().timestamp()))
        self.assertEqual(headers[POLY_API_KEY], creds.api_key)
        self.assertEqual(headers[POLY_PASSPHRASE], creds.api_passphrase)

        # with body
        headers = create_level_2_headers(
            signer,
            creds,
            request_args=RequestArgs(
                method="post", request_path="/order", body='{"hash": "0x123"}'
            ),
        )
        self.assertIsNotNone(headers)
        self.assertEqual(headers[POLY_ADDRESS], signer.address())
        self.assertIsNotNone(headers[POLY_SIGNATURE])
        self.assertIsNotNone(headers[POLY_TIMESTAMP])
        self.assertTrue(int(headers[POLY_TIMESTAMP]) <= int(datetime.now().timestamp()))
        self.assertEqual(headers[POLY_API_KEY], creds.api_key)
        self.assertEqual(headers[POLY_PASSPHRASE], creds.api_passphrase)
