terraform {
  backend "s3" {
    bucket       = "ai-engineer-knowledge-engine-tfstate-422271169214-us-east-2"
    key          = "production/terraform.tfstate"
    region       = "us-east-2"
    encrypt      = true
    use_lockfile = true
  }
}
