locals {
  name_prefix = "${var.project_name}-${var.environment}"

  terraform_state_bucket_name = (
    "${local.name_prefix}-terraform-state-${data.aws_caller_identity.current.account_id}"
  )
  backend_repository_name = "${var.project_name}/backend"

  frontend_bucket_name = (
    "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  )
  frontend_origin_id = "${local.name_prefix}-frontend-s3"
}
