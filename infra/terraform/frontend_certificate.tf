resource "aws_acm_certificate" "frontend" {
  domain_name       = "mangarecon.com"
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}