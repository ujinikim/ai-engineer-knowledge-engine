# Developer Update Radar

A time-aware, multi-source RAG article feed for AI engineering news and releases.

The application collects official releases, changelogs, product news, and engineering blogs into PostgreSQL. New or changed items receive structured feed summaries and taxonomy metadata. Questions remain grounded in retrieved original source chunks rather than generated summaries.

```text
Official feeds -> normalize -> deduplicate -> summarize + categorize
       |                                      |
       +--------------> chunk original text -> embed -> PostgreSQL
                                                     |
Article feed <- time/facet query <- ranked stories   |
                                                     |
Question -> filtered hybrid retrieval -> original evidence -> cited answer
```

## MVP

- Seventeen quality-tiered sources spanning primary releases, engineering publications, and selected editorial analysis
- Structured headlines, summaries, why-it-matters text, key points, and entity tags
- Nine-topic controlled taxonomy with event type, source type, and maturity facets
- Idempotent collection with publication and fetch timestamps
- PostgreSQL + pgvector storage
- `24 hours`, `7 days`, `30 days`, and `All` dashboard windows
- Tool, topic, event, source-type, and source filters
- Deterministic recency and source-quality ranking
- Vector, keyword, and recency-aware hybrid RAG retrieval
- Answers restricted to the selected update window
- Used citations separated from all retrieved evidence
- Retrieval latency, token, and cost diagnostics
- Existing documentation corpus retained as a separate collection

The MVP does not include general web crawling, engagement-based popularity, cross-publication story clustering, agents, chat memory, or an LLM browsing the web at question time. Summaries are derived display content; original chunks remain the RAG evidence.

## Stack

- FastAPI, SQLAlchemy, Pydantic
- PostgreSQL 16 with pgvector
- OpenAI embeddings and answer generation
- React, TypeScript, Vite
- Docker Compose for PostgreSQL

## Local Setup

Start PostgreSQL and prepare the schema:

```bash
docker compose up -d postgres
cd backend
uv sync
uv run python scripts/create_db.py
```

Collect the latest matching official articles and releases once:

```bash
uv run python scripts/collect_updates.py --max-items 12
```

Keep the database fresh every hour:

```bash
uv run python scripts/collect_updates.py --max-items 12 --interval-minutes 60
```

Start the API:

```bash
uv run fastapi dev app/main.py
```

Start the frontend in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. API documentation is at `http://localhost:8000/docs`.

The older documentation ingestion pipeline remains available through `backend/scripts/ingest.py`.

Generate or regenerate article metadata for already stored updates:

```bash
uv run python scripts/backfill_article_metadata.py
uv run python scripts/backfill_article_metadata.py --force
```

## Documentation

- [Project brief](docs/PROJECT_BRIEF.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data sources](docs/DATA_SOURCES.md)
- [Product direction](docs/PRODUCT_DIRECTION.md)
- [Quality improvement plan](docs/QUALITY_IMPROVEMENT_PLAN.md)
- [Extraction evaluation runbook](docs/EXTRACTION_EVAL_RUNBOOK.md)
- [Summary evaluation runbook](docs/SUMMARY_EVAL_RUNBOOK.md)
- [Collection runbook](docs/COLLECTION_RUNBOOK.md)
- [API design](docs/API_DESIGN.md)
- [MVP status](docs/MVP_STATUS.md)
- [Roadmap](docs/ROADMAP.md)
