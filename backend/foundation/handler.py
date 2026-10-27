import json
import os
import time
import uuid

import boto3
from botocore.exceptions import ClientError

from backend.dynamic_auth.replay_store import ReplayDetectedError
from backend.dynamic_auth.issuer import (
    issue_invocation_token_from_environment,
    load_signing_secret,
)
from backend.dynamic_auth.protected_invocation import validate_and_consume

dynamodb = boto3.resource("dynamodb")
events_table = dynamodb.Table(os.environ["RESEARCH_EVENTS_TABLE"])
replay_table = dynamodb.Table(os.environ["REPLAY_STATE_TABLE"])


def response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def authenticated_subject(event):
    """Read the subject only from API Gateway's validated JWT claims."""
    try:
        claims = event["requestContext"]["authorizer"]["jwt"]["claims"]
        subject = claims.get("sub")
        if isinstance(subject, str) and subject:
            return subject
    except (KeyError, TypeError):
        pass

    return None


def parse_json_body(event):
    body = event.get("body")

    if not isinstance(body, str):
        raise ValueError("A JSON request body is required")

    parsed = json.loads(body)

    if not isinstance(parsed, dict):
        raise ValueError("The JSON body must be an object")

    return parsed


def lambda_handler(event, context):
    start_time = time.perf_counter()
    request_id = str(uuid.uuid4())

    route_key = event.get("routeKey", "")
    subject = authenticated_subject(event)

    # JWT authorization should normally reject unauthenticated requests
    # before Lambda invocation. Fail closed if claims are unavailable.
    if not subject:
        return response(
            401,
            {"error": "Authenticated subject is required"},
        )

    if route_key == "POST /token":
        try:
            issued = issue_invocation_token_from_environment(subject)
            return response(200, issued)

        except Exception:
            # Never expose secret material or internal exception details.
            print(
                json.dumps(
                    {
                        "event": "token_issuance_failed",
                        "request_id": request_id,
                    }
                )
            )
            return response(500, {"error": "Token issuance failed"})

    if route_key == "POST /research":
        try:
            try:
                body = parse_json_body(event)
            except (json.JSONDecodeError, ValueError):
                return response(400, {"error": "Invalid request body"})

            token = body.get("token")
            invocation_id = body.get("invocation_id")

            if not isinstance(token, str) or not isinstance(
                invocation_id, str
            ):
                return response(
                    400,
                    {"error": "token and invocation_id are required"},
                )

            secret_name = os.environ.get("SIGNING_SECRET_NAME")
            if not secret_name:
                raise RuntimeError("Signing secret is not configured")

            secret = load_signing_secret(secret_name)

            try:
                claims = validate_and_consume(
                    token=token,
                    secret=secret,
                    expected_invocation_id=invocation_id,
                    expected_subject=subject,
                    dynamodb_table=replay_table,
                )

            except ReplayDetectedError:
                print(
                    json.dumps(
                        {
                            "event": "dynamic_token_replay_rejected",
                            "request_id": request_id,
                        }
                    )
                )
                return response(
                    409,
                    {"error": "Dynamic token has already been used"},
                )

            except ValueError:
                return response(
                    401,
                    {"error": "Dynamic token is invalid or expired"},
                )

            latency_ms = round(
                (time.perf_counter() - start_time) * 1000,
                3,
            )

            item = {
                "experiment_id": "EXP-DYNAMIC",
                "request_id": request_id,
                "scenario": "DYNAMIC_TOKEN",
                "decision": "ALLOW",
                "risk_score": 0,
                "risk_level": "LOW",
                "token_status": "VALID_CONSUMED",
                "replay_detected": False,
                "timestamp": str(time.time()),
                "invocation_id": claims["invocation_id"],
            }

            events_table.put_item(Item=item)

            return response(
                200,
                {
                    "message": "Protected invocation accepted",
                    "request_id": request_id,
                    "experiment_id": item["experiment_id"],
                    "decision": item["decision"],
                    "token_status": item["token_status"],
                    "latency_ms": latency_ms,
                },
            )

        except ClientError:
            print(
                json.dumps(
                    {
                        "event": "research_infrastructure_error",
                        "request_id": request_id,
                    }
                )
            )
            return response(
                500,
                {"error": "Request could not be processed"},
            )

        except Exception:
            print(
                json.dumps(
                    {
                        "event": "research_request_failed",
                        "request_id": request_id,
                    }
                )
            )
            return response(
                500,
                {"error": "Request could not be processed"},
            )

    return response(404, {"error": "Route not found"})