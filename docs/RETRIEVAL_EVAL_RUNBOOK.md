# Retrieval Eval Runbook

This is the legacy documentation-corpus smoke loop for the RAG system.

It evaluates retrieval only. It does not grade final answer quality yet.

It must remain green for backward compatibility, but its 15 documentation questions
are not the update-focused Phase 3 benchmark. The versioned update benchmark is
specified in `PHASE3_RETRIEVAL_BENCHMARK_PLAN.md`.

## Files

Question set:

```text
backend/data/eval/questions.yml
```

Runner:

```text
backend/scripts/evaluate_retrieval.py
```

Generated outputs:

```text
backend/data/eval/results.jsonl
backend/data/eval/summary.json
```

Generated outputs are gitignored.

## Run

Make sure Postgres is running and the corpus has been ingested.

```bash
cd /path/to/ai-engineer-knowledge-engine
docker compose up -d postgres

cd backend
uv run python scripts/evaluate_retrieval.py
```

## Latency Profiling

To separate retrieval latency from LLM latency:

```bash
cd /path/to/ai-engineer-knowledge-engine/backend
uv run python scripts/profile_latency.py
```

Output:

```text
backend/data/eval/latency_profile.json
```

## Metrics

`source_hit_rate`

At least one expected source appeared anywhere in the retrieved top-k chunks.

`all_expected_sources_hit_rate`

Every expected source appeared in the retrieved top-k chunks. This is stricter and more useful for comparison questions.

`top_3_source_hit_rate`

At least one expected source appeared in the top 3 retrieved chunks.

`avg_top_score`

Average similarity score of the first result. This is not a universal quality score, but it is useful for tracking changes over time.

`title_hint_hit_rate`

Whether retrieved document titles contain at least one expected title hint. This is stricter than source-level retrieval because it checks whether the right document family showed up.

`avg_keyword_coverage`

How many expected keywords appeared across the retrieved titles and chunks. This is a lightweight proxy for whether the retrieved context contains the concepts needed for an answer.

## How To Interpret

Easy questions should usually pass.

Medium comparison questions may pass partially if one expected source dominates the top-k.

Hard questions exercise the implemented retrieval controls and expose where more advanced techniques may be justified:

- source balancing
- exact keyword search
- hybrid retrieval
- similarity thresholds
- query rewriting
- reranking

## Tuning Order

Use eval results to tune in this order:

1. Fix bad source pages or extraction.
2. Adjust chunk size and overlap.
3. Adjust top-k.
4. Compare vector, keyword, and hybrid modes.
5. Apply source filters or source-balanced retrieval where appropriate.
6. Add reranking only for measured failures that the current controls cannot fix.
7. Add query rewriting or multi-query retrieval only after evaluating the added cost and complexity.
