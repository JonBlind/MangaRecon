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
