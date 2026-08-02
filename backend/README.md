# Backend

FastAPI backend for ingestion, retrieval, and answer generation.

## Planned Commands

```bash
uv sync
uv run python scripts/fetch_sources.py
docker compose up -d postgres
uv run alembic upgrade head
uv run python scripts/ingest.py
uv run fastapi dev app/main.py
```

`uv run python scripts/create_db.py` remains as a compatibility command and now runs
the same Alembic upgrade rather than executing a separate SQL schema file.

## Database migrations

Alembic is the source of truth for the PostgreSQL schema. From `backend/`, inspect and
apply migrations with:

```bash
uv run alembic current
uv run alembic upgrade head
uv run alembic check
```

The initial revision enables pgvector and creates the document, chunk, source, search,
and vector indexes. It can also adopt an existing database created by the former SQL
bootstrap without deleting its data. Back up a production database and verify its
schema before adopting any unversioned copy.

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

The minimal Alpine-based runtime image installs dependencies from `uv.lock`, runs
as a non-root user, and exposes `GET /health` as its Docker health check. Database
and OpenAI settings must be supplied at runtime rather than copied into the image.
The image includes the Alembic configuration and revisions so the deployment workflow
can migrate the database with the same immutable image that runs the API.
