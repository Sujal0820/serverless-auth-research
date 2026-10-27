
import base64
import hashlib
import hmac
import json
import time
import uuid


def _encode(data: bytes) -> str:
    """Encode bytes as URL-safe Base64 without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    """Decode URL-safe Base64 without padding."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def issue_token(
    secret: bytes,
    invocation_id: str,
    subject: str,
    ttl_seconds: int = 30,
) -> str:
    """Issue a signed token bound to one invocation and one user."""
    if not secret:
        raise ValueError("Signing secret must not be empty")
    if not invocation_id:
        raise ValueError("invocation_id must not be empty")
    if not subject:
        raise ValueError("subject must not be empty")
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive")

    now = int(time.time())
    payload = {
        "jti": str(uuid.uuid4()),
        "invocation_id": invocation_id,
        "sub": subject,
        "iat": now,
        "exp": now + ttl_seconds,
    }

    payload_bytes = json.dumps(
        payload,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    encoded_payload = _encode(payload_bytes)
    signature = hmac.new(
        secret,
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()

    return f"{encoded_payload}.{_encode(signature)}"


def validate_token(
    token: str,
    secret: bytes,
    expected_invocation_id: str,
    expected_subject: str,
) -> dict:
    """Validate signature, expiry, invocation binding, and user binding."""
    if not token or not secret or not expected_invocation_id or not expected_subject:
        raise ValueError(
            "Token, secret, invocation ID, and subject are required"
        )

    try:
        encoded_payload, encoded_signature = token.split(".")
        supplied_signature = _decode(encoded_signature)
        expected_signature = hmac.new(
            secret,
            encoded_payload.encode("ascii"),
            hashlib.sha256,
        ).digest()

        if not hmac.compare_digest(
            supplied_signature,
            expected_signature,
        ):
            raise ValueError("Invalid token signature")

        payload = json.loads(_decode(encoded_payload).decode("utf-8"))

        if not isinstance(payload, dict):
            raise ValueError("Invalid token payload")

        if not isinstance(payload.get("jti"), str) or not payload["jti"]:
            raise ValueError("Invalid token ID")

        if not isinstance(payload.get("iat"), int):
            raise ValueError("Invalid token issue time")

        if not isinstance(payload.get("exp"), int):
            raise ValueError("Invalid token expiry")

        if payload["exp"] <= payload["iat"]:
            raise ValueError("Invalid token lifetime")

        if int(time.time()) >= payload["exp"]:
            raise ValueError("Token expired")

        if payload.get("invocation_id") != expected_invocation_id:
            raise ValueError("Invocation binding mismatch")

        if payload.get("sub") != expected_subject:
            raise ValueError("Subject binding mismatch")

        return payload

    except (
        ValueError,
        TypeError,
        KeyError,
        UnicodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(f"Token validation failed: {exc}") from exc
