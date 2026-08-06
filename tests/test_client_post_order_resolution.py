import base64
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from py_clob_client_v2.client import ClobClient
from py_clob_client_v2.clob_types import (
    ApiCreds,
    OrderType,
    PostOrdersV1Args,
    TradeParams,
)
from py_clob_client_v2.constants import AMOY
from py_clob_client_v2.order_utils.model.side import Side

# publicly known private key
PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


def _make_client() -> ClobClient:
    return ClobClient(
        host="http://localhost:8080",
        chain_id=AMOY,
        key=PRIVATE_KEY,
        creds=ApiCreds(
            api_key="key",
            api_secret=base64.urlsafe_b64encode(b"secret-secret-secret").decode(),
            api_passphrase="passphrase",
        ),
    )


def _make_signed_order():
    return SimpleNamespace(
        salt="1000",
        maker="0xmaker",
        signer="0xsigner",
        taker="0xtaker",
        tokenId="123",
        makerAmount="50",
        takerAmount="100",
        side=Side.BUY,
        expiration="0",
        nonce="0",
        feeRateBps="0",
        signatureType=0,
        signature="0xsig",
    )


def _make_order_response(**overrides) -> dict:
    response = {
        "success": True,
        "errorMsg": "",
        "orderID": "0xorder",
        "status": "matched",
        "takingAmount": "100",
        "makingAmount": "50",
    }
    response.update(overrides)
    return response


def _make_trade(**overrides) -> dict:
    trade = {
        "id": "trade-1",
        "taker_order_id": "0xorder",
        "market": "0xmarket",
        "asset_id": "123",
        "side": "BUY",
        "size": "100",
        "fee_rate_bps": "0",
        "price": "0.5",
        "status": "MATCHED",
        "match_time": "1752500000",
        "last_update": "1752500000",
        "outcome": "YES",
        "owner": "owner",
        "maker_address": "0xmaker",
        "maker_orders": [],
        "trader_side": "TAKER",
    }
    trade.update(overrides)
    return trade


class TestPostOrderResolution(unittest.TestCase):
    def test_returns_sync_responses_without_polling(self):
        client = _make_client()
        response = _make_order_response(
            transactionsHashes=["0xaaa"], tradeIDs=["trade-1"]
        )
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades") as get_trades,
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0xaaa"])
        get_trades.assert_not_called()

    def test_resolves_hashes_by_polling_when_only_trade_ids_returned(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        pending = _make_trade()
        executed = _make_trade(status="MINED", transaction_hash="0xccc")
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(
                client, "get_trades", side_effect=[[pending], [executed]]
            ) as get_trades,
            patch("py_clob_client_v2.client.time.sleep") as sleep,
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0xccc"])
        self.assertEqual(res["tradeIDs"], ["trade-1"])
        self.assertEqual(get_trades.call_count, 2)
        get_trades.assert_called_with(TradeParams(id="trade-1"), only_first_page=True)
        sleep.assert_called()

    def test_resolves_hashes_for_limit_orders_that_matched_on_placement(self):
        client = _make_client()
        # partial fill: matched portion produced a trade, remainder rests on the book
        response = _make_order_response(tradeIDs=["trade-1"])
        executed = _make_trade(status="CONFIRMED", transaction_hash="0xeee")
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades", return_value=[executed]),
        ):
            res = client.post_order(_make_signed_order(), OrderType.GTC)

        self.assertEqual(res["transactionsHashes"], ["0xeee"])

    def test_does_not_poll_for_orders_resting_on_the_book(self):
        client = _make_client()
        response = _make_order_response(status="live")
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades") as get_trades,
        ):
            res = client.post_order(_make_signed_order(), OrderType.GTC)

        self.assertNotIn("transactionsHashes", res)
        get_trades.assert_not_called()

    def test_does_not_poll_for_defer_exec_orders(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades") as get_trades,
        ):
            res = client.post_order(
                _make_signed_order(), OrderType.FOK, defer_exec=True
            )

        self.assertNotIn("transactionsHashes", res)
        get_trades.assert_not_called()

    def test_excludes_failed_trades_from_resolved_hashes(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1", "trade-2"])

        def trades_for(params, only_first_page=False):
            if params.id == "trade-1":
                return [_make_trade(id="trade-1", status="FAILED")]
            return [_make_trade(id="trade-2", status="MINED", transaction_hash="0x222")]

        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades", side_effect=trades_for),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0x222"])

    def test_returns_response_without_hashes_when_every_trade_failed(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(
                client, "get_trades", return_value=[_make_trade(status="FAILED")]
            ),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertNotIn("transactionsHashes", res)
        self.assertEqual(res["tradeIDs"], ["trade-1"])

    def test_best_effort_returns_response_unchanged_on_timeout(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        clock = iter(float(i) for i in range(100_000))
        with (
            patch.object(client, "_post", return_value=response),
            # trade never resolves
            patch.object(client, "get_trades", return_value=[_make_trade()]),
            patch(
                "py_clob_client_v2.client.time.monotonic",
                side_effect=lambda: next(clock),
            ),
            patch("py_clob_client_v2.client.time.sleep"),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertNotIn("transactionsHashes", res)
        self.assertEqual(res["tradeIDs"], ["trade-1"])
        self.assertEqual(res["status"], "matched")

    def test_returns_partially_resolved_hashes_on_timeout(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1", "trade-2"])
        clock = iter(float(i) for i in range(100_000))

        def trades_for(params, only_first_page=False):
            if params.id == "trade-1":
                return [
                    _make_trade(id="trade-1", status="MINED", transaction_hash="0x111")
                ]
            return [_make_trade(id="trade-2")]  # never resolves

        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades", side_effect=trades_for),
            patch(
                "py_clob_client_v2.client.time.monotonic",
                side_effect=lambda: next(clock),
            ),
            patch("py_clob_client_v2.client.time.sleep"),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0x111"])

    def test_retries_after_transient_trade_polling_failures(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        executed = _make_trade(status="MINED", transaction_hash="0xfff")
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(
                client,
                "get_trades",
                side_effect=[Exception("trades api unavailable"), [executed]],
            ) as get_trades,
            patch("py_clob_client_v2.client.time.sleep"),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0xfff"])
        self.assertEqual(get_trades.call_count, 2)

    def test_never_raises_on_successful_post_when_polling_keeps_failing(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        clock = iter(float(i) for i in range(100_000))
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(
                client, "get_trades", side_effect=Exception("trades api unavailable")
            ),
            patch(
                "py_clob_client_v2.client.time.monotonic",
                side_effect=lambda: next(clock),
            ),
            patch("py_clob_client_v2.client.time.sleep"),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertNotIn("transactionsHashes", res)
        self.assertEqual(res["tradeIDs"], ["trade-1"])
        self.assertEqual(res["status"], "matched")

    def test_deduplicates_trade_ids_before_polling(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1", "trade-1"])
        executed = _make_trade(status="MINED", transaction_hash="0xccc")
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades", return_value=[executed]) as get_trades,
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0xccc"])
        self.assertEqual(get_trades.call_count, 1)

    def test_ignores_unrelated_trades_in_poll_results(self):
        client = _make_client()
        response = _make_order_response(tradeIDs=["trade-1"])
        unrelated = _make_trade(
            id="trade-other", status="MINED", transaction_hash="0xother"
        )
        executed = _make_trade(id="trade-1", status="MINED", transaction_hash="0x111")
        with (
            patch.object(client, "_post", return_value=response),
            patch.object(client, "get_trades", side_effect=[[unrelated], [executed]]),
            patch("py_clob_client_v2.client.time.sleep"),
        ):
            res = client.post_order(_make_signed_order(), OrderType.FOK)

        self.assertEqual(res["transactionsHashes"], ["0x111"])


class TestPostOrdersResolution(unittest.TestCase):
    def test_resolves_matched_entries_and_skips_unmatched_ones(self):
        client = _make_client()
        responses = [
            _make_order_response(orderID="0xorder-1", tradeIDs=["trade-1"]),
            _make_order_response(orderID="0xorder-2", status="live"),
        ]
        executed = _make_trade(status="MINED", transaction_hash="0x111")
        with (
            patch.object(client, "_post", return_value=responses),
            patch.object(client, "get_trades", return_value=[executed]) as get_trades,
        ):
            res = client.post_orders(
                [
                    PostOrdersV1Args(
                        order=_make_signed_order(), orderType=OrderType.FOK
                    ),
                    PostOrdersV1Args(
                        order=_make_signed_order(), orderType=OrderType.GTC
                    ),
                ]
            )

        self.assertEqual(res[0]["transactionsHashes"], ["0x111"])
        self.assertNotIn("transactionsHashes", res[1])
        self.assertEqual(get_trades.call_count, 1)
        get_trades.assert_called_with(TradeParams(id="trade-1"), only_first_page=True)

    def test_does_not_poll_when_posting_with_defer_exec(self):
        client = _make_client()
        responses = [_make_order_response(tradeIDs=["trade-1"])]
        with (
            patch.object(client, "_post", return_value=responses),
            patch.object(client, "get_trades") as get_trades,
        ):
            res = client.post_orders(
                [PostOrdersV1Args(order=_make_signed_order(), orderType=OrderType.FOK)],
                defer_exec=True,
            )

        self.assertNotIn("transactionsHashes", res[0])
        get_trades.assert_not_called()


if __name__ == "__main__":
    unittest.main()
