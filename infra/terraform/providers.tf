provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Application = "MangaRecon"
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

data "aws_caller_identity" "current" {}
