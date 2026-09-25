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

With Docker running and Node.js/npm and `uv` installed, install dependencies once:

```bash
npm install --prefix frontend
cd backend
uv sync
cd ..
```

From the project root, start each service separately. Run the backend and frontend
in separate terminals:

```bash
npm run db:up
npm run dev:backend
npm run dev:frontend
```

Open `http://localhost:5173`; API docs are at `http://localhost:8000/docs`.
Starting the services does not ingest articles or migrate the database. Run
`npm run db:migrate` after creating a database or changing its schema, and run
`npm run ingest -- --max-items 12` when you want a collection pass. Stop the
servers with Ctrl+C and PostgreSQL with `npm run db:stop`; its data is preserved.
Use the local database URL from `.env.example` when working locally.

## Documentation

- [Documentation guide](docs/README.md): current references, runbooks, and historical records
- [Roadmap](docs/ROADMAP.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Data sources](docs/DATA_SOURCES.md)
