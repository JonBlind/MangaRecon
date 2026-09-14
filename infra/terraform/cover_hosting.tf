resource "aws_s3_bucket" "covers" {
  bucket        = local.cover_bucket_name
  force_destroy = false
}

resource "aws_s3_bucket_ownership_controls" "covers" {
  bucket = aws_s3_bucket.covers.id

  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_public_access_block" "covers" {
  bucket = aws_s3_bucket.covers.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "covers" {
  bucket = aws_s3_bucket.covers.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_cloudfront_origin_access_control" "covers" {
  name                              = "${local.name_prefix}-covers"
  description                       = "Restrict MangaRecon cover images to CloudFront."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

data "aws_iam_policy_document" "cover_bucket" {
  statement {
    sid    = "AllowCloudFrontReadOnly"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.covers.arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "covers" {
  bucket = aws_s3_bucket.covers.id
  policy = data.aws_iam_policy_document.cover_bucket.json
}
