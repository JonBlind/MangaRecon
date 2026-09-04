variable "aws_region" {
  description = "AWS Region used by the MangaRecon production stack."
  type        = string
  default     = "us-east-1"

  validation {
    condition     = var.aws_region == "us-east-1"
    error_message = "MangaRecon currently deploys in us-east-1."
  }
}

variable "project_name" {
  description = "Lowercase project identifier used in AWS resource names."
  type        = string
  default     = "mangarecon"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,31}$", var.project_name))
    error_message = "project_name must be 3-32 lowercase letters, digits, or hyphens."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "prod"

  validation {
    condition     = contains(["dev", "staging", "prod"], var.environment)
    error_message = "environment must be dev, staging, or prod."
  }
}

variable "github_repository" {
  description = "Exact GitHub owner/repository allowed to deploy MangaRecon."
  type        = string
  default     = "JonBlind/MangaRecon"

  validation {
    condition     = var.github_repository == "JonBlind/MangaRecon"
    error_message = "Production deployment is restricted to JonBlind/MangaRecon."
  }
}

variable "github_production_environment" {
  description = "GitHub environment required by the AWS deployment trust policy."
  type        = string
  default     = "production"

  validation {
    condition     = var.github_production_environment == "production"
    error_message = "The production deployment environment must be named production."
  }
}
