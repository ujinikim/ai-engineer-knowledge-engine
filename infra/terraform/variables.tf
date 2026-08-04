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
  description = "Number of days RDS retains automated backups for point-in-time recovery."
  type        = number
  default     = 7

  validation {
    condition     = var.database_backup_retention_days >= 1 && var.database_backup_retention_days <= 35
    error_message = "database_backup_retention_days must be between 1 and 35 days."
  }
}
