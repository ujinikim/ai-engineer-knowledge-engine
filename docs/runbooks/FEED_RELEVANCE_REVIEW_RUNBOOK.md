# Feed Relevance Review Runbook

## Review File

Review:

```text
backend/data/eval/summaries/feed_relevance_review_sample.json
```

The completed calibration contains:

- 50 full review items
- All 17 configured sources
- 33 reviewed `core` records
- 12 reviewed `contextual` records
- 5 reviewed `excluded` records
- A lightweight recommendation index for all 240 collected documents

The tracked review artifact keeps source links, generated cards, taxonomy, and
decisions, but deliberately excludes full article text. Open `url` or use the local
document store when source verification is needed.

All 50 decisions are recorded in:

```text
backend/data/eval/summaries/feed_relevance_review_decisions_2026-07-27.json
```

The calibration is complete, but the decisions have not yet been applied to stored
document metadata, API filtering, or the UI.

## Tier Meanings

### `core`

Show in the default AI-engineering feed.

### `contextual`

Retain and make searchable, but show only when an **Industry context** filter is
enabled.

### `excluded`

Hide from the normal feed and search experience. Retain the record for provenance,
collection diagnostics, and later policy changes.

## Fields to Edit

For each object in `items`, edit:

```json
{
  "relevance_review": "correct",
  "reviewed_tier": null,
  "reviewed_reasons": [],
  "relevance_notes": ""
}
```

Allowed `relevance_review` values:

- `correct`: accept `recommended_tier`
- `change_required`: set `reviewed_tier` and explain briefly
- `uncertain`: do not force an exclusion; add the uncertainty to
  `relevance_notes`
- `not_reviewed`: untouched

When using `change_required`, for example:

```json
{
  "relevance_review": "change_required",
  "reviewed_tier": "contextual",
  "reviewed_reasons": ["business_or_partnership_context"],
  "relevance_notes": "Relevant ecosystem context, but no concrete technical change."
}
```

## Review Order Used

1. Review all `excluded` recommendations first. These carry the greatest risk
   because the content would disappear from normal product views.
2. Review the `contextual` recommendations.
3. Spot-check the `core` controls for peripheral material that escaped the
   candidate rules.

Pay particular attention to:

- Customer stories that contain real implementation detail
- Partnerships that are actually technical integrations
- Research funds that announce a concrete research result
- Security partnerships that describe an operational security event
- Records with `extraction_status: feed_excerpt_only`, where extraction quality
  rather than relevance is the problem

Sparse-source visibility is a separate axis. A technically relevant article may be
`core` while still being hidden by `default_feed_exclusion_reason:
low_source_detail`.

## After Review

The calibration and validator are complete. Production rollout is intentionally
deferred. The future rollout consists of:

1. Relevance metadata at collection time
2. A reviewed-record backfill
3. Default `core` filtering
4. The **Industry context** UI control
5. Diagnostic-only access to `excluded` records

Every proposed `excluded` item has now been reviewed. Application rollout still
requires the metadata backfill, API behavior, UI control, and regression tests.
The planned LLM classification flow and its safe fallback behavior are recorded in
`../archive/FEED_RELEVANCE_POLICY_PROPOSAL.md`.
