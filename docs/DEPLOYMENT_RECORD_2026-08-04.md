# AWS Deployment Record — 2026-08-04

## Outcome

The first production AWS deployment is live at:

<https://d13jtdxsfzu68j.cloudfront.net>

The final infrastructure drift check returned `No changes`, the public frontend and
same-origin API returned HTTP 200, FastAPI readiness reported the database reachable,
the schema current, and pgvector installed. All eight operational alarms are `OK`
after the first controlled collection.

## Deployed shape

- Region `us-east-2`: VPC, one public runtime subnet, two private database subnets,
  `t3.small` EC2, private encrypted `db.t4g.micro` PostgreSQL 16 RDS, Elastic IP,
  private versioned frontend S3 bucket, application log groups, regional SNS topic,
  and seven regional alarms.
- Region `us-east-1`: CloudFront's global 5xx alarm and its encrypted regional SNS
  topic.
- Global: CloudFront distribution `E2TXTMJ9BWUHDO` with private S3 as the static
  origin and `/api/*` routed uncached to FastAPI.
- Backend image:
  `1b6d24f0af7bf6927f618ffdb1eddeced02be73d`.
- Runtime instance after bootstrap repair: `i-0544cf3a88fc41846`.

RDS is not publicly accessible. PostgreSQL permits connections only from the runtime
security group. The API origin permits inbound port 8000 only from AWS's managed
CloudFront origin-facing prefix list. Administration uses Systems Manager rather than
SSH.

## First-deployment corrections

1. The account's AWS Free plan rejected seven-day RDS backup retention. The default
   was reduced to one day, retaining automated point-in-time recovery within the plan
   restriction. The Terraform variable still permits 1–35 days after an account-plan
   upgrade.
2. CloudFront metrics and alarms live in `us-east-1`; an alarm there could not use the
   original `us-east-2` SNS action. A second encrypted `us-east-1` topic was added for
   the global alarm, while application alarms retained the regional topic.
3. The RDS-managed secret contained only `username` and `password`, not host and port.
   Runtime bootstrap now combines those secret fields with the non-secret RDS address
   and port supplied by Terraform. The initially failed EC2 host was replaced, while
   RDS and all durable infrastructure were preserved and the same Elastic IP was
   reattached.
4. AWS/provider normalization for Elastic IP association, the default CloudFront
   certificate, and the static RDS parameter caused a false recurring repair plan.
   Configuration was aligned with AWS's returned representation; the subsequent live
   plan was clean.

## Content promotion

The local PostgreSQL corpus was streamed atomically through a temporary Systems
Manager port-forwarding session into private RDS. The database port was never made
public, and no dump was committed or uploaded to S3. The tunnel was closed and the
local PostgreSQL container stopped after verification.

Pre-collection production verification:

- 18 documentation records and 145 documentation chunks
- 240 reviewed release records and 1,134 release chunks
- 17 update-source records
- 0 orphan chunks
- frozen release-corpus hash
  `d12684ca90a0651eb3d80638d12b17df745ac780b9c3fefac5b86737db5eda73`

The count and hash exactly matched the frozen Phase 3 snapshot before live collection.

## Controlled collection and activation

The first collector run executed while the timer remained disabled:

- 17 sources processed
- 75 updates created
- 16 updates changed
- 94 updates unchanged
- 526 chunks written
- 0 errors
- duration: 616,959 ms
- estimated model cost: `$0.123639`

Post-run automated quality checks:

- summaries: 260 pass, 55 warning, 0 fail
- extraction: 285 pass, 30 warning, 0 fail

Warnings were dominated by the already-known OpenAI News hydration/excerpt limitation,
source-content incompleteness, and low lexical grounding. Sparse/incomplete records
remain governed by visibility metadata rather than being deleted. With zero collection
or quality failures, `knowledge-engine-collector.timer` was enabled. It runs every six
hours with up to 15 minutes of randomized delay and PostgreSQL advisory-lock overlap
protection.

## Hosted verification

- Frontend GitHub Actions deployment succeeded:
  <https://github.com/ujinikim/ai-engineer-knowledge-engine/actions/runs/30887091261>
- Latest Terraform validation succeeded:
  <https://github.com/ujinikim/ai-engineer-knowledge-engine/actions/runs/30887263242>
- Public frontend returned HTTP 200.
- `/api/health` returned `ok`.
- `/api/health/ready` reported database reachable, schema current, and pgvector
  installed.
- Hybrid source-balanced retrieval returned five hosted results.
- Default 300-token RAG answer completed with one citation, no warnings, and an
  estimated request cost of `$0.001279`.
- The default feed contained 263 visible updates after collection; the remaining
  stored release records are subject to the reviewed visibility/sparse policy.

## Pinned next task — not started

Run the frozen Phase 3 retrieval benchmark against the hosted AWS application and
compare relevance, exact recall, answer behavior, latency, and cost with the frozen
local baseline. Do not begin this benchmark until the deployment walkthrough is
complete and the owner explicitly resumes it.

## Non-blocking follow-ups

- Add and confirm email subscriptions for both SNS topics if direct alert delivery is
  desired. The alarms are live but currently have no human subscriber.
- Update GitHub Actions' Node runtime from 20 to 24; GitHub currently performs the
  compatibility upgrade automatically and emits a deprecation annotation.
- Add the protected Terraform plan/apply workflow after the first local apply has been
  fully reviewed.
- Consider a custom domain and ACM certificate later; the generated CloudFront domain
  is sufficient for the current side-project deployment.
