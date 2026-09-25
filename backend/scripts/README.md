# Backend commands

Run these from `backend/` with `uv run python scripts/<path>.py`.

| Location | Purpose |
| --- | --- |
| `collect_updates.py` | Collect configured update sources; writes articles and chunks. |
| `create_db.py` | Compatibility database setup command; use migrations for schema changes. |
| `evaluation/` | Read stored content and write local evaluation reports or review samples. |
| `reviews/` | Prepare or record human review decisions; check each command's `--help` before applying changes. |
| `maintenance/` | Backfill stored article metadata; use dry-run options where available. |
| `verification/` | Deployment and migration checks used by CI. |

Source definitions live in `data/update_sources.yml`. Evaluation output is under `data/eval/`.
