import json
import os
import time
import uuid

import boto3


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["RESEARCH_EVENTS_TABLE"])


def lambda_handler(event, context):
    start_time = time.perf_counter()

    request_id = str(uuid.uuid4())
    timestamp = str(time.time())

    item = {
        "experiment_id": "EXP-000",
        "request_id": request_id,
        "scenario": "FOUNDATION_TEST",
        "decision": "ALLOW",
        "risk_score": 0,
        "risk_level": "UNKNOWN",
        "token_status": "NOT_IMPLEMENTED",
        "replay_detected": False,
        "timestamp": timestamp,
    }

    table.put_item(Item=item)

    latency_ms = round((time.perf_counter() - start_time) * 1000, 3)

    response = {
        "message": "Serverless authentication research foundation is working",
        "request_id": request_id,
        "experiment_id": item["experiment_id"],
        "decision": item["decision"],
        "latency_ms": latency_ms,
    }

    return {
        "statusCode": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": json.dumps(response),
    }