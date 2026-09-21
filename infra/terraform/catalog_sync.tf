data "aws_iam_policy_document" "github_actions_catalog_sync_assume_role" {
  statement {
    sid     = "GitHubCatalogSync"
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [aws_iam_openid_connect_provider.github_actions.arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    condition {
      test     = "StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:${var.github_repository}:environment:${var.github_production_environment}",
        "repo:JonBlind@*/MangaRecon@*:environment:${var.github_production_environment}",
      ]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:repository"
      values   = [var.github_repository]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:ref"
      values   = ["refs/heads/main"]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:environment"
      values   = [var.github_production_environment]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:workflow"
      values   = ["Sync MangaUpdates catalog"]
    }
  }
}

resource "aws_iam_role" "github_actions_catalog_sync" {
  name                 = "${local.name_prefix}-github-actions-catalog-sync"
  assume_role_policy   = data.aws_iam_policy_document.github_actions_catalog_sync_assume_role.json
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_actions_catalog_sync" {
  statement {
    sid    = "ReadBackendRuntimeSecret"
    effect = "Allow"

    actions   = ["secretsmanager:GetSecretValue"]
    resources = [aws_secretsmanager_secret.backend_runtime.arn]
  }

  statement {
    sid    = "StoreCatalogCovers"
    effect = "Allow"

    actions   = ["s3:PutObject"]
    resources = ["${aws_s3_bucket.covers.arn}/covers/*"]
  }

  statement {
    sid    = "InspectCatalogCheckpointBucket"
    effect = "Allow"

    actions   = ["s3:ListBucket"]
    resources = [aws_s3_bucket.covers.arn]

    condition {
      test     = "StringEquals"
      variable = "s3:prefix"
      values = [
        "catalog-sync/mangaupdates-backfill-v1.json",
      ]
    }
  }

  statement {
    sid    = "MaintainCatalogCheckpoint"
    effect = "Allow"

    actions = [
      "s3:GetObject",
      "s3:PutObject",
    ]

    resources = [
      "${aws_s3_bucket.covers.arn}/catalog-sync/mangaupdates-backfill-v1.json",
    ]
  }
}

resource "aws_iam_role_policy" "github_actions_catalog_sync" {
  name   = "${local.name_prefix}-catalog-sync"
  role   = aws_iam_role.github_actions_catalog_sync.id
  policy = data.aws_iam_policy_document.github_actions_catalog_sync.json
}
