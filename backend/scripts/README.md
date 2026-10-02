# Backend commands

Run these from `backend/` with `uv run python -m scripts.<module>` (for example `scripts.collect_updates`).

| Location | Purpose |
| --- | --- |
| `collect_updates.py` | Collect configured update sources; writes articles and chunks. |
| `create_db.py` | Compatibility database setup command; use migrations for schema changes. |
| `verification/` | Deployment and migration checks used by CI. |

Source definitions live in `data/update_sources.yml`.
