
import base64
import os
import uuid

import boto3

from backend.dynamic_auth.tokens import issue_token


def load_signing_secret(
    secret_name: str,
    secrets_client=None,
) -> bytes:
    """Load and decode the HMAC key from AWS Secrets Manager."""
    if not secret_name:
        raise ValueError("Secret name must not be empty")

    if secrets_client is None:
        secrets_client = boto3.client("secretsmanager")

    response = secrets_client.get_secret_value(SecretId=secret_name)
    secret_string = response.get("SecretString")

    if not secret_string:
        raise ValueError("Signing secret has no SecretString")

    try:
        secret = base64.b64decode(secret_string, validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("Signing secret is not valid Base64") from exc

    if len(secret) < 32:
        raise ValueError("Signing secret must contain at least 32 bytes")

    return secret


def issue_invocation_token(
    subject: str,
    secret: bytes,
    ttl_seconds: int = 30,
) -> dict:
    """Issue a short-lived token bound to a server-generated invocation ID."""
    if not subject:
        raise ValueError("Authenticated subject must not be empty")

    invocation_id = str(uuid.uuid4())

    token = issue_token(
        secret=secret,
        invocation_id=invocation_id,
        subject=subject,
        ttl_seconds=ttl_seconds,
    )

    return {
        "invocation_id": invocation_id,
        "token": token,
        "expires_in": ttl_seconds,
    }


def issue_invocation_token_from_environment(subject: str) -> dict:
    """Load the configured secret and issue a token for an authenticated user."""
    secret_name = os.environ.get("SIGNING_SECRET_NAME")

    if not secret_name:
        raise RuntimeError("SIGNING_SECRET_NAME is not configured")

    secret = load_signing_secret(secret_name)

    return issue_invocation_token(
        subject=subject,
        secret=secret,
    )
