# Phase 3 Retrieval and Grounded-Answer Closeout — July 29, 2026

## Decision

Phase 3 is complete for the MVP. The frozen update benchmark satisfies every initial
retrieval and answer-safety acceptance target. Deployment foundation is now the active
phase.

## Evaluated Scope

- Frozen corpus: 240 update documents and 1,134 original-text chunks
- Corpus hash:
  `d12684ca90a0651eb3d80638d12b17df745ac780b9c3fefac5b86737db5eda73`
- Retrieval questions: 30
- Calibration/holdout split: 20/10
- Answer-review sample: 12
- Answer model: `gpt-4.1-mini`
- Embedding model: `text-embedding-3-small`
- Retrieval: hybrid, standard strategy
- Context budget: 3,500 tokens
- Completion ceiling: 500 tokens

## Final Retrieval Result

| Metric | Result |
|---|---:|
| Recall@K | 1.000 |
| Precision@K | 0.509 |
| Mean reciprocal rank | 0.982 |
| All relevant documents hit | 1.000 |
| All required sources hit | 1.000 |
| Filter correctness | 1.000 |
| Required-text coverage | 0.988 |

Result artifact:
`backend/data/eval/retrieval/updates_tuned_hybrid_standard_context_ready_2026-07-29.json`

The only remaining required-text partial is `synthesis_monday_agents`, where selected
context includes `SNS` and `EFS` but not `SQS`.

## Human Answer Review

Final judgments:

| Outcome | Cases |
|---|---:|
| Pass | 11 |
| Partial | 1 |
| Fail | 0 |

The sample covered exact lookups, temporal retrieval, comparisons, filtering,
synthesis, and all three insufficient-evidence cases.

- Valid citation IDs: 100%
- Comparison source coverage: 100%
- Insufficient-evidence behavior: 3/3 pass
- Unsupported confident answers after remediation: 0
- Generation-limit warnings in accepted final answers: 0

Human-review artifact:
`backend/data/eval/retrieval/updates_answer_review_sample.json`

The original unsupported Presence metric and the original incomplete agent-security
comparison remain in the artifact as historical pre-fix results. Their post-fix
reviews pass.

## Accepted Changes

- Canonical separator normalization for lexical matching
- Title-aware lexical scoring without document-specific rules
- Title-only chunk suppression when substantive chunks are available
- Comparison-aware document-diverse context packing
- Continued token packing after an oversized candidate
- Separate retrieved-candidate and answer-context diagnostics
- Stronger exact-metric and insufficient-evidence prompt requirements
- Concise-answer guidance and explicit generation-limit warnings
- Future trailing-slash URL normalization and variant-aware upsert lookup

All accepted changes have focused regression tests and saved before/after results.

## Deferred Decisions

### Within-document neighbor expansion

Do not add it now. Only the monday.com synthesis remained partial, and its answer was
still materially useful. Add neighbor expansion only if staging or later answer
reviews show repeated omissions from long, correctly retrieved documents.

### Stronger reranking

Do not add a cross-encoder, late-interaction index, learned reranker, or LLM reranker
for the MVP. The deterministic pipeline meets the retrieval targets. Reconsider only
after new labeled failures establish a repeated relevance problem.

### Historical duplicate merge

Future collection now normalizes trailing-slash URL variants, and answer-context
packing groups those variants. Existing duplicate rows were not deleted. Consolidate
them only through a separately reviewed, recoverable data migration.

## Acceptance Targets

| Target | Status |
|---|---|
| 100% filter correctness | Pass |
| At least 90% exact-lookup Recall@5 | Pass |
| At least 0.80 exact-lookup MRR | Pass |
| At least 80% comparison required-source coverage | Pass |
| At least 85% holdout Recall@K | Pass |
| No documentation-smoke regression | Pass |
| 100% valid citation IDs in answer sample | Pass |
| No unsupported confident insufficient-evidence answer | Pass |
| Saved before/after results for accepted retrieval changes | Pass |

## Deployment Handoff

Phase 4 should:

1. Package the API, frontend, collector, and PostgreSQL/pgvector services.
2. Introduce versioned database migrations.
3. Add production environment validation and readiness checks.
4. Deploy staging.
5. Rerun the frozen Phase 3 benchmark without retuning.
6. Record hosted retrieval and answer latency.
7. Exercise collection, filters, answer context, citations, and rollback.

