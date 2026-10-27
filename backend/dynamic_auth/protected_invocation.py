
from backend.dynamic_auth.tokens import validate_token
from backend.dynamic_auth.replay_store import consume_token


def validate_and_consume(
    token: str,
    secret: bytes,
    expected_invocation_id: str,
    expected_subject: str,
    dynamodb_table,
) -> dict:
    """
    Validate a token and atomically consume its unique ID.

    Returns the validated payload only if both steps succeed.
    """
    payload = validate_token(
        token=token,
        secret=secret,
        expected_invocation_id=expected_invocation_id,
        expected_subject=expected_subject,
    )

    consume_token(
        dynamodb_table=dynamodb_table,
        jti=payload["jti"],
        expires_at=payload["exp"],
    )

    return payload
