
import concurrent.futures
import time
import uuid

import boto3
from botocore.exceptions import ClientError


REGION = "eu-west-1"
TABLE_NAME = "serverless-auth-replay-state"
ATTEMPTS = 10


def main():
    dynamodb = boto3.resource("dynamodb", region_name=REGION)
    table = dynamodb.Table(TABLE_NAME)

    # All concurrent requests use the same unique token ID.
    test_jti = f"concurrency-test-{uuid.uuid4()}"
    expires_at = int(time.time()) + 3600

    def attempt_consume(_):
        try:
            table.put_item(
                Item={
                    "jti": test_jti,
                    "expires_at": expires_at,
                },
                ConditionExpression="attribute_not_exists(jti)",
            )
            return "ACCEPTED"
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code == "ConditionalCheckFailedException":
                return "REJECTED_REPLAY"
            return f"ERROR:{code}"

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=ATTEMPTS
    ) as executor:
        results = list(executor.map(attempt_consume, range(ATTEMPTS)))

    accepted = results.count("ACCEPTED")
    rejected = results.count("REJECTED_REPLAY")
    errors = [result for result in results if result.startswith("ERROR:")]

    print(f"Attempts: {ATTEMPTS}")
    print(f"Accepted: {accepted}")
    print(f"Rejected as replay: {rejected}")
    print(f"Other errors: {errors}")
    print(f"Test jti: {test_jti}")

    if accepted == 1 and rejected == ATTEMPTS - 1 and not errors:
        print("PASS: only one concurrent attempt was accepted.")
    else:
        print("FAIL: unexpected result; inspect the output before continuing.")


if __name__ == "__main__":
    main()
