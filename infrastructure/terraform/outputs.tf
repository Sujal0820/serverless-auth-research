
# Outputs

output "research_events_table_name" {
  description = "DynamoDB table used for structured research events"
  value       = aws_dynamodb_table.research_events.name
}

output "research_api_url" {
  description = "HTTP API endpoint for the research foundation"
  value       = aws_apigatewayv2_stage.default.invoke_url
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for the JWT baseline"
  value       = aws_cognito_user_pool.research_users.id
}

output "cognito_client_id" {
  description = "Public Cognito app client ID for authentication testing"
  value       = aws_cognito_user_pool_client.research_client.id
}

output "cognito_issuer_url" {
  description = "JWT issuer URL for the Cognito User Pool"
  value       = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.research_users.id}"
}
