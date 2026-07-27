# Quality Improvement Plan

The improvement program is intentionally ordered so later evaluation never hides an upstream data-quality failure.

## Phase 1: Extraction Quality

- Automated integrity and content-quality checks for every stored update
- Per-source and per-extraction-method reporting
- Stratified human-review sample with labels preserved across reruns
- Report-only quality thresholds before any ingestion gate is enabled

Status on July 24, 2026: complete with one documented source limitation.

- Evaluation tooling and the original 91-document baseline are complete.
- Twelve representative documents have human labels and calibrated notes.
- Full-page hydration is configured for Google Developers, Hugging Face, NVIDIA, and OpenAI.
- Failed hydration falls back to feed text and is reported instead of failing the source.
- Publication dates remain unknown when neither the feed nor article exposes a valid date.
- Excerpt and duplicate-line heuristics are calibrated for short GitHub releases and RSS footers.
- The fresh collection processed all 17 sources with no source errors.
- The post-remediation baseline is 177 pass, 10 warning, and 0 fail across 187 documents.
- All remaining warnings belong to OpenAI News because Cloudflare blocks plain HTTP article hydration; validated feed previews are retained and marked explicitly.
- The original 12-document human calibration is archived as `human_review_baseline_2026-07-22.json`.
- A later review found that The Batch date-tag catalogs and Import AI newsletters had incorrect document boundaries even though structural checks passed.
- The Batch now stores individual stories, Import AI stores deterministic story sections, Anthropic excludes related cards, and relevance terms use word boundaries.
- The refreshed baseline is 184 pass, 10 warning, and 0 fail across 194 documents. Remaining warnings are still isolated to OpenAI News.
- The refreshed 20-document human sample contains 18 complete extractions and 2 incomplete OpenAI previews.
- The Batch, Import AI, Anthropic, and GitHub boundary fixes passed human review.
- OpenAI preview-only records remain accepted as a visible, explicitly labeled limitation with original links retained.

## Phase 2: Summary Evaluation

- Human-labeled faithfulness, coverage, usefulness, and headline-quality sample
- Taxonomy accuracy checks
- Optional LLM judge calibrated against human labels before use
- Prompt regression report by source type

Status on July 27, 2026: complete for MVP quality calibration.

- The current baseline evaluates 240 summaries: 196 pass, 44 warning, and 0 fail.
- Remaining warnings are review signals: 29 low lexical grounding, 19 known
  preview-only sources, and 4 derived or rounded number expressions.
- Percentage symbols/words and numerically equivalent trailing-zero forms are
  normalized.
- Lexical grounding records source detail, normalizes basic word forms, and applies a
  stricter threshold to sparse sources than detailed sources.
- Generated and fallback headlines are capped at 90 characters; three stored
  headlines were backfilled.
- The refreshed ten-item human sample has no unreviewed fields. All ten taxonomy
  assignments are correct after two follow-up corrections.
- Sparse prompt regression, taxonomy regression, extraction provenance, sparse
  visibility, and feed-relevance calibration are complete.
- Automatic production relevance classification and the optional LLM summary judge
  are explicitly deferred; neither blocks the next phase.

## Phase 3: Deployment Foundation

- Package the frontend, API, collector, and Postgres deployment reproducibly
- Replace production schema initialization with versioned migrations
- Add health/readiness endpoints and environment validation
- Deploy staging, exercise scheduled collection, and run hosted smoke tests
- Launch production with backups, monitoring, cost controls, and rollback procedures

The detailed order, recommended Render topology, and acceptance criteria are in
`DEPLOYMENT_PLAN.md`.

## Phase 4: Retrieval Benchmark

- Versioned question and relevance judgments
- Recall@K, Precision@K, MRR, filter correctness, and source coverage
- Temporal, comparison, and insufficient-evidence questions
- Baseline comparisons before retrieval changes

Run the saved baseline against the hosted Phase 3 environment so latency and
connection behavior represent the deployed application.

## Phase 5: Content Structure

- Generalize and evaluate multi-story splitting beyond the source-specific The Batch and Import AI adapters
- Cluster cross-source coverage of the same event
- Evaluate story boundaries and pairwise cluster precision and recall

## Phase 6: Product-Focused UI

- Contextual cited brief
- Today, week, month, and since-last-visit views
- Followed topics and tools
- Read, saved, and learning-queue states

Each phase requires a saved baseline, documented findings, and measurable completion criteria before the next phase begins.
