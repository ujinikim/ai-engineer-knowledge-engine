# API Design

## Health

```http
GET /health
```

## Update Sources

```http
GET /update-sources
```

Returns enabled database-backed source records and collection status.

## Dashboard Updates

```http
GET /updates?window=week&categories=inference-serving&event_types=library-release&limit=30
```

Supported windows are `day`, `week`, `month`, and `all`. Optional repeated query parameters filter `source_names`, `tools`, `categories` (primary topics), `event_types`, `source_types`, and `maturities`. `start` and `end` accept explicit ISO timestamps.

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
