# Taxonomy Review Runbook

The active review artifact is:

```text
backend/data/eval/summaries/taxonomy_review_sample.json
```

It was generated after a fresh collection of all 17 configured sources. The artifact
contains:

- `items`: 43 public-safe human-review records with source links and generated cards
- `all_assignments`: a concise index of all 239 stored taxonomy assignments
- `collection_summary`: collection-wide topic, event, maturity, and review-focus counts
- `change_history`: every regeneration and the reason for it

The 43-item sample covers every source and every topic, event type, and maturity value
present in the refreshed collection. It prioritizes release-candidate mismatches,
versioned libraries missing `library-release`, and libraries labeled as model
launches.

Full source text is deliberately excluded from the tracked artifact. Open each
item's `url` or query the locally stored document when source verification is needed.

## Review Order

Review one axis across the entire sample before moving to the next:

1. `event_types`
2. `maturity`
3. `primary_topic`

Do not attempt to settle all three axes for one item at once. Reviewing one axis at a
time produces more consistent decisions.

Use `../archive/TAXONOMY_REMEDIATION_PLAN.md` for the proposed definitions and decision
boundaries.

## Step 1: Event Types

For each object under `items`, compare:

```json
"configured_defaults": {
  "event_types": ["library-release"]
},
"generated_taxonomy": {
  "event_types": ["product-release"]
}
```

Then set:

```json
"event_types_review": "correct"
```

when the generated event types should remain unchanged.

When they should change:

```json
"event_types_review": "change_required",
"proposed_event_types": ["library-release"],
"taxonomy_notes": "Versioned Qdrant package release; no user-facing hosted product launch is represented."
```

When a policy decision is genuinely unresolved:

```json
"event_types_review": "uncertain",
"taxonomy_notes": "Ollama can be treated as either a downloadable runtime release or a product release; apply the final source policy."
```

Questions to ask:

- What materially happened?
- Is this a model, product, library, API, integration, research result, benchmark,
  analysis, tutorial, or operational event?
- Does every assigned event type appear materially in the generated card?
- Is `product-release` being used only because something was announced?
- Does a versioned installable package require `library-release`?

## Step 2: Maturity

After every event review is complete, set one of:

```json
"maturity_review": "correct"
```

or:

```json
"maturity_review": "change_required",
"proposed_maturity": "release-candidate",
"taxonomy_notes": "The version is v0.24.0rc2."
```

Treat maturity as the lifecycle of the principal announced artifact or capability, not
the publication type.

Questions to ask:

- Does the source explicitly say GA, beta, preview, RC, alpha, experimental,
  research, or deprecated?
- Is `stable` supported, or merely the fallback?
- Is the article describing research without a production-ready artifact?

## Step 3: Primary Topic

After event and maturity decisions stabilize, set:

```json
"primary_topic_review": "correct"
```

or:

```json
"primary_topic_review": "change_required",
"proposed_primary_topic": "retrieval-data",
"taxonomy_notes": "The principal result concerns web retrieval failure; evaluation is secondary."
```

Questions to ask:

- What single engineering subject best represents the card?
- What would a user expect when filtering by that topic?
- Is the configured default a narrow-source prior or a broad-publication fallback?
- Should another subject be represented as a secondary topic tag instead?

## Allowed Review Values

Every axis accepts:

```text
not_reviewed
correct
change_required
uncertain
```

Use `taxonomy_notes` for evidence and competing interpretations. When multiple axes
need changes, place all explanations in the same note and name each axis explicitly.

## Progress Checks

From `backend`:

```bash
jq '{
  event_remaining: [.items[] | select(.event_types_review == "not_reviewed")] | length,
  maturity_remaining: [.items[] | select(.maturity_review == "not_reviewed")] | length,
  topic_remaining: [.items[] | select(.primary_topic_review == "not_reviewed")] | length
}' data/eval/summaries/taxonomy_review_sample.json
```

List only event decisions still needing review:

```bash
jq '.items[]
  | select(.event_types_review == "not_reviewed")
  | {
      source_name,
      title,
      configured: .configured_defaults.event_types,
      generated: .generated_taxonomy.event_types,
      review_focus
    }' data/eval/summaries/taxonomy_review_sample.json
```

## Regeneration

Do not regenerate the artifact while manually reviewing it unless the underlying
source or taxonomy has changed. When regeneration is required:

```bash
cd backend
uv run python scripts/reviews/prepare_taxonomy_review.py \
  --sample-size 43 \
  --change-note "Describe exactly what changed."
```

Ratings are preserved only when the source content and generated taxonomy produce the
same `review_key`. The artifact's `change_history` records each regeneration.
