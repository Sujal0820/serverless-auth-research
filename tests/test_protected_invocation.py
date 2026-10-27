
import time
import unittest
from unittest.mock import Mock

from backend.dynamic_auth.tokens import issue_token
from backend.dynamic_auth.replay_store import ReplayDetectedError
from backend.dynamic_auth.protected_invocation import validate_and_consume


TEST_SECRET = b"local-test-secret-change-me"
TEST_SUBJECT = "cognito-user-001"


class TestProtectedInvocation(unittest.TestCase):
    def setUp(self):
        self.table = Mock()
        self.invocation_id = "invocation-001"

        self.token = issue_token(
            secret=TEST_SECRET,
            invocation_id=self.invocation_id,
            subject=TEST_SUBJECT,
            ttl_seconds=30,
        )

    def test_valid_token_is_consumed(self):
        payload = validate_and_consume(
            token=self.token,
            secret=TEST_SECRET,
            expected_invocation_id=self.invocation_id,
            expected_subject=TEST_SUBJECT,
            dynamodb_table=self.table,
        )

        self.assertEqual(payload["invocation_id"], self.invocation_id)
        self.assertEqual(payload["sub"], TEST_SUBJECT)
        self.table.put_item.assert_called_once()

    def test_wrong_invocation_does_not_consume_token(self):
        with self.assertRaises(ValueError):
            validate_and_consume(
                token=self.token,
                secret=TEST_SECRET,
                expected_invocation_id="different-invocation",
                expected_subject=TEST_SUBJECT,
                dynamodb_table=self.table,
            )

        self.table.put_item.assert_not_called()

    def test_wrong_subject_does_not_consume_token(self):
        with self.assertRaises(ValueError):
            validate_and_consume(
                token=self.token,
                secret=TEST_SECRET,
                expected_invocation_id=self.invocation_id,
                expected_subject="different-cognito-user",
                dynamodb_table=self.table,
            )

        self.table.put_item.assert_not_called()

    def test_invalid_signature_does_not_consume_token(self):
        tampered_token = self.token + "tampered"

        with self.assertRaises(ValueError):
            validate_and_consume(
                token=tampered_token,
                secret=TEST_SECRET,
                expected_invocation_id=self.invocation_id,
                expected_subject=TEST_SUBJECT,
                dynamodb_table=self.table,
            )

        self.table.put_item.assert_not_called()

    def test_replayed_token_is_rejected(self):
        self.table.put_item.side_effect = ReplayDetectedError(
            "Dynamic token has already been consumed"
        )

        with self.assertRaises(ReplayDetectedError):
            validate_and_consume(
                token=self.token,
                secret=TEST_SECRET,
                expected_invocation_id=self.invocation_id,
                expected_subject=TEST_SUBJECT,
                dynamodb_table=self.table,
            )

    def test_expired_token_does_not_consume_token(self):
        expired_token = issue_token(
            secret=TEST_SECRET,
            invocation_id=self.invocation_id,
            subject=TEST_SUBJECT,
            ttl_seconds=1,
        )
        time.sleep(2)

        with self.assertRaises(ValueError):
            validate_and_consume(
                token=expired_token,
                secret=TEST_SECRET,
                expected_invocation_id=self.invocation_id,
                expected_subject=TEST_SUBJECT,
                dynamodb_table=self.table,
            )

        self.table.put_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
