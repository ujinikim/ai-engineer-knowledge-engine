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
