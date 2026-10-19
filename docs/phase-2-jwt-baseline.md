@'

\# Phase 2 Checkpoint - Conventional JWT Baseline



\*\*Date:\*\* 19 October 2026  

\*\*Status:\*\* Baseline infrastructure and pilot experiments completed



\## 1. Infrastructure



\- AWS region: `eu-west-1`

\- Authentication: Amazon Cognito User Pool and app client

\- API: API Gateway HTTP API with a JWT authorizer

\- Compute: AWS Lambda using Python 3.12

\- Event storage: Amazon DynamoDB

\- API access logging: Amazon CloudWatch Logs



API Gateway validates JWTs before forwarding authenticated requests to Lambda.



\## 2. Authentication tests



| Test | Observed result |

|---|---|

| Valid Cognito access token | HTTP 200 |

| Missing token | HTTP 401 |

| Malformed token | HTTP 401 |



API Gateway access logs contained successful and rejected request entries.



\## 3. Baseline performance



The 100-request experiment completed with 100 successful HTTP 200 responses.



| Metric | Result |

|---|---:|

| Requests | 100 |

| Successful responses | 100 |

| Mean client-observed latency | 302.520 ms |

| P50 | 283.653 ms |

| P90 | 405.175 ms |

| P95 | 437.601 ms |

| Minimum | 129.005 ms |

| Maximum | 892.064 ms |



Results: `experiments/results/jwt-baseline-100.csv`



The 10-request pilot is preserved separately. These measurements represent client-observed latency, not isolated JWT validation overhead. Cold-start behavior has not been established.



\## 4. Research-event logging limitation



The DynamoDB table `serverless-auth-research-events` contained 138 items, all labelled `FOUNDATION\_TEST` at inspection time. The current Lambda handler uses placeholder risk and token fields. These records must not be treated as a separate JWT-baseline dataset.



The JWT baseline is currently evidenced by the CSV measurements and API Gateway access logs.



\## 5. Next steps



1\. Review and commit the Phase 2 checkpoint and experiment files.

2\. Improve experiment logging and request correlation where needed.

3\. Implement invocation-bound dynamic tokens.

4\. Add expiry and replay protection.

5\. Implement risk scoring and integrate the framework.

6\. Run comparative experiments against the conventional JWT baseline.



\## 6. Reproducibility and security



The baseline script is `experiments/scripts/run-jwt-baseline.ps1`. It reads configuration from Terraform outputs and obtains an access token for the dedicated test user. Do not commit passwords, access tokens, or other secrets.

'@ | Set-Content -Path .\\docs\\phase-2-jwt-baseline.md -Encoding utf8

