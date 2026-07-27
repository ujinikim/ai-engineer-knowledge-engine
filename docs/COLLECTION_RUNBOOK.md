# Collection Runbook

## Prepare PostgreSQL

```bash
docker compose up -d postgres
cd backend
uv sync
uv run python scripts/create_db.py
```

## Review Sources

Update sources live in:

```text
backend/data/update_sources.yml
```

Each entry requires a unique slug, tool, organization, default primary topic, source type, feed URL, homepage URL, and credibility weight. Broad feeds can define `include_terms` and `exclude_terms`.

## Collect Once

```bash
uv run python scripts/collect_updates.py --max-items 12
```

Collect one or more sources during remediation:

```bash
uv run python scripts/collect_updates.py --max-items 12 --source the-batch
uv run python scripts/collect_updates.py --max-items 12 \
  --source the-batch --source import-ai --source anthropic-news
```

The collector:

1. Registers or updates source records.
2. Fetches official RSS, Atom, or configured HTML discovery pages.
3. Applies configured relevance filters.
4. Extracts source text and publication time. When configured full-article fetching
   fails, it retains the source-entry excerpt and records structured fetch
   diagnostics rather than treating the whole collection as failed.
5. Generates a structured article summary and taxonomy for new or changed content.
6. Classifies source detail and stores default-feed visibility metadata. Sparse
   records remain searchable but are suppressed from the default feed unless they
   represent an important operational event.
7. Upserts by canonical URL.
8. Skips summarization and embeddings when the content hash is unchanged.
9. Replaces original-text chunks and embeddings when content changes.
10. Records collection time and source errors.

The Batch uses nested issue discovery to store individual stories. Import AI uses explicit newsletter delimiters to store independently retrievable stories. Parent issue and newsletter URLs are retained in document metadata.

## Backfill Existing Updates

```bash
uv run python scripts/backfill_article_metadata.py
uv run python scripts/backfill_source_detail.py
uv run python scripts/backfill_extraction_metadata.py
```

Use `--force` to regenerate summaries after changing the prompt or taxonomy. Use `--limit N` for a quality sample before a full run.
The source-detail backfill is idempotent and supports `--dry-run`; it updates only
visibility metadata and does not regenerate summaries or embeddings.
The extraction-metadata backfill is also idempotent and supports `--dry-run`. It
separates source completeness from summary-generation provenance without
regenerating source text, summaries, taxonomy, chunks, or embeddings.

## Extraction and Summary Provenance

These metadata fields describe independent stages:

| Field | Purpose |
|---|---|
| `extraction_status` | `full_article`, `source_entry`, `feed_excerpt_only`, `title_only`, or `parent_section_fallback` |
| `summary_input_source` | The text supplied to summarization: full article, source entry, feed excerpt, title, or parent section |
| `full_article_fetch_attempted_at` | Timestamp of the latest configured full-page attempt |
| `full_article_fetch_http_status` | HTTP response status when one was available |
| `full_article_fetch_error_code` | Controlled code such as `http_forbidden`, `http_not_found`, `http_error`, `network_error`, or `content_incomplete` |
| `summary_generated_by` | Model and source type, or `deterministic-fallback` when model generation failed |
| `default_feed_eligible` | Whether the record is visible in the default feed |

For example, an official feed excerpt can be successfully summarized while still
being hidden for insufficient source detail:

```json
{
  "extraction_status": "feed_excerpt_only",
  "full_article_fetch_http_status": 403,
  "full_article_fetch_error_code": "http_forbidden",
  "summary_input_source": "feed_excerpt",
  "summary_generated_by": "gpt-4.1-mini:official-product-news",
  "default_feed_eligible": false,
  "default_feed_exclusion_reason": "low_source_detail"
}
```

`hydration_status` and `hydration_error` remain temporarily for backward
compatibility. New code should use the structured extraction fields.

## Run Continuously

```bash
uv run python scripts/collect_updates.py --max-items 12 --interval-minutes 60
```

Run this as a separate worker process. The dashboard reads PostgreSQL and never waits for collection.

## Inspect Data

```bash
docker compose exec postgres psql -U postgres -d knowledge_engine \
  -c "SELECT source_name, count(*) FROM documents WHERE source_type = 'release' GROUP BY 1 ORDER BY 1;"
```

Check collector health:

```bash
docker compose exec postgres psql -U postgres -d knowledge_engine \
  -c "SELECT slug, last_collected_at, last_error FROM update_sources ORDER BY slug;"
```

## Existing Documentation Collection

The original curated documentation pipeline remains available:

```bash
uv run python scripts/ingest.py
```
