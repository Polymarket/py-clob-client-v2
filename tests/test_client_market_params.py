from unittest import TestCase

from py_clob_client_v2 import BookParams, ClobClient, Side
from py_clob_client_v2.endpoints import (
    GET_LAST_TRADES_PRICES,
    GET_MIDPOINTS,
    GET_ORDER_BOOKS,
    GET_PRICES,
    GET_SPREADS,
)

TEST_HOST = "https://example.invalid"


class TestClientMarketParams(TestCase):
    def setUp(self):
        self.client = ClobClient(host=TEST_HOST, chain_id=80002)
        self.calls = []

        def fake_post(endpoint, headers=None, data=None, params=None):
            self.calls.append(
                {
                    "endpoint": endpoint,
                    "headers": headers,
                    "data": data,
                    "params": params,
                }
            )
            return data

        self.client._post = fake_post

    def assert_last_call(self, endpoint, data):
        self.assertEqual(self.calls[-1]["endpoint"], f"{TEST_HOST}{endpoint}")
        self.assertEqual(self.calls[-1]["data"], data)

    def test_get_order_books_serializes_book_params(self):
        result = self.client.get_order_books([BookParams(token_id="123")])

        self.assertEqual(result, [{"token_id": "123"}])
        self.assert_last_call(GET_ORDER_BOOKS, [{"token_id": "123"}])

    def test_get_order_book_hash_accepts_raw_api_response(self):
        raw_orderbook = {
            "market": "0xaabbcc",
            "asset_id": "100",
            "bids": [
                {"price": "0.3", "size": "100"},
                {"price": "0.4", "size": "100"},
            ],
            "asks": [
                {"price": "0.6", "size": "100"},
                {"price": "0.7", "size": "100"},
            ],
            "hash": "",
            "timestamp": "123456789",
            "min_order_size": "100",
            "neg_risk": False,
            "tick_size": "0.01",
            "last_trade_price": "0.5",
        }

        self.assertEqual(
            self.client.get_order_book_hash(raw_orderbook),
            "0458ea5755c9f73d64a14636fa5c36ed460ec394",
        )

    def test_get_midpoints_serializes_book_params(self):
        result = self.client.get_midpoints([BookParams(token_id="123")])

        self.assertEqual(result, [{"token_id": "123"}])
        self.assert_last_call(GET_MIDPOINTS, [{"token_id": "123"}])

    def test_get_prices_serializes_side_values(self):
        result = self.client.get_prices(
            [
                BookParams(token_id="123", side=Side.BUY),
                {"token_id": "456", "side": Side.SELL},
            ]
        )

        self.assertEqual(
            result,
            [
                {"token_id": "123", "side": "BUY"},
                {"token_id": "456", "side": "SELL"},
            ],
        )
        self.assert_last_call(GET_PRICES, result)

    def test_get_spreads_serializes_book_params(self):
        result = self.client.get_spreads([BookParams(token_id="123")])

        self.assertEqual(result, [{"token_id": "123"}])
        self.assert_last_call(GET_SPREADS, [{"token_id": "123"}])

    def test_get_last_trades_prices_serializes_book_params(self):
        result = self.client.get_last_trades_prices(
            [
                BookParams(token_id="123"),
                {"token_id": "456", "side": Side.SELL},
            ]
        )

        self.assertEqual(
            result,
            [
                {"token_id": "123"},
                {"token_id": "456", "side": "SELL"},
            ],
        )
        self.assert_last_call(GET_LAST_TRADES_PRICES, result)
