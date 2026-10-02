# Code map

Where things live. Layers and the dependency rule are in [ARCHITECTURE.md](ARCHITECTURE.md#layers-and-the-dependency-rule): `api -> serving -> db / domain / sources / core`; `ingestion` uses the same bottom layers; nothing but `ingestion` and scripts imports `ingestion`.

## backend/app — the running service

| Path | Job |
|---|---|
| `main.py` | FastAPI app setup |
| `api/routes.py` | HTTP endpoints; thin, calls `serving/` |
| `schemas/` | Request/response models (`updates`, `search`, `ask`, `health`) |
| `serving/feed.py` | Feed listing, filters, facets, ordering |
| `serving/search.py` | Vector search over chunks |
| `serving/answer.py` | Q&A over retrieved chunks |
| `serving/visibility.py` | The one rule for "which articles are visible" |
| `serving/health.py` | Health checks |
| `domain.py` | Shared vocabulary: statuses, tiers, topics, event types, `evidence_level` |
| `sources.py` | Reads `data/update_sources.yml` (the source list and per-source options) |
| `db/models.py`, `db/session.py` | Tables, constraints, DB session |
| `core/` | Settings, logging, embeddings, model-usage counting |
| `evaluation/` | Quality checks for extraction and summaries (used by `scripts/evaluation`) |

## backend/app/ingestion — the collector (one article's journey, in order)

| Step | File |
|---|---|
| Run all sources | `pipeline.py` (`IngestionPipeline`), `lock.py` (one collector at a time) |
| Fetch feed/page, retries | `fetch.py` |
| Parse feeds, HTML, dates | `parsing.py` |
| Build a candidate | `candidate.py`, `urls.py` |
| Publish or quarantine | `policy.py` |
| Process one article (6 routes) | `ingest.py` |
| Relevance tier (core/contextual/excluded) | `relevance.py`, `prompts.py` |
| Topic and event labels | `taxonomy_classifier.py`, `taxonomy.py` |
| Summary and card text | `summary.py`, `content_detail.py`, `text.py` |
| Chunk and embed | `chunking.py` |
| Save to DB | `store.py` |

## Elsewhere

- `backend/data/update_sources.yml` — the sources and their options
- `backend/migrations/versions/` — schema history (head: `20260925_0014`)
- `backend/tests/` — mirrors `app/`; shared helpers `factories.py`, `fakes.py`
- `backend/scripts/` — `collect_updates.py` (production job), `create_db.py`; subfolders `evaluation/`, `verification/`
- `frontend/src/` — `App.tsx`, `FeedSection.tsx`, `BriefingPanel.tsx`, `AboutView.tsx`, `api.ts`, `display.ts`, `styles/`
- `infra/` — Terraform for AWS
- `.github/workflows/` — CI and image build
