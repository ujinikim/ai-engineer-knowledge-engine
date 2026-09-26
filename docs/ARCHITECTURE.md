# Architecture

## System

```text
Official RSS and Atom feeds
  -> collector worker
  -> normalization and URL/hash deduplication
  -> structured article summary and controlled taxonomy
  -> original-text chunking and embeddings
  -> PostgreSQL + pgvector

React dashboard
  -> GET /updates with time and facet filters
  -> ranked article records

Analysis panel
  -> POST /ask with the same filters
  -> vector + keyword + recency retrieval
  -> context budget
  -> OpenAI answer
  -> used citations + retrieved evidence + metrics
```

## Article corpus

The active corpus contains dated articles collected from configured update sources.
The earlier documentation corpus and ingestion path have been removed.

## Update Storage

`backend/data/update_sources.yml` defines the sources used by collection, dashboard queries, and article retrieval. `collection_source_runs` records the outcome of each source attempt, grouped by `run_id`; it does not store source settings. Articles are stored in `documents` with `source_type = release` for schema compatibility. Original text remains in `raw_text` and pgvector-backed chunks. Generated feed fields and taxonomy values live in JSON metadata.

Generated metadata includes `display_headline`, `summary`, `why_it_matters`,
`key_points`, `primary_topic`, `event_types`, `entity_tags`, `source_type`, `maturity`,
and `taxonomy_policy_version`. Taxonomy v2 assigns exactly one of six broad primary
topics and at most one of five events in the existing summary-model call. Strict schema
validation prevents invented categories. The legacy `topic_tags` field remains present
but empty for API compatibility. These values drive the feed but do not replace original
evidence during RAG.

Retrieval only considers the article corpus.

## Ranking

The dashboard ranking is deterministic:

```text
importance = 40% source credibility + 40% freshness + 10% content detail + 10% maturity
```

First-party sources receive high credibility weights. Stable and generally available items receive a preference over release candidates, development builds, and previews. The score is transparent and is not an editorial truth claim.

Hybrid retrieval for release records uses:

```text
60% vector relevance + 25% normalized keyword relevance + 15% recency
```

Final retrieval is capped at two chunks per document so one long release note cannot
consume the entire context window for a multi-update question. Release retrieval derives
eligibility from the typed `ingestion_status`, `extraction_status`, and `relevance_tier`
columns.
Core records are retrieved by default; contextual records require explicit inclusion;
excluded, quarantined, and official-feed-excerpt records cannot enter LLM context.

## Freshness

`collect_updates.py` can run once or remain active with `--interval-minutes 60`. Collection normalizes URLs and uses canonical URLs plus content hashes to prevent equivalent links from becoming new records. Unchanged entries retain generated metadata and skip both summarization and embedding. A deterministic publication gate runs before model work, and a failed refresh cannot overwrite an existing published article.

In a hosted deployment, the collector should run as a separate scheduled worker rather than inside web request handling.

## Current Limitations

- Release entries are not clustered into cross-source stories.
- HTML-only publications use explicit listing-link patterns and article-content selectors. The collector does not perform broad crawling.
- Ranking has no engagement signal.
- The API response is not streamed yet.
