resource "aws_secretsmanager_secret" "backend_runtime" {
  name = "${local.name_prefix}/backend/runtime"

  description = "Production runtime secrets consumed by the MangaRecon backend."

  recovery_window_in_days = 7

  lifecycle {
    prevent_destroy = true
  }
}
