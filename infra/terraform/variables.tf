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
