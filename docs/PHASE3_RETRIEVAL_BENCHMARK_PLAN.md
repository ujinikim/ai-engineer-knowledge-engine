# Phase 3 Retrieval Benchmark Plan

## Goal

Measure whether the RAG system retrieves the right original update evidence, respects
time and taxonomy filters, supports comparisons, and recognizes insufficient
evidence before deployment work begins.

The benchmark evaluates the system built during Phases 1 and 2:

```text
collected source
  -> extracted story
  -> original-text chunks
  -> embeddings + keyword index
  -> taxonomy/time filters
  -> hybrid ranking and diversification
  -> evidence supplied to the answer model
  -> grounded answer and citations
```

Summaries remain display content. Expected evidence and answer judgments must be based
on original source chunks.

## Existing Starting Point

The repository already has:

- pgvector semantic retrieval
- keyword and hybrid retrieval modes
- standard and source-balanced strategies
- recency-aware ranking for updates
- document-level chunk diversification
- time, source, tool, topic, event, source-type, and maturity filters
- answer similarity thresholds
- citation validation and retrieval diagnostics
- a 15-question documentation-corpus smoke test

The existing `backend/data/eval/questions.yml` set targets documentation sources. It
is useful for backward compatibility but is not the Phase 3 update benchmark.

## Work Order

### 1. Freeze the evaluation snapshot

Create a dated manifest for the current 240-update corpus containing:

- document ID
- canonical URL
- source
- title
- publication time
- content hash
- taxonomy policy version
- embedding model and dimensions
- collection timestamp

The benchmark must identify its snapshot so later collection does not silently change
the denominator or expected answers.

### 2. Create the update question set

Start with 30 independently reviewable questions:

| Question family | Initial count | Purpose |
|---|---:|---|
| Exact update lookup | 8 | Retrieve a specific release, model, API, or technical change |
| Temporal/latest | 5 | Respect publication ranges and distinguish recent from old |
| Cross-source comparison | 5 | Retrieve evidence from every required source/document |
| Taxonomy/filter | 5 | Enforce tool, topic, event, maturity, and source filters |
| Synthesis | 4 | Gather several complementary chunks for one engineering question |
| Insufficient evidence | 3 | Avoid pretending the corpus supports an answer |

Each case should store:

```yaml
id: unique_case_id
question: User-facing question
intent: comparison
request:
  collection: updates
  top_k: 8
  search_mode: hybrid
  retrieval_strategy: source_balanced
  published_after: null
  published_before: null
  source_names: null
  tools: null
  categories: null
  event_types: null
  source_types: null
  maturities: null
relevant_document_ids:
  - reviewed-document-uuid
required_source_names:
  - source-slug
required_facts:
  - Fact that must be present in retrieved original text
expected_outcome: answerable
notes: Why these judgments are appropriate
```

Use exact document judgments rather than title hints as the principal ground truth.
Title terms and keywords may remain secondary diagnostics.

Split the set before tuning:

- 20 calibration questions for inspecting and improving retrieval
- 10 holdout questions that are not used to choose weights or thresholds

### 3. Upgrade the deterministic evaluator

Keep the documentation smoke evaluator working, but add an update-benchmark mode that:

- reads the complete `SearchRequest` configuration from each case
- checks exact relevant document IDs
- detects filter violations
- preserves per-result document IDs, chunk IDs, scores, and ranks
- supports multiple relevant documents
- reports metrics overall and by question family
- writes a dated, versioned baseline artifact that is committed

Required retrieval metrics:

- Recall@K
- Precision@K
- Mean Reciprocal Rank
- first relevant rank
- all-required-documents hit rate
- all-required-sources hit rate
- filter correctness
- required-fact coverage
- embedding, database retrieval, and total retrieval latency

Source hit rate remains a useful diagnostic but is too weak to be the main metric.

### 4. Run the unmodified baseline

Evaluate this fixed matrix before changing retrieval:

| Search mode | Strategy |
|---|---|
| vector | standard |
| keyword | standard |
| hybrid | standard |
| hybrid | source-balanced |

Save:

- per-question results
- aggregate metrics
- results by question family
- failed and partially satisfied cases
- configuration and corpus snapshot references

Do not tune weights until this baseline is saved.

### 5. Review failures by cause

Assign each failure one principal cause:

- missing or bad source content
- wrong document boundary
- unsuitable chunk boundary
- embedding miss
- lexical/exact-term miss
- recency overweighting
- filter bug
- one document/source dominating comparison results
- insufficient top-k
- genuinely ambiguous question or bad relevance judgment

Fix upstream extraction or labels rather than compensating for them with ranking
weights.

### 6. Tune only measured failures

Use the existing tuning order:

1. Correct ground-truth or upstream data defects.
2. Correct filter behavior.
3. Adjust top-k for question families that need broader evidence.
4. Compare current vector, keyword, hybrid, and source-balanced controls.
5. Adjust hybrid/recency weights only with before/after results.
6. Revisit chunk size/overlap only when failures show missing evidence boundaries.
7. Add reranking only when simpler controls cannot satisfy the holdout target.
8. Add query rewriting or multi-query retrieval only after measuring its cost.

Every accepted retrieval change must include the baseline comparison and focused
regression tests.

### 7. Evaluate answer grounding

After retrieval meets its target, select 12 cases across the question families and
run the full `/ask` path.

Human-grade:

- factual groundedness
- coverage of required facts
- citation correctness
- whether every material claim has usable evidence
- whether comparison answers represent every required source
- whether insufficient-evidence cases abstain or qualify appropriately

Do not add an LLM judge during initial calibration. Human judgments are the reference
labels if a judge is introduced later.

### 8. Save the Phase 3 closeout baseline

Commit:

- snapshot manifest
- versioned question set
- relevance judgments
- retrieval result summary
- selected answer-review sample
- findings and accepted changes
- exact model, ranking, chunking, and request configuration

## Initial Acceptance Targets

These targets are deliberately practical for the first 30-case benchmark:

- 100% filter correctness
- At least 90% Recall@5 for exact update lookups
- At least 0.80 MRR for exact update lookups
- At least 80% all-required-sources hit rate for comparison cases at their configured K
- At least 85% overall Recall@K on the 10-question holdout
- No regression in the existing documentation smoke set
- 100% valid citation IDs in the answer-review sample
- No unsupported confident answer for the three insufficient-evidence cases
- All accepted retrieval changes have saved before/after results

If the unmodified baseline shows that a target is poorly specified, change the target
only with a written reason before tuning.

## Phase 4 Deployment Rerun

Deployment does not repeat relevance labeling or retrieval tuning. It reruns the
frozen Phase 3 benchmark in staging to verify:

- identical filter and relevance outcomes
- no material retrieval-quality regression
- hosted embedding, database, and total latency
- connection-pool and cold-start behavior

Hosted latency becomes a Phase 4 operational measurement; retrieval correctness is
established in Phase 3.
