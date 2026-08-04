output "backend_ecr_repository_arn" {
  description = "ARN of the private ECR repository for backend images."
  value       = aws_ecr_repository.backend.arn
}

output "backend_ecr_repository_url" {
  description = "Registry URL used to push and pull backend images."
  value       = aws_ecr_repository.backend.repository_url
}

output "vpc_id" {
  description = "Application VPC containing the runtime and database subnets."
  value       = aws_vpc.application.id
}

output "availability_zones" {
  description = "Availability Zones selected deterministically for the initial network."
  value       = local.availability_zones
}

output "public_subnet_id" {
  description = "Public subnet reserved for the EC2 application runtime."
  value       = aws_subnet.public.id
}

output "database_subnet_ids" {
  description = "Private subnet IDs used by the future RDS DB subnet group."
  value       = aws_subnet.database[*].id
}

output "ec2_security_group_id" {
  description = "Security group for the future API and collector EC2 instance."
  value       = aws_security_group.ec2.id
}

output "rds_security_group_id" {
  description = "Security group allowing PostgreSQL only from the EC2 security group."
  value       = aws_security_group.rds.id
}

output "cloudfront_origin_prefix_list_id" {
  description = "AWS-managed CloudFront origin-facing prefix list used by the API ingress rule."
  value       = data.aws_ec2_managed_prefix_list.cloudfront_origin_facing.id
}

output "database_endpoint" {
  description = "Private RDS hostname and port used by the future EC2 runtime."
  value       = aws_db_instance.postgresql.endpoint
}

output "database_name" {
  description = "Initial application database name."
  value       = aws_db_instance.postgresql.db_name
}

output "database_master_username" {
  description = "Administrative username whose password is managed by RDS."
  value       = aws_db_instance.postgresql.username
}

output "database_master_secret_arn" {
  description = "Secrets Manager ARN containing the RDS-managed master credentials; the secret value is never stored in Terraform."
  value       = aws_db_instance.postgresql.master_user_secret[0].secret_arn
}
