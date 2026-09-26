# API Design

## Health

```http
GET /health/live
GET /health/ready
```

`/health/live` is a dependency-free process check:

```json
{"status": "alive"}
```

`/health/ready` verifies PostgreSQL connectivity, the packaged Alembic head, and the
pgvector extension. A ready instance returns `200`:

```json
{
  "status": "ready",
  "checks": {"database": "reachable", "schema": "current", "vector": "installed"}
}
```

An unavailable dependency returns `503` and stable diagnostic labels without raw
exception or connection details. OpenAI is not a readiness dependency. `GET /health`
remains temporarily available for backward compatibility.

## Update Sources

```http
GET /update-sources
```

Returns configured sources from YAML with their latest collection outcome from the run log.

## Dashboard Updates

```http
GET /updates?window=week&categories=inference-serving&event_types=library-release&limit=30
```

Supported windows are `day`, `week`, `month`, and `all`. Optional repeated query parameters filter `source_names`, `tools`, `categories` (primary topics), `event_types`, `source_types`, and `maturities`. `start` and `end` accept explicit ISO timestamps.

Quarantined records remain stored for diagnosis but are never returned by the
dashboard or RAG retrieval. Successful sparse security issues, breaking changes,
deprecations, and incidents can be published and remain visible when their relevance
tier is `core`. The legacy `include_sparse` option never bypasses ingestion quarantine
or relevance routing.

A source may explicitly publish a trusted official-feed description; the API reports it
as `evidence_level = official_feed_excerpt`. Core items use the source wording directly
and may appear on the dashboard, but their evidence level keeps them out of search
results and generated-answer context.

Publication eligibility is recorded as `ingestion_status`, `extraction_status`, and
`relevance_tier` in typed document columns. The API's `evidence_level` is derived from
them: `full_article`, `official_feed_excerpt` for a published feed excerpt, or
`source_entry`. Source attributes (`organization`, `tool`, `source_type`) come from the
source registry. The
`low_lexical_grounding` evaluation warning never controls product visibility.

The response contains ranked article items, structured summaries, the resolved time range, summary statistics, and available facets.

## Search

```http
POST /search
```

```json
{
  "query": "Which releases added MCP support?",
  "collection": "updates",
  "published_after": "2026-07-01T00:00:00Z",
  "source_names": null,
  "tools": null,
  "categories": null,
  "event_types": null,
  "source_types": null,
  "maturities": null,
  "top_k": 8,
  "search_mode": "hybrid",
  "retrieval_strategy": "standard"
}
```

Results include vector, keyword, recency, and combined scores plus publication metadata.

## Ask

```http
POST /ask
```

`/ask` accepts the same collection, publication, source, tool, taxonomy, retrieval mode, and top-k controls as `/search`, plus similarity and token budgets.

The response separates:

- `citations`: evidence IDs actually referenced in the answer
- `retrieved_chunks`: all evidence available to the model
- `citation_warnings`: invalid or missing citation markers
- `metrics`: embedding, retrieval, LLM, token, and estimated cost measurements

The endpoint is currently non-streaming.
