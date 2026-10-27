
import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from backend.dynamic_auth.replay_store import (
    ReplayDetectedError,
    consume_token,
)


class TestReplayStore(unittest.TestCase):
    def setUp(self):
        self.table = Mock()

    def test_first_use_is_accepted(self):
        consume_token(self.table, "jti-001", 2000000000)

        self.table.put_item.assert_called_once_with(
            Item={
                "jti": "jti-001",
                "expires_at": 2000000000,
            },
            ConditionExpression="attribute_not_exists(jti)",
        )

    def test_second_use_is_rejected(self):
        self.table.put_item.side_effect = ClientError(
            {
                "Error": {
                    "Code": "ConditionalCheckFailedException",
                    "Message": "The item already exists",
                }
            },
            "PutItem",
        )

        with self.assertRaises(ReplayDetectedError):
            consume_token(self.table, "jti-001", 2000000000)

    def test_other_dynamodb_errors_propagate(self):
        error = ClientError(
            {
                "Error": {
                    "Code": "AccessDeniedException",
                    "Message": "Access denied",
                }
            },
            "PutItem",
        )
        self.table.put_item.side_effect = error

        with self.assertRaises(ClientError):
            consume_token(self.table, "jti-001", 2000000000)

    def test_empty_jti_is_rejected(self):
        with self.assertRaises(ValueError):
            consume_token(self.table, "", 2000000000)

        self.table.put_item.assert_not_called()

    def test_invalid_expiry_is_rejected(self):
        with self.assertRaises(ValueError):
            consume_token(self.table, "jti-001", 0)

        self.table.put_item.assert_not_called()


if __name__ == "__main__":
    unittest.main()
