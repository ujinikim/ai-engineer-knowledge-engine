# AWS Observability Runbook

## Scope and current state

This runbook covers the first single-stack CloudWatch and SNS monitoring layer.

The design deliberately uses AWS's included service metrics plus three custom metrics:

- `CWAgent/disk_used_percent`, aggregated only by EC2 instance ID
- `ai-engineer-knowledge-engine/Operational/CollectorFailures`
- `ai-engineer-knowledge-engine/Operational/CollectorCompletions`

It does not enable paid EC2 detailed monitoring, CloudFront additional metrics,
Performance Insights, a synthetic canary, or a custom dashboard for the first release.

## Alarms

| Alarm suffix | Signal | Trigger | First check |
|---|---|---|---|
| `cloudfront-5xx` | CloudFront `5xxErrorRate` | Above 5% for 10 minutes | CloudFront behavior, EC2 API logs, and instance status |
| `ec2-status` | EC2 `StatusCheckFailed` | Failed for 2 minutes | EC2 status checks and Systems Manager connectivity |
| `ec2-root-disk` | Agent `disk_used_percent` | Above 85% for 10 minutes | Docker images, container logs, and root-volume usage |
| `collector-failure` | Structured `collection_failed` log | One failure | Collector log stream and safe `exception_type` |
| `collector-stale` | Successful/partial collector completion | None in 12 hours | systemd timer, collector service, database, and source failures |
| `rds-free-storage` | RDS `FreeStorageSpace` | Below 5 GiB for 10 minutes | Database growth and storage autoscaling state |
| `rds-cpu` | RDS `CPUUtilization` | Above 90% for 15 minutes | Queries, collector overlap, and retrieval load |
| `rds-connections` | RDS `DatabaseConnections` | Above 60 for 15 minutes | API processes, leaked sessions, and collector overlap |

Every alarm sends both `ALARM` and recovery (`OK`) transitions to an encrypted SNS
topic in the alarm's Region. Missing data is treated as a problem for runtime,
collector freshness, and RDS signals; CloudFront missing data is acceptable when the
site has no traffic.

## Regions and console locations

Most resources are in `us-east-2`:

- CloudWatch > Alarms > All alarms
- CloudWatch > Log groups > `/ai-engineer-knowledge-engine/production/api`
- CloudWatch > Log groups > `/ai-engineer-knowledge-engine/production/collector`
- SNS > Topics > `ai-engineer-knowledge-engine-production-operational-alerts`

CloudFront metrics and `cloudfront-5xx` are in `us-east-1`, because AWS publishes
global CloudFront metrics only in Northern Virginia. Its actions use the separate
`ai-engineer-knowledge-engine-production-global-operational-alerts` topic in that
Region because a CloudWatch alarm cannot target an SNS topic in another Region.

## Optional email notification

Before the reviewed apply, set the non-secret Terraform variable to the desired
address:

```hcl
alarm_notification_email = "owner@example.com"
```

After apply, AWS sends one confirmation message for each regional topic. Both
subscriptions remain pending and deliver no alarms until both confirmation links are
accepted. The address is ordinary configuration rather than a credential, but it
will be stored in Terraform state.

Leaving the value `null` creates the alarms and SNS topics without a human subscriber.
This is acceptable for the initial infrastructure review, but an address should be
confirmed before the stack is shared publicly.

## Verification after apply

List the regional application alarms:

```bash
aws cloudwatch describe-alarms \
  --region us-east-2 \
  --alarm-name-prefix ai-engineer-knowledge-engine-production-
```

List the global CloudFront alarm:

```bash
aws cloudwatch describe-alarms \
  --region us-east-1 \
  --alarm-name-prefix ai-engineer-knowledge-engine-production-cloudfront-
```

Verify the email subscription and send a harmless topic test only after confirming the
destination:

```bash
aws sns list-subscriptions-by-topic \
  --region us-east-2 \
  --topic-arn "$(terraform -chdir=infra/terraform output -raw operational_alarm_topic_arn)"

aws sns publish \
  --region us-east-2 \
  --topic-arn "$(terraform -chdir=infra/terraform output -raw operational_alarm_topic_arn)" \
  --subject "Knowledge engine alert test" \
  --message "Operational SNS delivery test"

aws sns list-subscriptions-by-topic \
  --region us-east-1 \
  --topic-arn "$(terraform -chdir=infra/terraform output -raw global_operational_alarm_topic_arn)"
```

Verify the agent through Session Manager:

```bash
sudo systemctl status amazon-cloudwatch-agent
sudo tail -n 100 /opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log
```

Do not force real disk, database, or API exhaustion to test alarms. Validate the topic
delivery separately, then inspect alarm history and metrics after normal hosted smoke
tests and the first two collector runs.

## Response order

1. Confirm whether the signal is still breaching and note its start time.
2. Check the related CloudWatch metric and the smallest relevant log group.
3. Use Systems Manager rather than SSH for EC2 inspection.
4. Preserve logs and database state before restarting or changing infrastructure.
5. Prefer an application restart or forward repair over destructive database action.
6. Record the cause, corrective action, and recovery time in the deployment record.
