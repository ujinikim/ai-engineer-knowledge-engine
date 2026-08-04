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

- `GET /health/live`
- `GET /health/ready`
- `POST /search`
- `POST /ask`

`GET /health` remains available temporarily for compatibility. Liveness only confirms
that FastAPI can respond; it never contacts PostgreSQL or OpenAI. Readiness returns
`200` only when PostgreSQL is reachable, the database is at the packaged Alembic head,
and pgvector is installed. Otherwise it returns `503` with safe check labels and no
connection details. OpenAI is intentionally excluded so a provider outage does not
cause the API process to restart.

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
  --env APP_ENVIRONMENT=development \
  --publish 8000:8000 \
  ai-engineer-knowledge-engine-backend:local
```

The minimal Alpine-based runtime image installs dependencies from `uv.lock`, runs
as a non-root user, defaults to strict `production` configuration, and exposes
`GET /health/live` as its Docker health check. Database and OpenAI settings must be
supplied at runtime rather than copied into the image.
The image includes the Alembic configuration and revisions so the deployment workflow
can migrate the database with the same immutable image that runs the API.
API and collector application events are emitted as newline-delimited JSON for
CloudWatch ingestion. Uvicorn's duplicate request access log is disabled; see
`../docs/OBSERVABILITY_RUNBOOK.md` for event fields and sensitive-data rules.

## Runtime configuration

`APP_ENVIRONMENT` controls configuration strictness:

- `development` is the default when running the source directly and permits local
  database and frontend origins.
- `test` permits isolated test configuration.
- `production` refuses to start with missing or unsafe required values.

Production requires:

```text
APP_ENVIRONMENT=production
DATABASE_URL=postgresql+psycopg://<username>:<password>@<rds-host>:5432/knowledge_engine
OPENAI_API_KEY=<production-scoped-key>
CORS_ORIGINS=["https://<cloudfront-domain>"]
```

`APP_ENVIRONMENT` and the frontend origin are normal configuration. `OPENAI_API_KEY`
will be supplied from Systems Manager Parameter Store. The RDS master credentials are
generated and rotated by RDS in Secrets Manager; the EC2 runtime will retrieve them
and construct `DATABASE_URL` in memory. Neither secret is committed, copied into the
image, written into user data, or stored as a Terraform value.
