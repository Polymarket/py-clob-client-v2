from unittest import TestCase

from py_clob_client_v2.clob_types import (
    DropNotificationParams,
    OrdersScoringParams,
)
from py_clob_client_v2.http_helpers.helpers import (
    build_query_params,
    parse_drop_notification_params,
    parse_orders_scoring_params,
)


class TestHelpers(TestCase):
    def test_build_query_params(self):
        # last char is ?
        url = build_query_params("http://tracker?", "q1", "a")
        self.assertIsNotNone(url)
        self.assertEqual(url, "http://tracker?q1=a")

        # last char is not ?
        url = build_query_params("http://tracker?q1=a", "q2", "b")
        self.assertIsNotNone(url)
        self.assertEqual(url, "http://tracker?q1=a&q2=b")

    def test_parse_orders_scoring_params(self):
        result = parse_orders_scoring_params(
            OrdersScoringParams(orderIds=["0xaaa", "0xbbb"])
        )
        self.assertEqual(result, {"order_ids": "0xaaa,0xbbb"})

    def test_parse_orders_scoring_params_empty(self):
        self.assertEqual(parse_orders_scoring_params(None), {})
        self.assertEqual(parse_orders_scoring_params(OrdersScoringParams(orderIds=[])), {})

    def test_parse_drop_notification_params(self):
        result = parse_drop_notification_params(
            DropNotificationParams(ids=["1", "2", "3"])
        )
        self.assertEqual(result, {"ids": "1,2,3"})

    def test_parse_drop_notification_params_empty(self):
        self.assertEqual(parse_drop_notification_params(None), {})
        self.assertEqual(parse_drop_notification_params(DropNotificationParams(ids=[])), {})
