# Application Terraform

This Terraform root owns the single AWS application stack in `us-east-2`. Its remote
state is encrypted, versioned, and locked in the separately bootstrapped S3 bucket.

## Current resources

- Immutable, scan-on-push backend ECR repository
- Repository-scoped GitHub Actions ECR policy
- One application VPC
- One public EC2 subnet
- Two private database subnets in distinct Availability Zones
- Public and private route tables with one Internet Gateway and no NAT Gateway
- An EC2 runtime security group accepting API traffic only from AWS's managed
  CloudFront origin-facing prefix list
- An RDS security group accepting PostgreSQL only from the EC2 security group
- A private single-AZ RDS for PostgreSQL 16 instance with encrypted gp3 storage
- A two-AZ DB subnet group and a PostgreSQL parameter group requiring TLS
- Seven days of automated backups, deletion protection, and a required final snapshot
- An RDS-generated master password managed in AWS Secrets Manager
- One Amazon Linux 2023 `t3.small` EC2 runtime with encrypted gp3 storage
- A stable Elastic IP, an EC2 instance role, and Session Manager administration
- API and collector systemd services plus collector and credential-refresh timers
- Separate API and collector CloudWatch log groups with 14-day retention

The code does not yet create S3, CloudFront, the OpenAI Parameter Store value, or
alarms. Nothing listed above as application infrastructure is live until an
authenticated plan is explicitly applied.

## Address layout

The default `10.40.0.0/16` VPC derives its subnets rather than accepting three
independent values:

| Purpose | Default CIDR | Routing |
|---|---|---|
| EC2 public subnet | `10.40.0.0/24` | `0.0.0.0/0` through the Internet Gateway |
| Database subnet AZ 1 | `10.40.10.0/24` | VPC-local only |
| Database subnet AZ 2 | `10.40.11.0/24` | VPC-local only |

Derivation guarantees that the three subnets are within the VPC and do not overlap.
The first two sorted available Availability Zones are selected consistently.

## Security-group flow

```text
CloudFront managed origin prefix list
        | TCP 8000
        v
EC2 runtime security group
        | TCP 5432
        v
RDS security group
```

EC2 has no SSH ingress. Its outbound rules permit HTTPS for ECR, AWS APIs, OpenAI, and
configured sources; DNS inside the VPC; and PostgreSQL only to the RDS security group.
The RDS security group has no general internet ingress or egress rule.

## Database configuration

The initial database is deliberately small: PostgreSQL `16.14` on `db.t4g.micro`,
20 GiB of gp3 storage, and a 50 GiB autoscaling ceiling. It is single-AZ to control
cost, but its subnet group includes two Availability Zones so RDS can place or recover
the instance within the VPC. `pgvector` is supplied by RDS and enabled later by the
existing Alembic migration, not by Terraform.

Terraform never receives a database password. `manage_master_user_password = true`
asks RDS to generate the password and keep it in Secrets Manager; Terraform records
only the resulting secret ARN. The future runtime must retrieve the current secret
value and assemble `DATABASE_URL` without logging or persisting it. Because RDS-managed
credentials rotate, the runtime deployment must also include a safe credential-refresh
mechanism. The hourly timer reloads both secrets and restarts the API only when their
contents change.

## EC2 runtime

The runtime uses the current Amazon Linux 2023 x86 AMI discovered through AWS's public
Parameter Store path. The x86 `t3.small` matches the published `linux/amd64` backend
image and uses standard CPU credits to avoid unlimited-burst charges. It has no SSH
rule; administration and future deployments use Systems Manager. Containers use
Docker bridge networking and cannot reach the instance metadata credentials.

At first boot, secret-free user data installs Docker and these systemd units:

- `knowledge-engine-api.service` loads secrets, pulls the selected immutable ECR
  image, runs Alembic, and starts FastAPI with a restart policy.
- `knowledge-engine-collector.timer` starts the one-shot collector every six hours.
- `knowledge-engine-secret-refresh.timer` checks hourly for credential changes and
  restarts the API only after a change.

The credentials are written under `/run/knowledge-engine-secrets`, which is memory
backed, readable only by the fixed unprivileged container UID, and mounted read-only at `/run/secrets` in containers.
They do not appear in Terraform, EC2 user data, Docker environment metadata, or the
container image. API and collector stdout use Docker's `awslogs` driver.

## Validate and review

Run from the repository root:

```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan \
  -var='backend_image_tag=<full-existing-git-sha>' \
  -out=deployment.tfplan
terraform -chdir=infra/terraform show deployment.tfplan
```

Plan files and local Terraform working data are ignored by Git. Do not commit a copied
`terraform.tfvars` containing account-specific or sensitive values. The committed
example contains only non-secret defaults.

CI runs formatting, provider-lock, initialization-without-backend, validation, and
mock-provider tests for network boundaries plus database privacy, encryption, storage,
credentials, TLS, backup, and deletion safeguards. It does not assume the production
AWS role or apply infrastructure.
Authenticated plan and apply will be added to a protected GitHub environment only
after the deployment role receives separately reviewed infrastructure permissions.

## Apply boundary

Do not apply from this directory merely because validation succeeds. Before the first
long-lived application apply:

1. Review the saved plan and every replacement or deletion.
2. Confirm the AWS estimate and promotional-credit balance.
3. Add frontend/CDN, the OpenAI SecureString, and remaining observability resources to the same
   reviewed candidate stack.
4. Obtain owner approval for the displayed plan.
