# Feed Relevance Policy Proposal

## Goal

Decide whether a collected article belongs in the default AI-engineering feed
without distorting its topic, event type, or maturity.

Taxonomy answers **what the article is about**. Feed relevance answers **where the
article should appear**. These must remain separate metadata axes.

## Recommended Three-Tier Model

### `core`

Shown in the default feed.

Use when the article materially represents at least one of:

- Model, product, library, runtime, or API release/change
- Concrete integration
- Engineering implementation or architecture analysis
- Original research or benchmark result relevant to building/evaluating AI systems
- Security issue, incident, breaking change, deprecation, or pricing change
- Substantive technical tutorial

### `contextual`

Retained and searchable, but hidden from the default feed. Expose through an
**Industry context** filter.

Use for:

- Funding commitments and research funds
- Corporate partnerships without a concrete technical integration
- Legal or policy decisions
- Public-engagement initiatives
- Business announcements that affect the AI ecosystem but do not contain a
  technical result or product change

When the classifier is uncertain between `core` and exclusion, prefer
`contextual`. This avoids silently losing useful evidence.

### `excluded`

Not shown in normal feed or search results. Retain the source record for provenance
and collection diagnostics.

Use for:

- Event promotion with no technical content
- Hiring and employer-brand content
- Generic marketing or customer stories without engineering detail
- Navigation/index pages and extraction failures
- Content unrelated to the product's AI-engineering scope

## Metadata

Store:

```json
{
  "feed_relevance_tier": "core",
  "feed_relevance_reasons": ["technical_release_or_change"],
  "feed_relevance_confidence": 0.96,
  "feed_relevance_policy_version": "2026-07-26-v1",
  "feed_relevance_review_status": "unreviewed"
}
```

Reasons should come from a controlled list so decisions can be audited.

Initial controlled reasons include:

- `technical_release_or_change`
- `research_or_benchmark`
- `security_or_operational_event`
- `engineering_analysis`
- `technical_tutorial`
- `measured_customer_deployment`
- `event_or_community_update`
- `funding_or_research_program`
- `policy_or_legal_context`
- `public_or_community_initiative`
- `business_or_partnership_context`
- `general_strategy_or_societal_context`
- `customer_story_or_case_study`
- `promotional_or_brand_content`
- `generic_getting_started_content`
- `unclear_engineering_relevance`

## Decision Order

1. Reject clearly unrelated content as `excluded`.
2. Record extraction completeness separately and apply existing sparse-source
   visibility rules. Incomplete extraction does not make a relevant article
   irrelevant.
3. Detect concrete technical events or artifacts; classify these as `core`.
4. Classify business, funding, public-engagement, and legal/policy records without a
   concrete technical event as `contextual`.
5. Send low-confidence cases to `contextual`, never directly to `excluded`.
6. Apply manual overrides last and preserve the reviewer note.

Important sparse events (`security-issue`, `breaking-change`, `deprecation`, and
`incident`) retain their current default-feed override.

## Implementation Recommendation

Use a hybrid classifier:

- Deterministic rules for extraction failures, known technical release feeds, and
  important operational events.
- A small structured model classification for mixed news/editorial sources.
- Explicit manual overrides for reviewed edge cases.

Do not use a single keyword list or a raw relevance score as the final decision.
Keywords such as “research,” “security,” and “model” occur in both core engineering
work and peripheral announcements.

## Deferred Production Automation

**Status (July 27, 2026):** design recorded for later; not implemented.

The completed human review is a calibration and regression dataset. Its decision
file preserves judgments for the exact reviewed records, but it must not be treated
as a classifier for newly collected articles.

When production automation is implemented, each new article should follow this
flow:

1. Extract the available source content.
2. Generate the summary and taxonomy metadata.
3. Ask an LLM for one structured relevance tier, zero or more controlled reason
   tags, a confidence score, and short source-grounded evidence.
4. Validate the response in application code and apply fixed precedence rules.
5. Store the relevance decision separately from extraction completeness.
6. Calculate product visibility from both relevance and source-detail metadata.

The expected structured result is:

```json
{
  "feed_relevance_tier": "core",
  "feed_relevance_reasons": [
    "technical_release_or_change",
    "business_or_partnership_context"
  ],
  "feed_relevance_confidence": 0.91,
  "feed_relevance_evidence": [
    "The article introduces a new API endpoint."
  ],
  "feed_relevance_review_required": false,
  "feed_relevance_policy_version": "future-v1"
}
```

Application code retains final control:

- A substantive technical, security, or operational event takes precedence and
  makes a mixed article `core`.
- Business, policy, funding, or ecosystem context without a concrete technical
  change is `contextual`.
- Only clearly irrelevant or non-useful material is automatically `excluded`.
- A failed or invalid model response falls back to `contextual` with
  `feed_relevance_review_required: true`; it must never silently exclude a record.
- Incomplete extraction is not evidence of irrelevance. A `core` article may still
  be hidden from the default feed by the separate sparse-source visibility policy.

Before enabling this in production, evaluate the classifier against the completed
50-record human calibration and require the acceptance targets below. Until then,
new records do not receive automatic relevance-tier metadata.

## Rollout

1. Label the already-reviewed peripheral examples as a calibration set.
2. Generate a 40–60 item stratified relevance review containing likely `core`,
   `contextual`, and `excluded` records.
3. Tune for high recall on `core`; measure false exclusions separately.
4. Backfill only after review.
5. Default the UI to `core`, add an **Industry context** toggle, and keep excluded
   records available only to diagnostics/admin workflows.

## Acceptance Target

- Zero reviewed security, breaking, deprecation, or incident records wrongly hidden.
- At least 95% recall for reviewed `core` records.
- No low-confidence record automatically assigned to `excluded`.
- Every non-core record has a visible, auditable reason.
