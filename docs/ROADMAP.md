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

1. Complete the deployment-readiness work in `DEPLOYMENT_PLAN.md`
2. Deploy a staging frontend, API, collector cron job, and pgvector database
3. Run the update-focused retrieval benchmark against staging
4. Launch the initial production MVP with backups, monitoring, and rollback
5. Add story clustering and cross-source deduplication
6. Add contextual `Brief me` synthesis over the active feed
7. Add streaming responses and first-token latency
8. Add followed topics/tools and read, saved, and learning-queue state

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
The ordered evaluation and product phases are captured in `QUALITY_IMPROVEMENT_PLAN.md`.
Deployment topology, sequencing, and launch gates are captured in `DEPLOYMENT_PLAN.md`.
