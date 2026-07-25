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
- LLM judge calibrated against human labels
- Prompt regression report by source type

Status on July 24, 2026: paused at the project owner's request; Phase 1 no longer blocks it.

- A read-only evaluator checks structure, taxonomy validity, unsupported numbers, lexical grounding, fallback generation, and incomplete source content.
- The initial baseline evaluated 187 summaries: 144 pass, 43 warning, and 0 fail.
- Warnings include 28 low-lexical-grounding, 9 incomplete-source, 8 unsupported-number, and 1 headline-length finding.
- A ten-item sample is stratified across source types, generators, and sources. Known-incomplete OpenAI News previews are excluded from the normal sample.
- Human labels are still required before changing prompts or trusting an LLM judge.
- The procedure and rating definitions are documented in `SUMMARY_EVAL_RUNBOOK.md`.
- The earlier summary sample and baseline were generated before source-boundary remediation and must be regenerated after Phase 1 closes.

## Phase 3: Retrieval Benchmark

- Versioned question and relevance judgments
- Recall@K, Precision@K, MRR, filter correctness, and source coverage
- Temporal, comparison, and insufficient-evidence questions
- Baseline comparisons before retrieval changes

## Phase 4: Content Structure

- Generalize and evaluate multi-story splitting beyond the source-specific The Batch and Import AI adapters
- Cluster cross-source coverage of the same event
- Evaluate story boundaries and pairwise cluster precision and recall

## Phase 5: Product-Focused UI

- Contextual cited brief
- Today, week, month, and since-last-visit views
- Followed topics and tools
- Read, saved, and learning-queue states

Each phase requires a saved baseline, documented findings, and measurable completion criteria before the next phase begins.
