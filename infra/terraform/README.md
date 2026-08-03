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

The network code does not yet create EC2, Elastic IP, RDS, S3, CloudFront, Parameter
Store parameters, CloudWatch log groups, or alarms.

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

## Validate and review

Run from the repository root:

```bash
terraform -chdir=infra/terraform fmt -check -recursive
terraform -chdir=infra/terraform init
terraform -chdir=infra/terraform validate
terraform -chdir=infra/terraform plan -out=network.tfplan
terraform -chdir=infra/terraform show network.tfplan
```

Plan files and local Terraform working data are ignored by Git. Do not commit a copied
`terraform.tfvars` containing account-specific or sensitive values. The committed
example contains only non-secret defaults.

CI runs formatting, provider-lock, initialization-without-backend, validation, and
mock-provider tests for CIDR derivation, two-AZ placement, ingress boundaries, and
invalid input. It does not assume the production AWS role or apply infrastructure.
Authenticated plan and apply will be added to a protected GitHub environment only
after the deployment role receives separately reviewed infrastructure permissions.

## Apply boundary

Do not apply from this directory merely because validation succeeds. Before the first
long-lived application apply:

1. Review the saved plan and every replacement or deletion.
2. Confirm the AWS estimate and promotional-credit balance.
3. Add RDS, runtime, frontend/CDN, secrets, and observability resources to the same
   reviewed candidate stack.
4. Obtain owner approval for the displayed plan.
