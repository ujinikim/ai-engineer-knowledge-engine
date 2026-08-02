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

## Production container

Build the Linux AMD64 backend image from the repository root:

```bash
docker build \
  --platform linux/amd64 \
  --build-arg VCS_REF="$(git rev-parse HEAD)" \
  --tag ai-engineer-knowledge-engine-backend:local \
  backend
```

Run it locally without loading credentials into the image:

```bash
docker run --rm \
  --platform linux/amd64 \
  --publish 8000:8000 \
  ai-engineer-knowledge-engine-backend:local
```

The runtime image installs dependencies from `uv.lock`, runs as a non-root user,
and exposes `GET /health` as its Docker health check. Database and OpenAI settings
must be supplied at runtime rather than copied into the image.
