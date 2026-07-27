# Feed Relevance Review Runbook

## Review File

Review:

```text
backend/data/eval/summaries/feed_relevance_review_sample.json
```

The file contains:

- 50 full review items
- All 17 configured sources
- 31 proposed `core` controls
- 10 proposed `contextual` records
- 9 proposed `excluded` records
- A lightweight recommendation index for all 239 collected documents

The recommendations are proposals only. They have not been applied to stored
metadata or the UI.

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

## Recommended Review Order

1. Review all nine `excluded` recommendations first. These carry the greatest risk
   because the content would disappear from normal product views.
2. Review the ten `contextual` recommendations.
3. Spot-check the 31 `core` controls for peripheral material that escaped the
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

Run the relevance validator and create a before-change baseline. Then implement:

1. Relevance metadata at collection time
2. A reviewed-record backfill
3. Default `core` filtering
4. The **Industry context** UI control
5. Diagnostic-only access to `excluded` records

No automatic exclusion should be enabled until every proposed `excluded` item has
been reviewed.
