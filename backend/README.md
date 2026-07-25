# Backend

FastAPI backend for ingestion, retrieval, and answer generation.

## Planned Commands

```bash
uv sync
uv run python scripts/fetch_sources.py
docker compose up -d postgres
uv run python scripts/create_db.py
uv run python scripts/ingest.py
uv run fastapi dev app/main.py
```

## First Endpoints

- `GET /health`
- `POST /search`
- `POST /ask`
