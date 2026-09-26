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

Each entry requires a unique slug, tool, organization, default primary topic, source type, feed URL, homepage URL, and credibility weight. Broad feeds can define `include_terms` and `exclude_terms`. HTML sources whose article
pages keep the publication date outside the content selector can set `date_selector`. Remove retired sources from the registry after their stored data is cleaned up.

## Collect Once

```bash
uv run python scripts/collect_updates.py --max-items 12
```

Collect one or more sources during remediation:

```bash
uv run python scripts/collect_updates.py --max-items 12 --source langchain-blog
uv run python scripts/collect_updates.py --max-items 12 \
  --source langchain-blog --source microsoft-foundry --source anthropic-engineering
```

Normal collection loads all configured sources. An explicit `--source` selection
limits a run to listed configured slugs; removed slugs are rejected.

The collector:

1. Tries to acquire the PostgreSQL collector advisory lock. If another manual or
   scheduled run owns it, the new run reports `collection_already_running` and exits
   successfully without fetching or writing anything.
2. Starts a per-source collection attempt identified by the run ID.
3. Fetches official RSS, Atom, or configured HTML discovery pages. Feed and article
   requests are retried up to three times with short backoff for timeouts,
   connection errors, and HTTP 408, 429, 500, 502, 503, or 504. Each retry is logged
   as `fetch_retry`; other HTTP errors fail immediately.
4. Applies configured relevance filters.
5. Extracts source text and publication time. When configured full-article fetching
   fails, it retains the source-entry excerpt and logs `full_article_fetch_failed`
   rather than treating the whole collection as failed. Entries skipped for a missing
   required publication date are logged as `source_entry_skipped`.
6. Applies the deterministic publication gate. Title-only extraction and ordinary
   sparse records are stored as `quarantined`. Failed full-article hydration is also
   quarantined unless the source explicitly permits its official feed excerpt as
   dashboard-only evidence. Sparse `alert` records may publish when extraction
   itself succeeded.
7. Generates a structured article summary and taxonomy only for new or changed
   content eligible for RAG. Quarantined candidates are not summarized, chunked,
   embedded, shown in the feed, or returned by retrieval. Approved official feed
   excerpts use the source description directly, appear in the dashboard, and skip
   summarization, chunks, embeddings, and RAG.
8. Upserts by normalized URL, canonical URL, or matching source/title/content hash.
   Tracking parameters and equivalent default ports do not create new records.
9. Preserves a previously published article when a later fetch is quarantined and
   logs the attempt as `stored_article_retained`.
10. Skips summarization and embeddings when published content is unchanged.
11. Replaces original-text chunks and embeddings when published content changes.
12. Records collection time, per-source quarantine counts, and source errors.

Taxonomy v2 uses the same model request as summary generation. Its strict response
schema permits one of six broad `primary_topic` values and exactly one broad event.
Source defaults are fallbacks, not automatically attached labels. Deterministic
fallbacks follow the same constraints, and `topic_tags` is stored as an empty list.

The lock is held on a dedicated database connection for the whole run, so commits
inside the collector do not release it. A normal completion unlocks explicitly; a
crash or lost connection is cleaned up automatically by PostgreSQL.

Collector output is newline-delimited structured JSON. Each run has a `run_id` joining
start, per-source, token/cost, completion, overlap, and failure events. See
`OBSERVABILITY_RUNBOOK.md` for the event catalog and sensitive-data rules.

## Backfill Existing Updates

```bash
uv run python scripts/maintenance/backfill_article_metadata.py
uv run python scripts/maintenance/backfill_source_detail.py
uv run python scripts/maintenance/backfill_extraction_metadata.py
uv run python scripts/maintenance/backfill_taxonomy_v2.py --dry-run --limit 25
```

Use `--force` to regenerate summaries after changing the prompt or taxonomy. Use `--limit N` for a quality sample before a full run.
The source-detail backfill is idempotent and supports `--dry-run`; it updates only
visibility metadata and does not regenerate summaries or embeddings.
The extraction-metadata backfill is also idempotent and supports `--dry-run`. It
separates source completeness from summary-generation provenance without
regenerating source text, summaries, taxonomy, chunks, or embeddings.

The taxonomy-v2 command is dry-run by default and reports every before/after value.
It scopes itself to enabled, published update sources, skips records already on v2,
and leaves disabled, quarantined, and legacy documentation records alone. Full-text
articles use the configured summary model for constrained classification; approved
feed excerpts use deterministic classification. After review, add `--apply` to update
taxonomy metadata only. `--source`, `--model`, and `--force` support controlled trials.
The command never rewrites summaries, chunks, or embeddings.

## Extraction and Summary Provenance

These metadata fields describe independent stages:

| Field | Purpose |
|---|---|
| `extraction_status` | `full_article`, `source_entry`, `feed_excerpt_only`, or `title_only` |
| `summary_input_source` | The text supplied to summarization: full article, source entry, feed excerpt, or title |
| `summary_generated_by` | Model and source type, or `deterministic-fallback` when model generation failed |
| `ingestion_status` | `published` when eligible for a user-facing surface or `quarantined` when retained only for diagnosis |
| `ingestion_failure_codes` | Deterministic reasons such as `article_hydration_failed`, `title_only_source`, or `insufficient_source_detail` |
| `ingestion_warning_codes` | Non-blocking limitations on published evidence, including an approved feed fallback |
| `quarantine_reason` | The primary ingestion failure code |
| `evidence_level` | `full_article`, `source_entry`, or `official_feed_excerpt` |
| `relevance_tier` | `core`, `contextual`, or `excluded`; classified independently from evidence quality |
| `relevance_reason` | Evidence-based explanation for the relevance route |
| `rag_eligible` | Derived compatibility value: published, non-excerpt evidence that is not excluded |
| `default_feed_eligible` | Derived compatibility value: published evidence with `core` relevance |

For example, the OpenAI source explicitly permits its official feed description as
a dashboard announcement when the configured full-page fetch is blocked:

```json
{
  "extraction_status": "feed_excerpt_only",
  "summary_input_source": "feed_excerpt",
  "ingestion_status": "published",
  "ingestion_failure_codes": [],
  "ingestion_warning_codes": [
    "article_hydration_failed",
    "insufficient_source_detail"
  ],
  "evidence_level": "official_feed_excerpt",
  "rag_eligible": false,
  "summary_generated_by": "source-excerpt",
  "default_feed_eligible": true,
  "default_feed_exclusion_reason": null
}
```

`hydration_status` remains temporarily for backward compatibility. New code should
use the structured extraction fields.

Per-attempt diagnostics are log events, not document metadata. A failed full-page
fetch logs `full_article_fetch_failed` with the source slug, URL without query string,
HTTP status, and a controlled `error_code` such as `http_forbidden`, `http_not_found`,
`http_error`, `network_error`, or `content_incomplete`.

## Run Continuously

```bash
uv run python scripts/collect_updates.py --max-items 12 --interval-minutes 60
```

The interval option remains useful for local development. Production uses a one-shot
command started every six hours by a systemd timer. The advisory lock protects both
forms as well as manual invocations. The dashboard reads PostgreSQL and never waits
for collection.

## Inspect Data

```bash
docker compose exec postgres psql -U postgres -d knowledge_engine \
  -c "SELECT source_name, count(*) FROM documents WHERE source_type = 'release' GROUP BY 1 ORDER BY 1;"
```

Check collector health:

```bash
docker compose exec postgres psql -U postgres -d knowledge_engine \
  -c "SELECT run_id, source_slug, finished_at, status, matched_items, updates_created, error FROM collection_source_runs ORDER BY finished_at DESC LIMIT 20;"
```

Review the quarantine without exposing it to retrieval:

```bash
docker compose exec postgres psql -U postgres -d knowledge_engine \
  -c "SELECT source_name, doc_metadata->>'quarantine_reason' AS reason, count(*) FROM documents WHERE doc_metadata->>'ingestion_status' = 'quarantined' GROUP BY 1, 2 ORDER BY 1, 2;"
```
