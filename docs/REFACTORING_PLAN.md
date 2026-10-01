# Refactoring Plan

Goal: make the codebase easy to navigate and own. Every phase is behavior-preserving:
the API contract does not change, and each phase lands as its own commit that passes
tests, lint, and a real collection run.

## Phase 1: Readable ingestion (done)

- `pipeline.py` runs a collection (sources, retries, run records); `ingest.py` decides
  what one entry becomes. The 342-line `_upsert_entry` is now `ArticleIngestor.ingest`,
  39 lines.
- `candidate.py` prepares an entry; `store.py` owns database reads and writes, with one
  `save_article` replacing five copied create-or-update blocks.
- The extraction mixin became plain functions: `fetch.py` (HTTP and retries) and
  `parsing.py` (feeds, HTML, dates).
- `summary.py` keeps summarizing only; prompts and schemas live in `prompts.py`, and
  the three-step taxonomy classifier in `taxonomy_classifier.py`, which returns a
  named result instead of an eight-item tuple.
- Characterization tests pin every ingestion route and the classifier.
- Follow-up readability pass: URL helpers in `urls.py` (no import cycle between
  `candidate` and `store`), `SourceConfig` documents every source option in one typed
  place, and the redundant `hydration_status` is gone (`extraction_status` says it).

## Phase 2: Consistent names and dead code

- Class names match their files (`IngestionPipeline`, `SearchService`, `FeedService`) (done).
- One word per concept: "article" internally; "update" only in API paths. Add a short
  glossary to `ARCHITECTURE.md`.
- Remove legacy taxonomy lists (the database now rejects legacy values), defensive
  `getattr(document, ...)` fallbacks left from untyped rows, and `datetime.utcnow`.

## Phase 3: Scripts (done)

- Scripts run as `python -m scripts.<module>`; the 17 `sys.path.append` lines are gone.
  The image sets `PYTHONPATH=/app`, so the production command
  `python scripts/collect_updates.py` is unchanged (the Terraform user-data template
  replaces the instance on change, so it was deliberately not edited), and CI sets
  `PYTHONPATH: backend` for its verification step.
- Removed the `_source_config.py` wrapper; scripts use `app.sources.sources_by_slug()`.
- Retired the taxonomy v1 review tools and archived their runbook, and removed hardcoded
  article IDs and titles from removed sources in `prepare_feed_relevance_review.py`
  (with the five tests that only pinned those lookups).
- Left in place: the `relevance` entry in the taxonomy v2 review output, which keeps
  existing review keys stable.

## Phase 4: Tests (done)

- `tests/` mirrors `app/`; each file covers one module. Old catch-all files were split
  by subject (for example `test_article_taxonomy.py` became `test_taxonomy.py`,
  `test_summary.py`, `test_prompts.py`, `test_parsing.py`, and `test_fetch.py`).
- `tests/factories.py` replaces five copies of `make_document` and uses real column
  names; `tests/fakes.py` replaces six copies of a fake database and a "must not run"
  stub. The old fixtures still set `doc_metadata` and `evidence_level`, which no
  longer exist.
- One test removed: it set a stored `summary_quality_warnings` value that nothing
  stores or reads, so it could not fail.

## Phase 5: Frontend

- Move `App.tsx` state into hooks (`useFeed`, `useAsk`, `useUrlFilters`) and components
  into `components/`.
- Add a linter to the frontend build.

## Phase 6: Docs

- Consolidate overlapping planning docs; keep README, ARCHITECTURE, DECISIONS, and
  ROADMAP, and archive the rest.
- Add an "article journey" map to `ARCHITECTURE.md`: feed, fetch, decide, summarize,
  store, then feed and search, with the file responsible for each step.
