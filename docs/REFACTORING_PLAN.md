# Refactoring Plan

Goal: make the codebase easy to navigate and own. Every phase is behavior-preserving:
the API contract does not change, and each phase lands as its own commit that passes
tests, lint, and a real collection run.

## Phase 1: Readable ingestion (done)

- `pipeline.py` routes each entry through small named steps; the 342-line
  `_upsert_entry` is now 39 lines.
- `candidate.py` prepares an entry; `store.py` owns database reads and writes, with one
  `save_article` replacing five copied create-or-update blocks.
- The extraction mixin became plain functions: `fetch.py` (HTTP and retries) and
  `parsing.py` (feeds, HTML, dates).
- `summary.py` keeps summarizing only; prompts and schemas live in `prompts.py`, and
  the three-step taxonomy classifier in `taxonomy_classifier.py`, which returns a
  named result instead of an eight-item tuple.
- Characterization tests (`test_ingestion_paths.py`, `test_taxonomy_classifier.py`)
  pin every ingestion route.

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

## Phase 4: Tests

- Mirror the app layout: `tests/ingestion/`, `tests/serving/`, `tests/evaluation/`.
- Share one set of document and chunk factories in `conftest.py`.

## Phase 5: Frontend

- Move `App.tsx` state into hooks (`useFeed`, `useAsk`, `useUrlFilters`) and components
  into `components/`.
- Add a linter to the frontend build.

## Phase 6: Docs

- Consolidate overlapping planning docs; keep README, ARCHITECTURE, DECISIONS, and
  ROADMAP, and archive the rest.
- Add an "article journey" map to `ARCHITECTURE.md`: feed, fetch, decide, summarize,
  store, then feed and search, with the file responsible for each step.
