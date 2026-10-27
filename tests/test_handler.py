import json
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("RESEARCH_EVENTS_TABLE", "test-research-events")
os.environ.setdefault("REPLAY_STATE_TABLE", "test-replay-state")
os.environ.setdefault("SIGNING_SECRET_NAME", "test-signing-secret")

from backend.foundation import handler


def make_event(route_key, body=None, subject="test-cognito-subject"):
    return {
        "routeKey": route_key,
        "body": json.dumps(body) if body is not None else None,
        "requestContext": {
            "authorizer": {
                "jwt": {
                    "claims": {"sub": subject}
                }
            }
        },
    }


class HandlerTests(unittest.TestCase):

    @patch.object(handler, "issue_invocation_token_from_environment")
    def test_token_route_issues_token_for_authenticated_subject(self, issue):
        issue.return_value = {
            "invocation_id": "invocation-123",
            "token": "test-token",
            "expires_in": 30,
        }

        result = handler.lambda_handler(make_event("POST /token"), None)

        self.assertEqual(result["statusCode"], 200)
        issue.assert_called_once_with("test-cognito-subject")
        self.assertEqual(json.loads(result["body"])["invocation_id"], "invocation-123")

    def test_missing_subject_is_rejected(self):
        event = {
            "routeKey": "POST /token",
            "requestContext": {"authorizer": {"jwt": {"claims": {}}}},
        }

        result = handler.lambda_handler(event, None)

        self.assertEqual(result["statusCode"], 401)

    def test_unknown_route_returns_404(self):
        result = handler.lambda_handler(make_event("GET /unknown"), None)

        self.assertEqual(result["statusCode"], 404)


    def test_research_missing_token_fields_returns_400(self):
        result = handler.lambda_handler(
            make_event("POST /research", {"other": "value"}),
            None,
        )

        self.assertEqual(result["statusCode"], 400)

    @patch.object(handler.events_table, "put_item")
    @patch.object(handler, "load_signing_secret", return_value=b"x" * 32)
    @patch.object(handler, "validate_and_consume")
    def test_valid_dynamic_token_is_accepted(
        self, validate, load_secret, put_event
    ):
        validate.return_value = {
            "jti": "jti-123",
            "invocation_id": "invocation-123",
            "sub": "test-cognito-subject",
            "iat": 100,
            "exp": 200,
        }

        result = handler.lambda_handler(
            make_event(
                "POST /research",
                {
                    "token": "test-token",
                    "invocation_id": "invocation-123",
                },
            ),
            None,
        )

        self.assertEqual(result["statusCode"], 200)
        validate.assert_called_once()
        put_event.assert_called_once()


    @patch.object(handler, "load_signing_secret", return_value=b"x" * 32)
    @patch.object(handler, "validate_and_consume")
    def test_invalid_token_returns_401(self, validate, load_secret):
        validate.side_effect = ValueError("invalid token")

        result = handler.lambda_handler(
            make_event(
                "POST /research",
                {"token": "bad-token", "invocation_id": "invocation-123"},
            ),
            None,
        )

        self.assertEqual(result["statusCode"], 401)

    @patch.object(handler, "load_signing_secret", return_value=b"x" * 32)
    @patch.object(handler, "validate_and_consume")
    def test_replay_returns_409(self, validate, load_secret):
        validate.side_effect = handler.ReplayDetectedError("replay")

        result = handler.lambda_handler(
            make_event(
                "POST /research",
                {"token": "replayed-token", "invocation_id": "invocation-123"},
            ),
            None,
        )

        self.assertEqual(result["statusCode"], 409)

    @patch.object(handler, "load_signing_secret", return_value=b"x" * 32)
    @patch.object(handler, "validate_and_consume")
    def test_infrastructure_client_error_returns_500(
        self, validate, load_secret
    ):
        from botocore.exceptions import ClientError

        validate.side_effect = ClientError(
            {"Error": {"Code": "InternalServerError", "Message": "test"}},
            "PutItem",
        )

        result = handler.lambda_handler(
            make_event(
                "POST /research",
                {"token": "test-token", "invocation_id": "invocation-123"},
            ),
            None,
        )

        self.assertEqual(result["statusCode"], 500)


if __name__ == "__main__":
    unittest.main()
