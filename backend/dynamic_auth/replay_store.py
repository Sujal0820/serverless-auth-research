
from botocore.exceptions import ClientError


class ReplayDetectedError(Exception):
    """Raised when a dynamic token has already been consumed."""


def consume_token(
    dynamodb_table,
    jti: str,
    expires_at: int,
) -> None:
    """
    Atomically record a token as consumed.

    Raises ReplayDetectedError if the jti already exists.
    Other DynamoDB errors propagate to the caller.
    """
    if not jti:
        raise ValueError("jti must not be empty")

    if expires_at <= 0:
        raise ValueError("expires_at must be positive")

    try:
        dynamodb_table.put_item(
            Item={
                "jti": jti,
                "expires_at": expires_at,
            },
            ConditionExpression="attribute_not_exists(jti)",
        )
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")

        if error_code == "ConditionalCheckFailedException":
            raise ReplayDetectedError(
                "Dynamic token has already been consumed"
            ) from exc

        raise
