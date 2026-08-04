# EC2 Runtime Runbook

## What Terraform prepares

The runtime is one Amazon Linux 2023 EC2 instance running two uses of the same
immutable backend image:

```text
systemd
├── knowledge-engine-api.service       -> FastAPI, continuously restarted
├── knowledge-engine-collector.timer   -> one-shot collector every six hours
└── knowledge-engine-secret-refresh.timer -> credential check every hour
```

The EC2 host uses a stable Elastic IP but has no SSH ingress. Connect through AWS
Systems Manager Session Manager. The instance role can pull only this backend ECR
repository, read only the RDS-managed secret and configured OpenAI parameter, publish
to the two application log groups, and use Systems Manager.

## Secret lifecycle

`knowledge-engine-load-secrets` retrieves the current RDS JSON secret and the OpenAI
SecureString. It URL-encodes the database credentials, requires PostgreSQL TLS, and
writes two mode-`0600` files beneath `/run/knowledge-engine-secrets`:

```text
database_url
openai_api_key
```

`/run` is memory backed. Files are readable only by the container's fixed unprivileged
UID `10001`; containers mount the directory read-only as `/run/secrets`, and Pydantic
reads the files without putting their values in Docker arguments or image layers. The
hourly refresh compares hashes and restarts FastAPI only when a value changes. The
collector reloads secrets before every run.

## Initial deployment prerequisite

Before apply, create this Parameter Store value outside Terraform:

```text
/ai-engineer-knowledge-engine/production/openai-api-key
```

Use type `SecureString`. Do not put its value in a `.tfvars` file or GitHub variable.
The selected `backend_image_tag` must be a full 40-character Git SHA that already
exists in the immutable ECR repository.

## Operations after apply

Start a shell without opening SSH:

```bash
aws ssm start-session --target "$(terraform -chdir=infra/terraform output -raw runtime_instance_id)"
```

Inspect services on the instance:

```bash
sudo systemctl status knowledge-engine-api.service
sudo systemctl list-timers 'knowledge-engine-*'
sudo journalctl -u knowledge-engine-api.service --since today
```

Run collection manually:

```bash
sudo systemctl start knowledge-engine-collector.service
sudo systemctl status knowledge-engine-collector.service
```

Container application output is in CloudWatch Logs. The system journal primarily
records Docker startup, image-pull, migration, and service-control failures.

## Failure behavior

- Missing OpenAI or database credentials: API startup fails visibly in systemd and is
  retried; no placeholder credential is accepted.
- Migration failure: FastAPI does not start against an incompatible schema.
- Collector overlap: systemd prevents duplicate unit execution, while the PostgreSQL
  advisory lock also protects manual or external starts.
- Secret rotation: the hourly refresh reloads the values and restarts the API only
  after a content change.
- Host reboot: persistent timers catch up, Docker starts first, migrations run, and
  FastAPI restarts automatically.
