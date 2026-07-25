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
4. Extracts source text and publication time.
5. Generates a structured article summary and taxonomy for new or changed content.
6. Upserts by canonical URL.
7. Skips summarization and embeddings when the content hash is unchanged.
8. Replaces original-text chunks and embeddings when content changes.
9. Records collection time and source errors.

The Batch uses nested issue discovery to store individual stories. Import AI uses explicit newsletter delimiters to store independently retrievable stories. Parent issue and newsletter URLs are retained in document metadata.

## Backfill Existing Updates

```bash
uv run python scripts/backfill_article_metadata.py
```

Use `--force` to regenerate summaries after changing the prompt or taxonomy. Use `--limit N` for a quality sample before a full run.

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
