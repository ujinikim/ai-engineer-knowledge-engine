# Documentation guide

Start with the [root README](../README.md) for local commands, then use the
links below for the work you are doing. Documents marked **historical** record
earlier decisions or evaluations; they are not current instructions.

## Current references

- [Roadmap](ROADMAP.md) — high-level sequence; confirm status against current code.
- [Architecture](ARCHITECTURE.md), [API design](API_DESIGN.md), and [data sources](DATA_SOURCES.md) — system and source contracts.
- [Product direction](PRODUCT_DIRECTION.md), [project brief](PROJECT_BRIEF.md), and [UI product plan](UI_PRODUCT_PLAN.md) — intended use and interface.
- [Agent source audit](AGENT_SOURCE_AUDIT_2026-09-25.md) — proposed source and filter changes; no configuration applied.
- [Decisions](DECISIONS.md) — design history, including the original documentation prototype.

## Operating guides

- [Collection](runbooks/COLLECTION_RUNBOOK.md), [extraction review](runbooks/EXTRACTION_EVAL_RUNBOOK.md), [summary review](runbooks/SUMMARY_EVAL_RUNBOOK.md), [taxonomy review](runbooks/TAXONOMY_REVIEW_RUNBOOK.md), [feed relevance review](runbooks/FEED_RELEVANCE_REVIEW_RUNBOOK.md), and [retrieval evaluation](runbooks/RETRIEVAL_EVAL_RUNBOOK.md).
- [Deployment plan](DEPLOYMENT_PLAN.md), [EC2 runtime](runbooks/EC2_RUNTIME_RUNBOOK.md), [AWS observability](runbooks/AWS_OBSERVABILITY_RUNBOOK.md), and [application observability](runbooks/OBSERVABILITY_RUNBOOK.md).
- [Terraform instructions](../infra/terraform/README.md) and [demo script](DEMO_SCRIPT.md).

## Historical plans and findings

- [Original documentation pipeline plan](archive/AFTER_COLLECTION_PLAN.md), [quality improvement plan](archive/QUALITY_IMPROVEMENT_PLAN.md), [MVP status snapshot](archive/MVP_STATUS.md), and [evaluation overview](EVALUATION.md).
- [Phase 2 remediation backlog](archive/PHASE2_REMEDIATION_BACKLOG.md), [taxonomy remediation plan](archive/TAXONOMY_REMEDIATION_PLAN.md), and [taxonomy findings](archive/TAXONOMY_REVIEW_FINDINGS_2026-07-26.md).
- [Phase 3 benchmark plan](archive/PHASE3_RETRIEVAL_BENCHMARK_PLAN.md), [baseline findings](archive/PHASE3_RETRIEVAL_BASELINE_FINDINGS_2026-07-27.md), [retrieval upgrades](archive/RETRIEVAL_UPGRADES.md), and [closeout](archive/PHASE3_CLOSEOUT_2026-07-29.md).
- [Original feed relevance proposal](archive/FEED_RELEVANCE_POLICY_PROPOSAL.md) and [August 2026 deployment record](archive/DEPLOYMENT_RECORD_2026-08-04.md).

Evaluation datasets and reports live under [`backend/data/eval/`](../backend/data/eval/). Keep dated baselines when changing sources or article filtering so before/after results remain reproducible. Review generated draft reports separately from reviewed decisions before removing any.
