# Retrieval evaluation

Evaluate retrieval against saved article questions and an explicit corpus snapshot.

## Article benchmark

Frozen snapshot:

```text
backend/data/eval/retrieval/updates_snapshot_2026-07-27.json
```

Question set:

```text
backend/data/eval/retrieval/updates_questions_2026-07-27.yml
```

Create or intentionally refresh a snapshot:

```bash
cd backend
uv run python scripts/evaluation/prepare_update_retrieval_snapshot.py
```

Run the exact-document evaluator:

```bash
uv run python scripts/evaluation/evaluate_update_retrieval.py \
  --search-mode hybrid \
  --retrieval-strategy standard \
  --output data/eval/retrieval/updates_tuned_hybrid_standard.json
```

Useful isolated runs:

```bash
uv run python scripts/evaluation/evaluate_update_retrieval.py \
  --split calibration \
  --search-mode hybrid

uv run python scripts/evaluation/evaluate_update_retrieval.py \
  --intent exact_lookup \
  --top-k 5 \
  --search-mode hybrid
```

Do not regenerate the snapshot after ordinary collection and continue using the same
question judgments. A changed corpus hash requires an explicit benchmark-version
decision.

The original documentation-only smoke test was removed with the docs corpus.
