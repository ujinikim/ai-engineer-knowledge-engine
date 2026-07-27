# MVP Status

Last validated: July 27, 2026

## Complete

- Quality-tiered article and release collection from seventeen AI engineering sources
- Ingestion-time structured summaries and multi-axis categorization
- Idempotent update storage, chunking, OpenAI embeddings, and pgvector indexing
- Daily, weekly, monthly, and all-time update windows
- Tool, topic, event, source-type, maturity, and source filtering
- Deterministic update ranking using credibility, freshness, detail, and maturity
- Hybrid retrieval with semantic, keyword, and recency signals
- Filtered RAG analysis with source citations and citation validation
- Retrieval, latency, token, and estimated-cost diagnostics
- Responsive React dashboard for browsing and analyzing updates
- FastAPI endpoints for health, sources, updates, search, and answers

## Current Data

- 15 RSS or Atom sources and 2 configured HTML-listing sources
- 240 stored and summarized story or release records across 17 sources
- 0 collector source errors in the latest run
- Targeted source-boundary recollection completed for The Batch, Import AI, Anthropic, and GitHub Changelog

## Validation

- Backend tests: 77 passed
- Backend lint: Ruff passed
- Frontend TypeScript and production build: passed
- Desktop layout: validated at 1440 x 900 with no horizontal overflow
- Mobile layout: validated at 390 x 844 with no horizontal overflow
- End-to-end answer: completed with three valid citations and no citation warnings
- Observed answer latency: 4.6-5.7 seconds; model generation remained the dominant stage
- Pre-remediation extraction baseline: 64 pass, 27 warning, and 0 fail across 91 update documents
- Post-remediation extraction baseline: 177 pass, 10 warning, and 0 fail across 187 update documents
- Remaining extraction warnings are isolated to OpenAI News feed previews blocked from full-page hydration
- Initial summary baseline: 144 pass, 43 warning, and 0 fail across 187 generated summaries
- Phase 2 closeout summary baseline: 196 pass, 44 warning, and 0 fail across 240
  generated summaries
- Closeout warning composition: 29 lexical-grounding review signals, 19 known
  preview-only sources, 4 derived/rounded number candidates, and 0 overlong headlines
- Refreshed ten-item human summary sample: no unreviewed fields and 10/10 correct
  taxonomy ratings after two follow-up corrections
- Taxonomy regression: 43/43 reviewed items and 129/129 axes passed
- Feed-relevance calibration: 50/50 reviewed decisions completed; production
  classification remains deferred
- Source-boundary remediation baseline: 184 pass, 10 warning, and 0 fail across 194 documents
- Refreshed extraction review: 18 complete and 2 incomplete OpenAI previews across 20 sampled documents
- Phase 2 summary/taxonomy calibration is complete for the MVP

## Deliberately Deferred

- Dated research-discovery and community-signal snapshots
- Cross-source story clustering and duplicate-event merging
- User accounts, saved views, and personalization
- Streaming answer transport
- Learned reranking and formal retrieval-quality evaluation sets

See `ROADMAP.md` for the recommended order of follow-up work.
The update-focused RAG benchmark is the next active phase; see
`PHASE3_RETRIEVAL_BENCHMARK_PLAN.md`. Deployment follows as Phase 4.
