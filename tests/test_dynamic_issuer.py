
import base64
import unittest
from unittest.mock import Mock

from backend.dynamic_auth.issuer import (
    issue_invocation_token,
    load_signing_secret,
)
from backend.dynamic_auth.tokens import validate_token


TEST_SECRET = b"local-test-secret-change-me-32-bytes-minimum"

class DynamicIssuerTests(unittest.TestCase):
    def test_issuer_generates_unique_invocation_ids(self):
        first = issue_invocation_token("user-001", TEST_SECRET)
        second = issue_invocation_token("user-001", TEST_SECRET)

        self.assertNotEqual(
            first["invocation_id"],
            second["invocation_id"],
        )

    def test_issued_token_is_bound_to_subject_and_invocation(self):
        result = issue_invocation_token("user-001", TEST_SECRET)

        payload = validate_token(
            token=result["token"],
            secret=TEST_SECRET,
            expected_invocation_id=result["invocation_id"],
            expected_subject="user-001",
        )

        self.assertEqual(payload["sub"], "user-001")
        self.assertEqual(payload["exp"] - payload["iat"], 30)
        self.assertEqual(result["expires_in"], 30)

    def test_empty_subject_is_rejected(self):
        with self.assertRaises(ValueError):
            issue_invocation_token("", TEST_SECRET)

    def test_secret_is_loaded_and_decoded(self):
        encoded_secret = base64.b64encode(TEST_SECRET).decode("ascii")
        client = Mock()
        client.get_secret_value.return_value = {
            "SecretString": encoded_secret
        }

        result = load_signing_secret("test-secret", client)

        self.assertEqual(result, TEST_SECRET)
        client.get_secret_value.assert_called_once_with(
            SecretId="test-secret"
        )

    def test_missing_secret_value_is_rejected(self):
        client = Mock()
        client.get_secret_value.return_value = {}

        with self.assertRaises(ValueError):
            load_signing_secret("test-secret", client)

    def test_short_secret_is_rejected(self):
        client = Mock()
        client.get_secret_value.return_value = {
            "SecretString": base64.b64encode(b"short").decode("ascii")
        }

        with self.assertRaises(ValueError):
            load_signing_secret("test-secret", client)


if __name__ == "__main__":
    unittest.main()
