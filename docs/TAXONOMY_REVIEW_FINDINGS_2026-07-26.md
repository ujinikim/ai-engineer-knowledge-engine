# Taxonomy Review Findings — July 26, 2026

## Scope

- Fresh collection: 17 sources, 239 documents, zero source errors
- Human-review sample: 43 documents
- Coverage: every source and every topic, event type, and maturity value present
- Axes reviewed independently: event types, maturity, primary topic
- Stored taxonomy values were not changed during review; the approved corrections
  were subsequently backfilled as described below.

The completed decisions are stored in:

```text
backend/data/eval/summaries/taxonomy_review_sample.json
backend/data/eval/summaries/taxonomy_review_decisions_2026-07-26.json
backend/data/eval/summaries/taxonomy_backfill_report_2026-07-26.json
```

## Implementation Status

Implemented on July 26, 2026:

- Applied every `change_required` decision; `uncertain` decisions were not applied.
- Added versioned-library event invariants for vLLM, LangGraph, Qdrant,
  Transformers, and LiteLLM.
- Kept Ollama's existing `product-release` source policy.
- Fixed attached, separated, dotted, underscored, and uppercase RC parsing, with
  false-positive tests.
- Added research maturity inference for research/benchmark events that do not also
  represent a released artifact.
- Tightened the generation prompt around multi-event materiality, model support,
  security features, and integrations.
- Added `taxonomy_policy_version: 2026-07-26-v1` to stored release metadata.

Backfill outcome:

| Measure | Count |
|---|---:|
| Release documents inspected | 239 |
| Documents with taxonomy changes | 57 |
| Primary-topic changes | 5 |
| Event-type changes | 30 |
| Maturity changes | 26 |
| Missing reviewed IDs | 0 |

The larger maturity count includes seven attached-RC corrections and 19
research/benchmark artifacts changed from `stable` to `research`. A second dry run
reported zero changes, confirming that the backfill is idempotent. The backend suite
passed with 59 tests.

Post-backfill regression:

- 43 of 43 reviewed documents passed.
- 129 of 129 independently reviewed axes passed.
- All 83 `correct`, 32 `change_required`, and 14 `uncertain` axis expectations
  matched their intended stored values.
- The machine-readable result is
  `backend/data/eval/summaries/taxonomy_regression_report_2026-07-26.json`.

## Review Results

| Axis | Correct | Change required | Uncertain |
|---|---:|---:|---:|
| Event types | 20 | 18 | 5 |
| Maturity | 29 | 9 | 5 |
| Primary topic | 34 | 5 | 4 |

Primary topics are comparatively stable. Event types are the main taxonomy-quality
problem.

## Finding 1: Versioned Software Is Frequently Labeled as a Product

The most common reviewed correction was:

```text
product-release -> library-release
```

This affected Qdrant, vLLM, and LangGraph examples. LiteLLM examples also accumulated
`product-release`, `security-issue`, and `engineering-analysis` when the represented
event was principally a versioned library/API-proxy release.

Recommended rule:

- Treat configured versioned package feeds as `library-release`.
- Add `api-change`, `breaking-change`, or `security-issue` only when the card
  materially represents that additional event.
- Do not let the summarization model replace `library-release` with
  `product-release` merely because a version adds important features.

## Finding 2: Model Support Is Being Confused With Model Launch

Transformers releases that add support for named models were labeled
`model-launch`.

Recommended rule:

- A library adding compatibility for a model remains `library-release`.
- Use `model-launch` only when the card represents the formal introduction or
  availability of a new named model.
- A genuine Anthropic model introduction may carry both `model-launch` and
  `product-release` when the model is simultaneously made available through a hosted
  product.

## Finding 3: Release-Candidate Parsing Has a Deterministic Defect

Six reviewed vLLM versions were incorrectly marked `stable`:

```text
v0.24.0rc1
v0.24.0rc2
v0.25.0rc1
v0.25.0rc2
v0.25.0rc3
v0.26.0rc1
```

Recommended rule:

- Recognize attached, hyphenated, underscored, dotted, and uppercase RC forms.
- Use a version-aware expression so words such as `research`, `architecture`,
  `source`, and `PyTorch` do not become false positives.

## Finding 4: Research Artifacts Default to Stable

Three reviewed research or benchmark records should change:

```text
stable -> research
```

Examples include the web-retrieval study, domain-specific OCR benchmark work, and
ScarfBench.

Recommended rule:

- Use `research` when the card represents an experiment, benchmark, proposed method,
  or research artifact not presented as production-ready.
- Do not assign research maturity solely from publication source type.

## Finding 5: Multi-Event Output Is Often Overinclusive

Ninety-nine of 239 records have multiple event types. The sample showed valid and
invalid multi-event cases.

Valid examples:

- New named model made available through a hosted plan:
  `model-launch`, `product-release`
- Hosted capability with an API surface:
  `product-release`, `api-change`
- Technical backend integration article:
  `engineering-analysis`, `integration`
- Library release with an explicit compatibility break:
  `library-release`, `breaking-change`

Invalid patterns:

- Adding `engineering-analysis` to ordinary release notes
- Treating a security feature as a `security-issue`
- Treating availability across several surfaces as an `integration`
- Keeping a source default when the card does not materially represent that event

Recommended rule:

Every event type must be supported by a material claim in the generated card.

## Finding 6: Five Primary-Topic Corrections Are Supported

Recommended reviewed changes:

| Current | Proposed | Reason |
|---|---|---|
| `models-apis` | `inference-serving` | Quantized diffusion inference integration |
| `training-fine-tuning` | `infrastructure-hardware` | TPU kernel authoring and hardware optimization |
| `developer-tools` | `retrieval-data` | Web retrieval research |
| `models-apis` | `evaluation-observability` | Agent migration benchmark |
| `models-apis` | `safety-security` | Public initiative centered on AI risks and concerns |

The other 34 reviewed primary topics were correct. Four peripheral records could not
be cleanly represented.

## Finding 7: Peripheral Corporate and Policy Content Does Not Fit

The unresolved cases were mostly:

- Research funding commitments
- Research funds and agendas
- Public-engagement initiatives
- Legal and policy rulings

These are not naturally represented by the current AI-engineering event, maturity, or
primary-topic axes.

Recommended quick resolution:

1. Do not expand the core engineering taxonomy merely to accommodate a handful of
   peripheral corporate announcements.
2. Retain these records as source evidence.
3. Exclude them from the default engineering feed with a separate relevance policy,
   or admit them only when they contain a concrete technical result or product change.
4. Defer a `program-announcement` or policy/business taxonomy until product demand
   demonstrates that users want this material.

This keeps Phase 2 focused and avoids weakening precise labels such as
`product-release`, `research-result`, and `incident`.

## Finding 8: Ollama Needs One Source-Level Decision

Ollama is a downloadable runtime but is currently configured as `product-release`.
Both interpretations are defensible:

- `library-release`: installable versioned software artifact
- `product-release`: end-user local runtime product

Recommended quick resolution:

Keep Ollama as `product-release` for the current phase because that is the established
source policy. Document it as an explicit exception and revisit only if users expect
Ollama versions alongside package/library releases.

## Recommended Implementation Order

1. Fix RC maturity parsing and add false-positive tests.
2. Make versioned library-source defaults authoritative.
3. Prevent model-support additions from becoming model launches.
4. Tighten prompt rules for multi-event materiality.
5. Add research-maturity inference and regression cases.
6. Apply the five reviewed primary-topic corrections through targeted regeneration or
   backfill.
7. Add a peripheral-content relevance rule rather than expanding taxonomy.
8. Preserve Ollama's existing `product-release` policy as a documented exception.

## Phase-Closure Target

Phase 2 taxonomy work can be considered calibrated when:

- The deterministic RC and library-release contradictions are fixed.
- The 43-item event, maturity, and topic regression passes after regeneration.
- Unresolved peripheral records are excluded from the default engineering feed or
  documented as accepted exceptions.
- Before-and-after distributions and all changed document IDs are saved.

## July 27 Follow-Up and Closure

The closure targets are satisfied:

- The 43-item regression passes all 129 independently reviewed axes.
- RC parsing, versioned-library invariants, research maturity, and material event
  selection are implemented and tested.
- Peripheral content is handled through the separate relevance policy rather than
  expanding the engineering taxonomy.
- Ollama remains the documented `product-release` exception.
- A refreshed ten-item summary sample identified and applied two additional decisions:
  Cloudflare crawler controls moved from `developer-tools` to `retrieval-data`, and
  the monday.com production-agent architecture dropped `product-release` while
  retaining `engineering-analysis`.
- The refreshed sample is now 10/10 `correct` for taxonomy with no unreviewed fields.

The controlled taxonomy remains at 9 primary topics, 14 event types, 7 source types,
and 8 maturity values. Future individual edge cases may receive reviewed overrides;
the vocabulary should not expand without recurring evidence of a missing concept.
