provider "aws" {
  region = var.aws_region
}

# DynamoDB Table

resource "aws_dynamodb_table" "research_events" {
  name         = "serverless-auth-research-events"
  billing_mode = "PAY_PER_REQUEST"

  hash_key  = "experiment_id"
  range_key = "request_id"

  attribute {
    name = "experiment_id"
    type = "S"
  }

  attribute {
    name = "request_id"
    type = "S"
  }

  tags = {
    Project     = "serverless-auth-research"
    Environment = "dev"
    Purpose     = "research-events"
  }
}

resource "aws_iam_role" "lambda_foundation_role" {
  name = "serverless-auth-foundation-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = "serverless-auth-research"
    Environment = "dev"
    Purpose     = "lambda-foundation"
  }
}

resource "aws_iam_role_policy" "lambda_dynamodb_policy" {
  name = "serverless-auth-foundation-dynamodb-policy"
  role = aws_iam_role.lambda_foundation_role.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Action = [
          "dynamodb:PutItem"
        ]

        Resource = aws_dynamodb_table.research_events.arn
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.lambda_foundation_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}


# Lambda Function

resource "aws_lambda_function" "foundation" {
  function_name = "serverless-auth-foundation"

  role = aws_iam_role.lambda_foundation_role.arn

  runtime = "python3.12"
  handler = "handler.lambda_handler"

  filename         = "${path.module}/../../backend/foundation/lambda.zip"
  source_code_hash = filebase64sha256("${path.module}/../../backend/foundation/lambda.zip")

  timeout     = 10
  memory_size = 128

  environment {
    variables = {
      RESEARCH_EVENTS_TABLE = aws_dynamodb_table.research_events.name
    }
  }

  tags = {
    Project     = "serverless-auth-research"
    Environment = "dev"
    Purpose     = "foundation"
  }
}


# API Gateway

resource "aws_apigatewayv2_api" "research_api" {
  name          = "serverless-auth-research-api"
  protocol_type = "HTTP"

  tags = {
    Project     = "serverless-auth-research"
    Environment = "dev"
    Purpose     = "research-api"
  }
}

resource "aws_apigatewayv2_integration" "foundation_lambda" {
  api_id = aws_apigatewayv2_api.research_api.id

  integration_type   = "AWS_PROXY"
  integration_uri    = aws_lambda_function.foundation.invoke_arn
  integration_method = "POST"

  payload_format_version = "2.0"
}


resource "aws_apigatewayv2_route" "foundation_route" {
  api_id = aws_apigatewayv2_api.research_api.id

  route_key = "POST /research"

  target = "integrations/${aws_apigatewayv2_integration.foundation_lambda.id}"

  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito_jwt.id
}


# API Gateway Access Logs

resource "aws_cloudwatch_log_group" "api_access_logs" {
  name              = "/aws/apigateway/serverless-auth-research-access"
  retention_in_days = 14

  tags = {
    Project     = "serverless-auth-research"
    Environment = "dev"
    Purpose     = "api-access-logs"
  }
}



resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.research_api.id

  name        = "$default"
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_access_logs.arn

    format = jsonencode({
      requestId       = "$context.requestId"
      requestTime     = "$context.requestTime"
      routeKey        = "$context.routeKey"
      httpMethod      = "$context.httpMethod"
      status          = "$context.status"
      responseLatency = "$context.responseLatency"
      responseLength  = "$context.responseLength"
    })
  }
}




resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.foundation.function_name
  principal     = "apigateway.amazonaws.com"

  source_arn = "${aws_apigatewayv2_api.research_api.execution_arn}/*/*"
}


# Cognito User Pool - JWT Authentication Baseline

resource "aws_cognito_user_pool" "research_users" {
  name = "serverless-auth-research-users"

  password_policy {
    minimum_length                   = 12
    require_lowercase                = true
    require_numbers                  = true
    require_symbols                  = true
    require_uppercase                = true
    temporary_password_validity_days = 7
  }

  admin_create_user_config {
    allow_admin_create_user_only = true
  }

  tags = {
    Project     = "serverless-auth-research"
    Environment = "dev"
    Purpose     = "jwt-baseline"
  }
}

# Public app client for controlled testing.
# It has no client secret because it is a public client.

resource "aws_cognito_user_pool_client" "research_client" {
  name         = "serverless-auth-research-client"
  user_pool_id = aws_cognito_user_pool.research_users.id

  generate_secret = false

  explicit_auth_flows = [
    "ALLOW_USER_PASSWORD_AUTH",
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_USER_SRP_AUTH"
  ]

  prevent_user_existence_errors = "ENABLED"
}


# JWT Authorizer - Cognito baseline

resource "aws_apigatewayv2_authorizer" "cognito_jwt" {
  api_id          = aws_apigatewayv2_api.research_api.id
  name            = "cognito-jwt-authorizer"
  authorizer_type = "JWT"

  identity_sources = [
    "$request.header.Authorization"
  ]

  jwt_configuration {
    issuer = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.research_users.id}"

    audience = [
      aws_cognito_user_pool_client.research_client.id
    ]
  }
}
