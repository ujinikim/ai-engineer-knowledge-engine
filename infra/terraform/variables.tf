variable "aws_region" {
  description = "AWS region for the application infrastructure."
  type        = string
  default     = "us-east-2"
}

variable "environment" {
  description = "Deployment environment represented by this Terraform state."
  type        = string
  default     = "production"
}

variable "project_name" {
  description = "Stable name used to identify and tag application resources."
  type        = string
  default     = "ai-engineer-knowledge-engine"
}

variable "vpc_cidr" {
  description = "IPv4 CIDR for the application VPC; three non-overlapping /24 subnets are derived from it."
  type        = string
  default     = "10.40.0.0/16"

  validation {
    condition = (
      can(cidrnetmask(var.vpc_cidr)) &&
      can(cidrsubnet(var.vpc_cidr, 8, 11)) &&
      !strcontains(var.vpc_cidr, ":")
    )
    error_message = "vpc_cidr must be an IPv4 CIDR with room for derived /24 subnets, such as 10.40.0.0/16."
  }
}

variable "api_origin_port" {
  description = "FastAPI port reached by CloudFront at the EC2 origin."
  type        = number
  default     = 8000

  validation {
    condition     = var.api_origin_port >= 1 && var.api_origin_port <= 65535
    error_message = "api_origin_port must be a valid TCP port between 1 and 65535."
  }
}

variable "postgresql_port" {
  description = "Private PostgreSQL port allowed between the EC2 and RDS security groups."
  type        = number
  default     = 5432

  validation {
    condition     = var.postgresql_port >= 1 && var.postgresql_port <= 65535
    error_message = "postgresql_port must be a valid TCP port between 1 and 65535."
  }
}

variable "database_name" {
  description = "Initial PostgreSQL database created for the application."
  type        = string
  default     = "knowledge_engine"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,62}$", var.database_name))
    error_message = "database_name must begin with a letter and contain at most 63 letters, numbers, or underscores."
  }
}

variable "database_master_username" {
  description = "Administrative PostgreSQL username; RDS generates and manages its password in Secrets Manager."
  type        = string
  default     = "knowledge_admin"

  validation {
    condition     = can(regex("^[A-Za-z][A-Za-z0-9_]{0,62}$", var.database_master_username))
    error_message = "database_master_username must begin with a letter and contain at most 63 letters, numbers, or underscores."
  }
}

variable "database_engine_version" {
  description = "RDS for PostgreSQL 16 engine version verified as available in the selected region."
  type        = string
  default     = "16.14"

  validation {
    condition     = can(regex("^16\\.[0-9]+$", var.database_engine_version))
    error_message = "database_engine_version must select a PostgreSQL 16 minor release, such as 16.14."
  }
}

variable "database_instance_class" {
  description = "Low-cost RDS instance class for the single-user MVP."
  type        = string
  default     = "db.t4g.micro"

  validation {
    condition     = startswith(var.database_instance_class, "db.")
    error_message = "database_instance_class must be an RDS class beginning with db."
  }
}

variable "database_allocated_storage_gib" {
  description = "Initial gp3 database storage in GiB."
  type        = number
  default     = 20

  validation {
    condition     = var.database_allocated_storage_gib >= 20 && var.database_allocated_storage_gib <= 100
    error_message = "database_allocated_storage_gib must be between 20 and 100 GiB for this MVP."
  }
}

variable "database_max_storage_gib" {
  description = "Maximum storage autoscaling limit in GiB."
  type        = number
  default     = 50

  validation {
    condition     = var.database_max_storage_gib >= 20 && var.database_max_storage_gib <= 100
    error_message = "database_max_storage_gib must be between 20 and 100 GiB for this MVP."
  }
}

variable "database_backup_retention_days" {
  description = "Number of days RDS retains automated backups for point-in-time recovery; the AWS Free plan currently permits one day."
  type        = number
  default     = 1

  validation {
    condition     = var.database_backup_retention_days >= 1 && var.database_backup_retention_days <= 35
    error_message = "database_backup_retention_days must be between 1 and 35 days."
  }
}

variable "backend_image_tag" {
  description = "Immutable 40-character Git commit tag of the backend image to boot on EC2."
  type        = string

  validation {
    condition     = can(regex("^[0-9a-f]{40}$", var.backend_image_tag))
    error_message = "backend_image_tag must be a full lowercase 40-character Git commit SHA."
  }
}

variable "runtime_instance_type" {
  description = "x86 EC2 instance type used by the API and scheduled collector."
  type        = string
  default     = "t3.small"

  validation {
    condition     = startswith(var.runtime_instance_type, "t3.")
    error_message = "runtime_instance_type must use the x86 t3 family while the backend image is linux/amd64."
  }
}

variable "runtime_root_volume_gib" {
  description = "Encrypted gp3 root-volume size for the EC2 runtime."
  type        = number
  default     = 20

  validation {
    condition     = var.runtime_root_volume_gib >= 12 && var.runtime_root_volume_gib <= 100
    error_message = "runtime_root_volume_gib must be between 12 and 100 GiB."
  }
}

variable "openai_api_key_parameter_name" {
  description = "Name of the externally created SecureString containing the production OpenAI API key."
  type        = string
  default     = "/ai-engineer-knowledge-engine/production/openai-api-key"

  validation {
    condition     = startswith(var.openai_api_key_parameter_name, "/ai-engineer-knowledge-engine/")
    error_message = "openai_api_key_parameter_name must stay inside this application's Parameter Store path."
  }
}

variable "runtime_log_retention_days" {
  description = "CloudWatch retention for API and collector container logs."
  type        = number
  default     = 14

  validation {
    condition     = contains([7, 14, 30, 60, 90], var.runtime_log_retention_days)
    error_message = "runtime_log_retention_days must be one of 7, 14, 30, 60, or 90."
  }
}

variable "frontend_noncurrent_version_retention_days" {
  description = "Days to retain superseded frontend objects for deployment recovery."
  type        = number
  default     = 30

  validation {
    condition     = var.frontend_noncurrent_version_retention_days >= 7 && var.frontend_noncurrent_version_retention_days <= 90
    error_message = "frontend_noncurrent_version_retention_days must be between 7 and 90 days."
  }
}

variable "cloudfront_price_class" {
  description = "CloudFront edge-location class; PriceClass_100 limits the MVP to the lowest-cost regions."
  type        = string
  default     = "PriceClass_100"

  validation {
    condition     = contains(["PriceClass_100", "PriceClass_200", "PriceClass_All"], var.cloudfront_price_class)
    error_message = "cloudfront_price_class must be PriceClass_100, PriceClass_200, or PriceClass_All."
  }
}

variable "alarm_notification_email" {
  description = "Optional email address subscribed to operational alarm and recovery notifications."
  type        = string
  default     = null
  nullable    = true

  validation {
    condition = (
      var.alarm_notification_email == null ||
      can(regex("^[^@[:space:]]+@[^@[:space:]]+\\.[^@[:space:]]+$", var.alarm_notification_email))
    )
    error_message = "alarm_notification_email must be null or a valid email address."
  }
}

variable "rds_connection_alarm_threshold" {
  description = "Sustained PostgreSQL connection count that should trigger an operational alarm."
  type        = number
  default     = 60

  validation {
    condition     = var.rds_connection_alarm_threshold >= 10 && var.rds_connection_alarm_threshold <= 500
    error_message = "rds_connection_alarm_threshold must be between 10 and 500."
  }
}
