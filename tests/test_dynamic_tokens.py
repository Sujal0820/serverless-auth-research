
import time
import unittest

from backend.dynamic_auth.tokens import issue_token, validate_token


TEST_SECRET = b"local-test-secret-change-me"
TEST_INVOCATION = "invocation-001"
TEST_SUBJECT = "cognito-user-001"


class DynamicTokenTests(unittest.TestCase):
    def setUp(self):
        self.token = issue_token(
            secret=TEST_SECRET,
            invocation_id=TEST_INVOCATION,
            subject=TEST_SUBJECT,
            ttl_seconds=30,
        )

    def test_valid_token_is_accepted(self):
        payload = validate_token(
            self.token,
            TEST_SECRET,
            TEST_INVOCATION,
            TEST_SUBJECT,
        )
        self.assertEqual(payload["invocation_id"], TEST_INVOCATION)
        self.assertEqual(payload["sub"], TEST_SUBJECT)

    def test_wrong_invocation_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_token(
                self.token,
                TEST_SECRET,
                "different-invocation",
                TEST_SUBJECT,
            )

    def test_wrong_subject_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_token(
                self.token,
                TEST_SECRET,
                TEST_INVOCATION,
                "different-cognito-user",
            )

    def test_modified_token_is_rejected(self):
        tampered_token = self.token + "tampered"
        with self.assertRaises(ValueError):
            validate_token(
                tampered_token,
                TEST_SECRET,
                TEST_INVOCATION,
                TEST_SUBJECT,
            )

    def test_expired_token_is_rejected(self):
        token = issue_token(
            secret=TEST_SECRET,
            invocation_id=TEST_INVOCATION,
            subject=TEST_SUBJECT,
            ttl_seconds=1,
        )
        time.sleep(2)

        with self.assertRaises(ValueError):
            validate_token(
                token,
                TEST_SECRET,
                TEST_INVOCATION,
                TEST_SUBJECT,
            )

    def test_malformed_token_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_token(
                "not-a-valid-token",
                TEST_SECRET,
                TEST_INVOCATION,
                TEST_SUBJECT,
            )

    def test_token_can_currently_be_reused(self):
        first = validate_token(
            self.token,
            TEST_SECRET,
            TEST_INVOCATION,
            TEST_SUBJECT,
        )
        second = validate_token(
            self.token,
            TEST_SECRET,
            TEST_INVOCATION,
            TEST_SUBJECT,
        )
        self.assertEqual(first["jti"], second["jti"])


if __name__ == "__main__":
    unittest.main()
