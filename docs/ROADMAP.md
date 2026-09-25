# Roadmap

## Current MVP

- Official multi-source article and release collection
- Structured article summaries and multi-axis taxonomy
- Idempotent update storage and embeddings
- Rolling daily, weekly, and monthly dashboard windows
- Source, source-type, tool, topic, and event filters
- Transparent deterministic ranking
- Time-aware hybrid RAG
- Cited analysis with visible evidence and metrics
- Documentation collection retained separately

## Verification Before MVP Sign-Off

1. Run a fresh collection against all configured feeds.
2. Verify window and facet API behavior against stored releases.
3. Run backend tests and frontend production build.
4. Exercise a grounded update question end to end.
5. Verify desktop and mobile dashboard layouts.

## Next

1. Close the remaining pre-deployment UI acceptance items in `UI_PRODUCT_PLAN.md`
2. Complete deployment readiness
3. Deploy staging and rerun the frozen Phase 3 benchmark with hosted latency
4. Launch the initial production MVP with backups, monitoring, and rollback
5. Add story clustering and cross-source deduplication
6. Add streaming responses and first-token latency
7. Add followed topics/tools and read, saved, and learning-queue state

The main Phase 4 UI redesign, responsive hierarchy, briefing workspace, filter
presentation, and technical-editorial theme are implemented locally. Remaining UI
work is limited to acceptance and portfolio-presentation gaps; it is completed before
the first hosted deployment. Deployment packaging and infrastructure follow that UI
checkpoint.

## Later

1. Selected independent technical publications
2. Research-source ingestion and ranking
3. Historical ranking snapshots
4. Alerts and saved filters
5. Local embedding and answer models
6. Code and research-paper collections
7. Optional LLM relevance classification after calibration warrants the added runtime
8. Optional LLM summary judge after a measured need for ongoing automated grading

Agents, conversational memory, and autonomous browsing remain outside the planned product unless a measured workflow requires them.

The longer-term personal digest and learning-dashboard direction is captured in `PRODUCT_DIRECTION.md`.
The ordered evaluation and product phases are captured in `archive/QUALITY_IMPROVEMENT_PLAN.md`.
Phase 3 question design, metrics, tuning order, and gates are captured in
`archive/PHASE3_RETRIEVAL_BENCHMARK_PLAN.md`.
The completed Phase 3 result and deployment handoff are in
`archive/PHASE3_CLOSEOUT_2026-07-29.md`.
Deployment topology, sequencing, and launch gates are captured in `DEPLOYMENT_PLAN.md`.
The pre-launch interface hierarchy and personal-product direction are captured in
`UI_PRODUCT_PLAN.md`.

## Code organization

The commands are grouped by purpose in `backend/scripts/`; its README identifies
their roles and write behavior. Shared helpers load source configuration and retain
prior human review decisions. The frontend separates API calls, display helpers,
the About view, feed, briefing panel, and styles. The collector keeps orchestration
and storage while `source_extraction.py` handles feed and article parsing.

Feed and search use the same enabled-source and relevance-tier rules. Search also
requires published, substantive article evidence; the feed may show a published
official excerpt. These file moves require no database migration. A fresh local
ingestion and evaluation are still needed before changing source or relevance rules.
