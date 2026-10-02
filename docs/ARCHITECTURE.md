# Architecture

What the project does, how it is layered, and where each piece lives.

## What happens to an article

```text
update_sources.yml  ->  collector (scheduled job)
  fetch feed or listing -> fetch the article page -> publication gate
  -> relevance tier (core / contextual / excluded)
  -> summary card + topic and event labels
  -> chunk original text -> embed -> PostgreSQL + pgvector

React feed   -> GET /updates  (visible, ranked articles)
Q&A panel    -> POST /ask     (vector + keyword + recency search -> cited answer)
```

The collector is a scheduled job, not part of the API process. In production it runs
`python scripts/collect_updates.py --max-items 12` from the backend Docker image.

## Decisions made about each article

Every stored article is one `documents` row. Four fields decide what happens to it:

| Field | Meaning | Values |
|---|---|---|
| `extraction_status` | How much article text was obtained | `full_article`, `source_entry` (the feed's own text, by design), `feed_excerpt_only`, `title_only` |
| `ingestion_status` | The publication gate | `published`, or `quarantined` (fetch failed or too little detail; kept only for diagnosis) |
| `relevance_tier` | Relevance to agent engineering | `core`, `contextual`, `excluded`; empty means classification failed and is retried next run |
| `relevance_policy_version` | Rules version behind the tier | date string; a changed version re-classifies |

An article is visible in the feed when its source is configured, it is `published`, and its
tier is `core` (or also `contextual` when the request asks). Search uses the same rule.
Excluded articles get a card built from the source excerpt, with no model summary,
chunks, or embeddings. Core and contextual articles are summarized, chunked and embedded.

When a refresh is worse than what is stored (the page can no longer be fetched), the
stored article is kept.

## Ranking and retrieval

```text
importance = 45% source credibility + 45% freshness + 10% content detail
freshness  = exp(-age_days / 21)

retrieval  = 60% vector relevance + 25% keyword relevance + 15% recency
```

Final retrieval is capped at two chunks per article so one long post cannot fill the
context. Summaries are display content; original chunks are the evidence for answers.

## Layers and the dependency rule

```text
api/  ->  serving/  ->  db/, domain, sources, core/
                         ^
ingestion/  ------------'
```

`serving/`, `db/` and `api/` never import `ingestion/`, so the API process does not load
the feed parser or the classifiers. `tests/api/test_import_boundary.py` fails if that changes.

### backend/app

| Path | Job |
|---|---|
| `main.py`, `api/routes.py` | FastAPI app and thin endpoints |
| `schemas/` | Request and response models |
| `serving/feed.py` | Feed listing, filters, facets, ordering |
| `serving/search.py`, `serving/answer.py` | Retrieval and cited answers |
| `serving/visibility.py` | The single rule for which articles are visible |
| `serving/health.py` | Health checks |
| `domain.py` | Shared vocabulary: statuses, tiers, topics, event types, card excerpt |
| `sources.py` | Reads `data/update_sources.yml` |
| `db/` | Tables and constraints (`models.py`), session |
| `core/` | Settings, logging, embeddings, model-usage counting |

### backend/app/ingestion, in the order an article passes through

| Step | File |
|---|---|
| Run all sources, one collector at a time | `pipeline.py`, `lock.py` |
| Fetch feed or page, with retries | `fetch.py` |
| Parse feeds, HTML and dates | `parsing.py` |
| Build a candidate article | `candidate.py`, `urls.py` |
| Publish or quarantine | `policy.py` |
| Decide what one article becomes (five routes) | `ingest.py` |
| Relevance tier | `relevance.py`, `prompts.py` |
| Summary card, topic and event labels (one model call; keyword rules are the fallback) | `summary.py`, `taxonomy.py`, `content_detail.py`, `text.py` |
| Chunk | `chunking.py` |
| Save | `store.py` |

### Elsewhere

- `backend/data/update_sources.yml`: the sources and their options (see `docs/DATA_SOURCES.md`)
- `backend/migrations/versions/`: schema history
- `backend/tests/`: mirrors `app/`; shared helpers `factories.py` and `fakes.py`
- `backend/scripts/`: `collect_updates.py` (the production job), `create_db.py`, and `verification/` (CI checks)
- `frontend/src/`: `App.tsx`, `FeedSection.tsx`, `BriefingPanel.tsx`, `AboutView.tsx`, `api.ts`, `display.ts`, `styles/`
- `infra/terraform/`: AWS (see its README); `.github/workflows/`: CI and image build

## Words

| Word | Where | Meaning |
|---|---|---|
| article | code and docs | A collected piece of content |
| document | database | The `documents` row that stores an article (`chunks` belong to it) |
| update | API paths and `collection_source_runs` counters | Legacy name for an article in the feed |

## Limitations

- Articles are not clustered into cross-source stories.
- HTML-only publications use explicit link patterns and content selectors; there is no broad crawling.
- Ranking has no engagement signal, and the API response is not streamed.
