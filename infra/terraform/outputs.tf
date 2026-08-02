output "backend_ecr_repository_arn" {
  description = "ARN of the private ECR repository for backend images."
  value       = aws_ecr_repository.backend.arn
}

output "backend_ecr_repository_url" {
  description = "Registry URL used to push and pull backend images."
  value       = aws_ecr_repository.backend.repository_url
}
