# Deployment Plan

## Recommendation

Deploy the MVP as one deliberately small AWS stack:

- CloudFront as the single public HTTPS entry point
- A private S3 bucket for the built Vite frontend, readable only through CloudFront
- One EC2 instance for the FastAPI container and the scheduled collector
- One single-AZ RDS PostgreSQL 16 instance with `pgvector` in private subnets
- ECR for the backend image
- Systems Manager Parameter Store for runtime secrets and Systems Manager Session
  Manager for administration
- CloudWatch logs, metrics, alarms, and an AWS Budget for operating visibility
- Terraform for infrastructure and GitHub Actions with OIDC for delivery

Use the same stack for staging-like acceptance and the first production release. Do
not pay for a permanently duplicated staging environment while the project has one
developer and no production users.

This architecture is intentionally more hands-on than a platform-as-a-service. It
provides useful exposure to AWS networking, IAM, compute, storage, database,
observability, infrastructure as code, and keyless CI/CD without introducing services
that the current load does not justify.

## Target Topology

```text
Browser
  |
  | HTTPS
  v
CloudFront
  |-- default behavior --> private S3 frontend through OAC
  `-- /api/* -----------> EC2 FastAPI origin
                              |
                              | PostgreSQL, security-group scoped
                              v
                         private RDS PostgreSQL + pgvector

GitHub Actions -- OIDC --> AWS deployment role
  |-- Terraform plan/apply
  |-- build and push backend image to ECR
  `-- upload frontend build to S3 and invalidate CloudFront

EC2 systemd timer --> one-shot collector every six hours
EC2/collector -----> OpenAI and configured sources through Internet Gateway
```

### Network layout

- Region: `us-east-2` (Ohio).
- One VPC spanning two Availability Zones.
- One public subnet for EC2.
- Two private database subnets, one per Availability Zone, as required for the RDS DB
  subnet group. The initial database remains single-AZ.
- One Internet Gateway. EC2 receives a stable Elastic IP for outbound access and the
  CloudFront custom origin.
- No NAT Gateway. RDS does not need outbound internet access, and EC2 can reach OpenAI,
  source feeds, ECR, and AWS APIs through its public route.
- No inbound SSH. Administration uses Session Manager.
- The EC2 security group accepts origin traffic only from the AWS-managed CloudFront
  origin-facing prefix list. The RDS security group accepts port 5432 only from the
  EC2 security group.

CloudFront uses Origin Access Control (OAC) with always-signed requests for S3. The S3
bucket keeps Block Public Access enabled. The API behavior disables caching, permits
the required HTTP methods, and forwards only the headers and query strings the API
needs.

For the first CloudFront-domain validation, CloudFront-to-EC2 traffic may use HTTP
behind the CloudFront prefix-list restriction and an origin-only header. This is a
documented bootstrap tradeoff, not the desired long-term public boundary. Before a
custom public launch, attach a domain and terminate verified TLS at the API origin, or
replace the public custom origin with a private/VPC-origin design.

## Deliberate Exclusions

Do not add these to the first release:

- NAT Gateway
- Application Load Balancer
- ECS, EKS, or Kubernetes
- Aurora or Multi-AZ RDS
- bastion host or inbound SSH
- ElastiCache, SQS, or a separate worker fleet
- AWS Organizations, Control Tower, or IAM Identity Center
- a second permanent staging stack

These can be reconsidered from observed reliability, security, or load requirements.
They are not prerequisites for a credible side-project deployment.

## Placement in the Phase Plan

Deployment remains Phase 4, after the accepted local retrieval benchmark:

1. Phase 2 established trustworthy extraction, summaries, taxonomy, and visibility
   metadata.
2. Phase 3 established retrieval behavior against a frozen local corpus snapshot.
3. Phase 4A completes and freezes the public UI.
4. Phase 4B makes the repository and AWS infrastructure reproducibly deployable.
5. Phase 4C validates the single hosted stack as a staging candidate.
6. Phase 4D promotes that verified stack to the public MVP and observes it.

Production relevance automation remains deferred and is not a deployment blocker.

## Phase 4A: Pre-Deployment UI

**Status on July 30, 2026:** substantially complete locally.

Finish the P0 acceptance work in `UI_PRODUCT_PLAN.md`, run the production build and
responsive checks, and commit the accepted interface before provisioning application
infrastructure. The first hosted validation should exercise the interface intended for
public review, not an obsolete dashboard.

## Phase 4B: Deployment Readiness

### Repository and Terraform bootstrap

- Publish the cleaned repository to GitHub.
- Add the GitHub OIDC identity provider and a deployment role whose trust policy is
  restricted to this repository and approved branch/environment.
- Bootstrap an encrypted, versioned S3 Terraform-state bucket separately from the
  application stack.
- Use Terraform's S3 lockfile (`use_lockfile = true`); do not add the deprecated
  DynamoDB locking pattern.
- Keep account ID, region, names, and non-secret configuration in variables. Never put
  application secret values in Terraform variables or state.
- Structure Terraform by concern: state bootstrap, IAM/OIDC, network, database,
  compute/runtime, frontend/CDN, and observability.

### Application packaging

- Add a reproducible backend container and push immutable commit-SHA tags to ECR.
- Run the API container under systemd or Docker Compose on EC2 with restart and health
  policies.
- Build the Vite frontend with `npm ci` and `npm run build`, then upload `dist/` to S3.
- Add an `/api` deployment boundary without breaking local tests, so CloudFront can
  route `/api/*` to FastAPI while the default behavior serves the frontend.
- Use the same backend image for the API and one-shot collector.

### Database lifecycle

- Replace production dependence on `docker-entrypoint-initdb.d/init.sql` with an
  Alembic baseline migration.
- Enable `vector` through a migration or a documented one-time bootstrap.
- Keep schema migration separate from reviewed-corpus import and collection.
- Test an empty-database upgrade and an upgrade from a copy of the current local schema.
- Start with PostgreSQL 16, encrypted storage, automated backups, deletion protection,
  and a final-snapshot requirement.

### Runtime configuration and secrets

- Require `DATABASE_URL`, `OPENAI_API_KEY`, and explicit production `CORS_ORIGINS`.
- Store secrets as Parameter Store `SecureString` values created outside Terraform;
  Terraform manages only names and IAM access.
- Give the EC2 instance role read access only to this application's parameter path,
  ECR pull access, CloudWatch publishing, and Session Manager.
- Set frontend `VITE_API_URL` to `/api` at build time.
- Fail startup clearly when required configuration is absent.
- Never place the OpenAI key or database URL in frontend variables, AMIs, user data,
  logs, GitHub secrets, or Terraform state.

### Health, collection, and observability

- Add `/health/live` for process health.
- Add `/health/ready` for database connectivity and required schema/extension checks.
- Keep OpenAI calls out of readiness so provider failure does not restart the API.
- Run the collector as one command from a systemd timer every six hours, not as the
  local infinite interval loop.
- Add a PostgreSQL advisory lock or job lease to prevent overlapping manual and timed
  collection.
- Emit structured API and collector logs to CloudWatch with retention limits.
- Record collection start/end, partial source failures, document/chunk counts, token
  use, estimated model cost, and final status.
- Alarm on instance/API unavailability, repeated collector failure, low disk space,
  high RDS storage/connection pressure, and unexpected gross AWS spend.

### CI/CD

- Pull requests run backend tests, Ruff, frontend production build, Terraform format,
  validation, and plan.
- Merges to `main` build and push the backend image, apply reviewed Terraform changes,
  migrate the database, restart the API, publish the frontend, invalidate CloudFront,
  and run smoke checks.
- GitHub obtains short-lived AWS credentials through OIDC. Do not store AWS access keys
  as repository secrets.
- Protect the production GitHub environment and require approval before infrastructure
  apply or database migration once the public MVP is live.
- Record deployed commit SHA, image digest, migration revision, taxonomy policy, and
  summary prompt/model version.

## Phase 4C: Single-Stack Hosted Validation

1. Apply the smallest candidate stack in Ohio.
2. Apply migrations and verify `vector` and the required schema.
3. Import one reviewed corpus snapshot rather than regenerating every embedding and
   summary during infrastructure validation.
4. Deploy the API and frontend through the same workflow intended for production.
5. Exercise update windows, facets, maturity/sparse visibility, retrieval, answers,
   citations, error states, and the About view.
6. Confirm CloudFront serves S3 privately and the API origin rejects general public
   ingress outside the intended boundary.
7. Verify exact CORS behavior, idempotent redeployment, one manual collection, and one
   timed collection.
8. Rerun the frozen Phase 3 retrieval cases. Correctness must match the accepted local
   result; hosted latency is recorded separately.
9. Test application rollback and document database restore steps.

Treat this as staging even though it is the eventual production stack. Do not share it
broadly until every acceptance item passes.

## Phase 4D: Production Promotion

- Freeze the verified Terraform plan and application revision.
- Confirm the actual AWS estimate and available promotional-credit balance before
  leaving resources running continuously.
- Tighten CORS and CloudFront behaviors to the final HTTPS origin.
- Add a custom domain only after the generated CloudFront domain is stable. CloudFront
  certificates are requested in `us-east-1` even though the application runs in
  `us-east-2`.
- Enable the six-hour timer and all agreed alarms.
- Observe two collection cycles and 48 hours of API health, latency, errors, RDS
  growth, and OpenAI/AWS spend.
- Keep the deployment small until measured traffic or reliability requirements justify
  scaling.

## Ordered Execution Checklist

### Gate 0: Freeze the deployment candidate

- Commit the accepted UI and the reconciled AWS plan.
- Run backend tests and a clean frontend production build.
- Record the candidate commit SHA.

### Gate 1: Establish keyless delivery

- Create the public GitHub repository and push cleaned `main`.
- Create the GitHub OIDC provider and repository-scoped AWS role.
- Prove a read-only workflow can call `sts:GetCallerIdentity`.
- Bootstrap encrypted/versioned Terraform state with S3 lockfile support.

**Progress on August 2, 2026:** the public repository, GitHub OIDC provider,
repository-and-main-restricted role, remote Terraform state, and ECR repository are
complete. The manually triggered
`aws-oidc-smoke.yml` workflow successfully exchanged an OIDC token and called
`sts:GetCallerIdentity`. Terraform now manages a repository-scoped inline ECR policy,
and the backend image workflow has used it to publish and scan an immutable image.
The official GitHub actions are pinned to immutable commits, and the role ARN and
region are repository variables rather than secrets.

GitHub repositories created after July 15, 2026 use immutable OIDC subjects containing
the owner and repository IDs. The IAM trust uses that exact ID-bound subject plus the
`main` branch and `sts.amazonaws.com` audience. The original name-only trust failed
closed, and CloudTrail supplied the exact subject needed for the corrected policy. The
keyless delivery gate is complete.

### Gate 2: Make the repository deployable

- Add migrations, configuration validation, health endpoints, container packaging,
  one-shot collector locking, structured logging, Terraform, and CI.
- Pass tests, builds, Terraform validation/plan, and local migration checks.

**Progress on August 3, 2026:** backend container packaging, immutable ECR publishing,
scan gating, the Alembic baseline, explicit production configuration validation,
split liveness/readiness endpoints, PostgreSQL advisory locking for collector overlap
protection, and structured API/collector JSON logging are complete. Logs include safe
request/run correlation, controlled failure types, document/chunk counts, returned
token usage, and model-cost estimates without prompts, source bodies, credentials, or
raw exceptions. CI exercises a clean pgvector database, legacy-schema adoption,
downgrade/re-upgrade, real readiness and collector-lock checks, tests, and the
production container build. Gate 2 is complete; long-lived application resources can
now be planned and reviewed.

Do not create long-lived application resources until Gate 2 passes.

### Gate 3: Validate the AWS stack

- Apply the single candidate stack.
- Migrate, import the reviewed corpus, deploy, and run hosted smoke and retrieval tests.
- Test redeploy, rollback, collector idempotency, alarms, and restore documentation.

### Gate 4: Promote and observe

- Approve actual displayed AWS costs and start continuous operation.
- Tighten public boundaries, optionally attach a domain, and enable the timer.
- Observe for 48 hours before expanding scope or instance size.

## Owner Inputs

Owner input is limited to external access, secrets, and spending:

1. Approve GitHub repository visibility and the initial push.
2. Create the production-scoped OpenAI API key and store it directly in Parameter
   Store when requested.
3. Approve the AWS estimate immediately before the first long-lived Terraform apply.
4. Provide a custom domain later if desired; it is not a validation blocker.

No additional taxonomy or retrieval decisions are required for deployment.

## Rollback and Recovery

- Application rollback: redeploy the preceding immutable ECR image and frontend build.
- Infrastructure rollback: review a new Terraform plan; never blindly reverse an apply.
- Migration recovery: prefer forward repair and take an RDS snapshot before destructive
  schema changes.
- Data recovery: restore automated/manual RDS snapshots into a replacement instance and
  repoint the runtime after verification.
- Collection recovery: rerun the idempotent one-shot collector after resolving the
  source or provider failure.
- Model regression: pin the prior prompt/model policy and regenerate only an evaluated
  target set before any full backfill.

## Security and Cost Controls

- Root MFA, no root access keys, IAM administrator MFA, alternate contacts, Free Tier
  alerts, and gross-cost AWS Budgets are prerequisites and are complete.
- Human local CLI access uses `aws login` temporary credentials; CI uses GitHub OIDC.
- Keep RDS private, S3 private, SSH closed, and security-group references narrow.
- Encrypt S3, EBS, RDS, Parameter Store secrets, and Terraform state.
- Put request-size, timeout, and basic rate limits around `/api/ask` before broad
  sharing.
- Limit logs so prompts, credentials, database URLs, and complete source documents are
  not emitted.
- Configure retention instead of keeping verbose logs indefinitely.
- Keep the gross-cost budget thresholds already configured and add OpenAI project
  limits before public use.
- AWS promotional credits reduce the bill, not resource consumption. Destroy unused
  resources promptly and verify current prices before apply.

## Phase 4 Acceptance Criteria

- The cleaned repository is public without credentials or reproduced article bodies.
- GitHub deploys through repository-scoped OIDC without AWS access-key secrets.
- Terraform state is encrypted, versioned, locked, and excluded from Git.
- A clean database reaches the current schema through migrations alone.
- API readiness verifies database access and the required schema/extensions.
- CloudFront serves the private S3 frontend and routes `/api/*` correctly.
- RDS is not publicly accessible; EC2 has no inbound SSH.
- One scheduled collector run completes and a second creates no duplicates.
- Filters, sparse visibility, retrieval, answers, citations, and error states pass the
  hosted smoke test.
- Backend tests, frontend build, and Terraform checks pass from a clean checkout.
- Monitoring detects API and collector failures, and recovery steps are exercised.
- Hosted retrieval correctness matches the accepted local benchmark.

## Later Platform Reconsideration

Reconsider the initial topology only after measured need:

- Add an ALB and multiple private API instances when uptime or traffic requires it.
- Move the API to ECS/Fargate when container orchestration saves more work than it adds.
- Add NAT/VPC endpoints only when private compute becomes a justified security boundary.
- Add Multi-AZ RDS when recovery requirements justify the ongoing cost.
- Add SQS/workers when collection or answer jobs outgrow one instance.
- Add a separate staging stack when multiple contributors or release frequency makes
  shared validation unsafe.

These are evidence-driven upgrades, not prerequisites for the first usable deployment.

## Primary References

- AWS CloudFront OAC for private S3 origins:
  https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html
- AWS CloudFront origin-facing managed prefix list:
  https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/LocationsOfEdgeServers.html
- GitHub OIDC for AWS:
  https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws
- Terraform S3 backend and lockfile:
  https://developer.hashicorp.com/terraform/language/backend/s3
