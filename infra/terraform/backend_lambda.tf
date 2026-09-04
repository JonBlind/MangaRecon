data "aws_iam_policy_document" "backend_lambda_assume_role" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "backend_lambda" {
  name               = "${local.backend_lambda_function_name}-execution"
  assume_role_policy = data.aws_iam_policy_document.backend_lambda_assume_role.json
}

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/aws/lambda/${local.backend_lambda_function_name}"
  retention_in_days = 30
}

data "aws_iam_policy_document" "backend_lambda_execution" {
  statement {
    sid    = "WriteFunctionLogs"
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents",
    ]

    resources = ["${aws_cloudwatch_log_group.backend.arn}:*"]
  }

  statement {
    sid    = "ReadRuntimeSecret"
    effect = "Allow"

    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.backend_runtime.arn]
  }
}

resource "aws_iam_role_policy" "backend_lambda_execution" {
  name   = "${local.backend_lambda_function_name}-execution"
  role   = aws_iam_role.backend_lambda.id
  policy = data.aws_iam_policy_document.backend_lambda_execution.json
}

data "aws_iam_policy_document" "backend_ecr" {
  statement {
    sid    = "LambdaECRImageRetrievalPolicy"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }

    actions = [
      "ecr:BatchGetImage",
      "ecr:GetDownloadUrlForLayer",
    ]
  }
}

resource "aws_ecr_repository_policy" "backend" {
  repository = aws_ecr_repository.backend.name
  policy     = data.aws_iam_policy_document.backend_ecr.json
}

resource "aws_lambda_function" "backend" {
  function_name = local.backend_lambda_function_name
  role          = aws_iam_role.backend_lambda.arn

  package_type  = "Image"
  image_uri     = "${aws_ecr_repository.backend.repository_url}@${local.backend_image_digest}"
  architectures = ["x86_64"]

  memory_size = 1024
  timeout     = 30

  # Terraform owns the function and runtime configuration. The production
  # workflow owns application-image releases after the bootstrap deployment.
  lifecycle {
    ignore_changes = [image_uri]
  }

  environment {
    variables = {
      AWS_SECRETS_MANAGER_SECRET_ID = aws_secretsmanager_secret.backend_runtime.arn

      MANGARECON_ENV = "prod"
      DEBUG          = "false"

      FRONTEND_ORIGINS   = local.frontend_url
      FRONTEND_URL       = local.frontend_url
      PASSWORD_RESET_URL = "${local.frontend_url}/reset-password"

      MAINTENANCE_MODE                = "false"
      MAINTENANCE_RETRY_AFTER_SECONDS = "300"

      ORIGIN_VERIFY_HEADER_NAME          = "X-MangaRecon-Origin-Verify"
      TRUSTED_CLIENT_ADDRESS_HEADER_NAME = "CF-Connecting-IP"

      EMAIL_DELIVERY_MODE                   = "resend"
      PASSWORD_RESET_TOKEN_LIFETIME_MINUTES = "30"
      RESEND_FROM_EMAIL                     = local.resend_from_email
      RESEND_FROM_NAME                      = "MangaRecon"
      RESEND_API_BASE_URL                   = "https://api.resend.com"
      RESEND_TIMEOUT_SECONDS                = "10"

      DATABASE_POOL_MODE                     = "null"
      DATABASE_CONNECT_TIMEOUT_SECONDS       = "5"
      DATABASE_COMMAND_TIMEOUT_SECONDS       = "15"
      DATABASE_READY_TIMEOUT_SECONDS         = "5"
      DATABASE_PREPARED_STATEMENT_CACHE_SIZE = "0"

      REDIS_CONNECT_TIMEOUT_SECONDS   = "3"
      REDIS_OPERATION_TIMEOUT_SECONDS = "3"
      REDIS_READY_TIMEOUT_SECONDS     = "5"
      REDIS_MAX_CONNECTIONS           = "4"

      ACCOUNT_EMAIL_IP_15_MINUTE_LIMIT         = "5"
      ACCOUNT_EMAIL_IP_DAILY_LIMIT             = "20"
      ACCOUNT_EMAIL_RECIPIENT_COOLDOWN_SECONDS = "60"
      ACCOUNT_EMAIL_RECIPIENT_HOURLY_LIMIT     = "3"
      ACCOUNT_EMAIL_RECIPIENT_DAILY_LIMIT      = "5"
      ACCOUNT_TOKEN_IP_MINUTE_LIMIT            = "10"

      CACHE_TTL_SECONDS       = "3600"
      RATELIMIT_CHECK_SECONDS = "15"

      MANGAUPDATES_BASE_URL                     = "https://api.mangaupdates.com/v1"
      MANGAUPDATES_TIMEOUT_SECONDS              = "10"
      MANGAUPDATES_MIN_REQUEST_INTERVAL_SECONDS = "1"
      MANGAUPDATES_USER_AGENT                   = "MangaRecon/0.1"
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.backend,
    aws_ecr_repository_policy.backend,
    aws_iam_role_policy.backend_lambda_execution,
  ]
}

resource "aws_lambda_function_url" "backend" {
  function_name      = aws_lambda_function.backend.function_name
  authorization_type = "NONE"
  invoke_mode        = "BUFFERED"
}
