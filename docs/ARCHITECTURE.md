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

## Collections

- `updates`: dated official articles and release records collected from feeds
- `docs`: stable documentation pages from the original RAG prototype
- `all`: both collections when a question needs recent changes and background documentation

## Update Storage

`update_sources` stores source registry, active state, and collection health. Scheduled collection, dashboard queries, and release retrieval use only enabled sources. Disabling a source preserves its documents and chunks so the decision can be reversed without recollecting historical data. Feed entries are stored in `documents` with `source_type = release` for collection compatibility. Original text remains in `raw_text` and pgvector-backed chunks. Generated feed fields and taxonomy values live in JSON metadata.

Generated metadata includes `display_headline`, `summary`, `why_it_matters`,
`key_points`, `primary_topic`, `event_types`, `entity_tags`, `source_type`, `maturity`,
and `taxonomy_policy_version`. Taxonomy v2 assigns exactly one of six broad primary
topics and at most one of five events in the existing summary-model call. Strict schema
validation prevents invented categories. The legacy `topic_tags` field remains present
but empty for API compatibility. These values drive the feed but do not replace original
evidence during RAG.

This preserves one retrieval path while keeping collections filterable.

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

Documentation retrieval retains the previous vector/keyword weighting without a recency boost.

Final retrieval is capped at two chunks per document so one long release note cannot
consume the entire context window for a multi-update question. Release retrieval derives
eligibility from canonical `ingestion_status`, `evidence_level`, and `relevance_tier`.
Core records are retrieved by default; contextual records require explicit inclusion;
excluded, quarantined, and official-feed-excerpt records cannot enter LLM context.
Legacy `rag_eligible` and `default_feed_eligible` metadata remain compatibility outputs
and are not trusted as policy inputs.

## Freshness

`collect_updates.py` can run once or remain active with `--interval-minutes 60`. Collection normalizes URLs and uses canonical URLs plus content hashes to prevent equivalent links from becoming new records. Unchanged entries retain generated metadata and skip both summarization and embedding. A deterministic publication gate runs before model work, and a failed refresh cannot overwrite an existing published article.

In a hosted deployment, the collector should run as a separate scheduled worker rather than inside web request handling.

## Current Limitations

- Release entries are not clustered into cross-source stories.
- HTML-only publications use explicit listing-link patterns and article-content selectors. The collector does not perform broad crawling.
- Ranking has no engagement signal.
- The API response is not streamed yet.
