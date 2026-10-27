import json
import getpass
import urllib.request
import urllib.error
import boto3

REGION = "eu-west-1"
USER_POOL_CLIENT_ID = "3sosvrnk3l384qn86pcgkd9892"
API_BASE = "https://3pvfet7076.execute-api.eu-west-1.amazonaws.com"

cognito = boto3.client("cognito-idp", region_name=REGION)

def authenticate(username):
    password = getpass.getpass(f"Password for {username}: ")
    result = cognito.initiate_auth(
        AuthFlow="USER_PASSWORD_AUTH",
        ClientId=USER_POOL_CLIENT_ID,
        AuthParameters={"USERNAME": username, "PASSWORD": password},
    )
    return result["AuthenticationResult"]["IdToken"]

def post(path, id_token, body=None):
    data = json.dumps(body or {}).encode("utf-8")
    request = urllib.request.Request(
        API_BASE + path,
        data=data,
        headers={
            "Authorization": "Bearer " + id_token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8")

def issue_token(id_token):
    status, body = post("/token", id_token)
    if status != 200:
        raise RuntimeError(
            f"Token issuance failed with HTTP {status}. "
            "Check Cognito authentication and API configuration."
        )
    result = json.loads(body)
    return result["token"], result["invocation_id"]

print("Authenticating both test users; credentials and tokens will not be displayed.")
user1 = authenticate("research-test-user")
user2 = authenticate("research-test-user-2")

# Verify both Cognito sessions are accepted by the protected API.
issue_token(user1)
issue_token(user2)
print("Both Cognito sessions accepted by /token.")

# BIND-001: Fresh token, same authenticated subject, only invocation ID changed.
token, invocation_id = issue_token(user1)
status, _ = post(
    "/research",
    user1,
    {"token": token, "invocation_id": invocation_id + "-wrong"},
)
print(
    f"BIND-001 invocation-ID mismatch: "
    f"{'PASS' if status == 401 else 'FAIL'} (HTTP {status}; expected 401)"
)

# BIND-002: Fresh User 1 token, correct invocation ID, authenticated as User 2.
token, invocation_id = issue_token(user1)
status, _ = post(
    "/research",
    user2,
    {"token": token, "invocation_id": invocation_id},
)
print(
    f"BIND-002 subject mismatch: "
    f"{'PASS' if status == 401 else 'FAIL'} (HTTP {status}; expected 401)"
)
