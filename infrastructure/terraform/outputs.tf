# Outputs

output "research_events_table_name" {
  description = "DynamoDB table used for structured research events"
  value       = aws_dynamodb_table.research_events.name
}

output "research_api_url" {
  description = "HTTP API endpoint for the research foundation"
  value       = aws_apigatewayv2_stage.default.invoke_url
}