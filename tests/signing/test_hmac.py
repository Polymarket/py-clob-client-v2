from unittest import TestCase
import binascii
import json

from py_clob_client_v2.signing.hmac import build_hmac_signature


class TestHMAC(TestCase):
    def setUp(self):
        self.secret = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="
        self.timestamp = "1000000"
        self.method = "test-sign"
        self.path = "/orders"
        self.string_body = '{"hash": "0x123"}'
        self.baseline_signature = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, self.string_body
        )

    def test_build_hmac_signature_matches_expected(self):
        signature = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, self.string_body
        )
        self.assertIsNotNone(signature)
        self.assertEqual("ZwAdJKvoYRlEKDkNMwd5BuwNNtg93kNaR_oU2HrfVvc=", signature)

    def test_dict_body_same_as_equivalent_string_body(self):
        dict_body_sig = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, {"hash": "0x123"}
        )
        self.assertEqual(self.baseline_signature, dict_body_sig)

    def test_different_method_changes_signature(self):
        get_sig = build_hmac_signature(
            self.secret, self.timestamp, "GET", self.path, {"hash": "0x123"}
        )
        post_sig = build_hmac_signature(
            self.secret, self.timestamp, "POST", self.path, {"hash": "0x123"}
        )
        self.assertNotEqual(get_sig, post_sig)
        self.assertNotEqual(get_sig, self.baseline_signature)

    def test_different_timestamp_changes_signature(self):
        sig = build_hmac_signature(
            self.secret, "1000001", self.method, self.path, {"hash": "0x123"}
        )
        self.assertNotEqual(sig, self.baseline_signature)

    def test_different_path_changes_signature(self):
        sig = build_hmac_signature(
            self.secret, self.timestamp, self.method, "/api/v1/orders", {"hash": "0x123"}
        )
        self.assertNotEqual(sig, self.baseline_signature)

    def test_extra_key_and_ordering_affect_signature(self):
        sig1 = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path,
            {"hash": "0x123", "foo": "bar"},
        )
        sig2 = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path,
            {"foo": "bar", "hash": "0x123"},
        )
        self.assertNotEqual(sig1, sig2)
        self.assertNotEqual(sig1, self.baseline_signature)

    def test_array_body_signature(self):
        sig = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, [1, 2, 3]
        )
        self.assertIsNotNone(sig)
        self.assertNotEqual(sig, self.baseline_signature)

    def test_unicode_body_signature(self):
        sig = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, {"emoji": "😃"}
        )
        self.assertIsNotNone(sig)
        self.assertNotEqual(sig, self.baseline_signature)

    def test_none_body_omitted_from_message(self):
        sig = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, None
        )
        self.assertNotEqual(sig, self.baseline_signature)

    def test_empty_string_body_omitted(self):
        sig = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, ""
        )
        self.assertNotEqual(sig, self.baseline_signature)

    def test_none_and_empty_body_same_signature(self):
        sig_none = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, None
        )
        sig_empty = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, ""
        )
        self.assertEqual(sig_none, sig_empty)

    def test_idempotent_same_inputs(self):
        sig1 = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, {"hash": "0x123"}
        )
        sig2 = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, {"hash": "0x123"}
        )
        self.assertEqual(sig1, sig2)

    def test_different_secret_changes_signature(self):
        other = build_hmac_signature(
            "BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB=",
            self.timestamp, self.method, self.path, {"hash": "0x123"},
        )
        original = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, {"hash": "0x123"}
        )
        self.assertNotEqual(other, original)

    def test_invalid_secret_raises(self):
        with self.assertRaises(binascii.Error):
            build_hmac_signature(
                "!!!notbase64!!!", self.timestamp, self.method, self.path, {"hash": "0x123"}
            )

    def test_boolean_body_signature(self):
        sig_true = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, True
        )
        sig_false = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, False
        )
        self.assertIsNotNone(sig_true)
        self.assertIsNotNone(sig_false)
        self.assertNotEqual(sig_true, sig_false)

    def test_numeric_body_signature(self):
        sig_int = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, 42
        )
        sig_float = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, 3.14159
        )
        self.assertIsNotNone(sig_int)
        self.assertIsNotNone(sig_float)
        self.assertNotEqual(sig_int, sig_float)

    def test_nested_object_no_sorting_means_signatures_can_differ(self):
        body_a = {"a": {"z": 1, "b": 2}, "c": [3, 2, 1]}
        body_b = {"c": [3, 2, 1], "a": {"b": 2, "z": 1}}
        sig_a = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, body_a
        )
        sig_b = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, body_b
        )
        self.assertNotEqual(sig_a, sig_b)

    def test_list_of_dicts_key_order_affects_signature(self):
        body1 = [{"b": 2, "a": 1}, {"d": 4, "c": 3}]
        body2 = [{"a": 1, "b": 2}, {"c": 3, "d": 4}]
        sig1 = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, body1
        )
        sig2 = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, body2
        )
        self.assertNotEqual(sig1, sig2)

    def test_string_body_preserved_verbatim(self):
        sig_a = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, '{"x":1, "y":2}'
        )
        sig_b = build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, '{"x":1,"y":2}'
        )
        self.assertNotEqual(sig_a, sig_b)

    def _sig(self, body):
        return build_hmac_signature(
            self.secret, self.timestamp, self.method, self.path, body
        )

    def test_bool_value_serialized_as_json_not_python_repr(self):
        # Regression for #108: str({"deferExec": False}) yields "False", not the
        # JSON "false" the server actually receives. The signature must be taken
        # over the json.dumps form so it matches the sent payload.
        body = {"deferExec": False}
        self.assertEqual(
            self._sig(body), self._sig(json.dumps(body, ensure_ascii=False))
        )
        # The broken str()-based rendering must NOT match the fixed signature.
        self.assertNotEqual(self._sig(body), self._sig(str(body).replace("'", '"')))
        # Explicitly: signing the dict matches signing '{"deferExec": false}'.
        self.assertEqual(self._sig(body), self._sig('{"deferExec": false}'))

    def test_none_value_serialized_as_json_null(self):
        # Regression for #108: str({"foo": None}) yields "None", not JSON "null".
        body = {"foo": None}
        self.assertEqual(
            self._sig(body), self._sig(json.dumps(body, ensure_ascii=False))
        )
        self.assertNotEqual(self._sig(body), self._sig(str(body).replace("'", '"')))
        self.assertEqual(self._sig(body), self._sig('{"foo": null}'))

    def test_bool_true_and_nested_none_serialized_as_json(self):
        body = {"a": True, "b": {"c": None}, "d": [False, None]}
        self.assertEqual(
            self._sig(body), self._sig(json.dumps(body, ensure_ascii=False))
        )
        self.assertEqual(
            self._sig(body),
            self._sig('{"a": true, "b": {"c": null}, "d": [false, null]}'),
        )
