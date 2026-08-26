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
