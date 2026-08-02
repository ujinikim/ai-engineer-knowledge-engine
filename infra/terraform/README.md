# Terraform infrastructure

This directory defines the AWS infrastructure for the knowledge engine. Terraform
stores its remote state in the separately bootstrapped, encrypted, versioned S3
bucket `ai-engineer-knowledge-engine-tfstate-422271169214-us-east-2` under the key
`production/terraform.tfstate`.

The application stack currently manages a private ECR repository for immutable,
scan-on-push backend container images. Additional resources will be added by concern
as the deployment progresses.

The state bucket is intentionally not managed by this root module. Terraform needs
the bucket to exist before it can initialize this module, so the bucket's bootstrap
lifecycle remains separate from the application stack.

## Local workflow

Authenticate with temporary AWS Console credentials:

```sh
aws login --profile ai-engineer-admin --region us-east-2
```

Initialize and inspect the configuration without making changes:

```sh
cd infra/terraform
AWS_PROFILE=ai-engineer-admin terraform init
terraform fmt -check
AWS_PROFILE=ai-engineer-admin terraform validate
AWS_PROFILE=ai-engineer-admin terraform plan
```

Do not commit `.terraform/`, state files, saved plan files, AWS credentials, or
application secrets. Commit `.terraform.lock.hcl` so local and CI runs select the
same provider versions.
