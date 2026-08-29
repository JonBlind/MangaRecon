locals {
  name_prefix                  = "${var.project_name}-${var.environment}"
  backend_lambda_function_name = "${local.name_prefix}-backend"
  backend_image_digest         = "sha256:f0974dd83a23c93933b3b298201afc40e5d38308e3495405685ed90d0cb784eb"
  resend_from_email            = "noreply@mail.mangarecon.com"
  frontend_url                 = "https://mangarecon.com"

  terraform_state_bucket_name = (
    "${local.name_prefix}-terraform-state-${data.aws_caller_identity.current.account_id}"
  )
  backend_repository_name = "${var.project_name}/backend"

  frontend_bucket_name = (
    "${local.name_prefix}-frontend-${data.aws_caller_identity.current.account_id}"
  )
  frontend_origin_id = "${local.name_prefix}-frontend-s3"
}
