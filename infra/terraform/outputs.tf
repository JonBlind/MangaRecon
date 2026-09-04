output "aws_account_id" {
  description = "AWS account receiving MangaRecon resources."
  value       = data.aws_caller_identity.current.account_id
}

output "aws_region" {
  description = "AWS Region receiving MangaRecon resources."
  value       = var.aws_region
}

output "terraform_state_bucket_name" {
  description = "Private S3 bucket used after migrating Terraform state."
  value       = aws_s3_bucket.terraform_state.id
}

output "backend_ecr_repository_name" {
  description = "ECR repository containing backend container images."
  value       = aws_ecr_repository.backend.name
}

output "backend_ecr_repository_url" {
  description = "ECR repository URL used when tagging backend images."
  value       = aws_ecr_repository.backend.repository_url
}

output "backend_runtime_secret_name" {
  description = "Secrets Manager name populated outside Terraform for backend startup."
  value       = aws_secretsmanager_secret.backend_runtime.name
}

output "frontend_bucket_name" {
  description = "Private S3 bucket containing the compiled frontend assets."
  value       = aws_s3_bucket.frontend.id
}

output "frontend_cloudfront_distribution_id" {
  description = "CloudFront distribution used to publish the frontend."
  value       = aws_cloudfront_distribution.frontend.id
}

output "frontend_url" {
  description = "Canonical HTTPS URL for the MangaRecon frontend."
  value       = local.frontend_url
}

output "backend_lambda_function_name" {
  description = "Lambda function running the MangaRecon backend container."
  value       = aws_lambda_function.backend.function_name
}

output "backend_lambda_log_group_name" {
  description = "CloudWatch Logs group receiving backend Lambda logs."
  value       = aws_cloudwatch_log_group.backend.name
}

output "backend_origin_url" {
  description = "Lambda Function URL used only as the Cloudflare Worker origin."
  value       = aws_lambda_function_url.backend.function_url
  sensitive   = true
}

output "github_actions_deploy_role_arn" {
  description = "Short-lived AWS role assumed by the gated production workflow."
  value       = aws_iam_role.github_actions_deploy.arn
}
