# Taxonomy Remediation Plan

This plan addresses taxonomy quality in a deliberate order so deterministic defects
are fixed before subjective classification policy is tuned. It is based on the July
25, 2026 audit of 194 stored release documents.

The active record-level workflow is documented in `TAXONOMY_REVIEW_RUNBOOK.md`.
Following the fresh all-source collection, its review artifact indexes 239 documents
and provides a 43-item stratified human-review sample.

The completed review findings are summarized in
`TAXONOMY_REVIEW_FINDINGS_2026-07-26.md`.

No stored taxonomy values should be changed until the relevant decision gate is
accepted and a before-change baseline is preserved.

## Baseline

Current primary-topic distribution:

| Primary topic | Documents |
|---|---:|
| `models-apis` | 71 |
| `developer-tools` | 37 |
| `infrastructure-hardware` | 26 |
| `inference-serving` | 21 |
| `agents-orchestration` | 13 |
| `training-fine-tuning` | 11 |
| `retrieval-data` | 10 |
| `safety-security` | 4 |
| `evaluation-observability` | 1 |

Current high-volume event types:

| Event type | Documents |
|---|---:|
| `product-release` | 117 |
| `engineering-analysis` | 58 |
| `library-release` | 45 |
| `research-result` | 26 |
| `integration` | 24 |
| `model-launch` | 14 |

Current maturity distribution:

| Maturity | Documents |
|---|---:|
| `stable` | 171 |
| `development` | 13 |
| `release-candidate` | 9 |
| `preview` | 1 |
| `research` | 0 |

The concentration in `product-release` and `stable` indicates that both labels are
currently acting as broad defaults rather than precise classifications.

## Step 1: Define Event-Type Semantics

### Decision gate

Approve written definitions before changing the prompt or stored data.

### Recommended definitions

#### `model-launch`

A new named model, model family, or materially distinct model generation becomes
available or is formally introduced.

Do not use for:

- A framework or library version
- A model-support addition inside a library
- A benchmark of an existing model
- An article that merely discusses models

#### `product-release`

A user-facing product, hosted service, managed capability, or substantial product
feature becomes available or materially changes.

Do not use as a generic announcement label.

#### `library-release`

An installable framework, SDK, runtime, database, package, CLI, or versioned
open-source software artifact is released or updated.

Examples include vLLM, LangGraph, Qdrant, Transformers, LiteLLM, Ollama, and PyTorch
version releases when the installable software artifact is the event.

#### `api-change`

An API contract, endpoint, parameter, response, limit, or supported behavior changes.
It may accompany `library-release` or `product-release` when both facts are material.

#### `integration`

Two named products, platforms, libraries, or services gain explicit interoperability.
General compatibility discussion is not enough.

#### `research-result`

An original study, experiment, paper, or research program reports a method or finding.
Editorial coverage may receive this label when the card materially represents the
underlying research result.

#### `benchmark-result`

The card materially reports measured comparative or absolute performance. The
presence of a number alone is insufficient.

#### `engineering-analysis`

The article materially explains architecture, implementation, performance work,
operational lessons, or design tradeoffs.

#### `tutorial`

The principal purpose is instructional and includes actionable steps or a walkthrough.

#### Operational events

`security-issue`, `incident`, `breaking-change`, `deprecation`, and `pricing-change`
retain their literal meanings and may coexist with a release event.

### Multiple-event policy

Multiple event types are allowed only when each type represents a material part of the
feed card. Source defaults must not be appended automatically when the card does not
represent that event.

Examples:

- PyTorch release with technical explanation:
  `library-release`, `engineering-analysis`
- Hosted feature with an API change:
  `product-release`, `api-change`
- Library patch fixing a vulnerability:
  `library-release`, `security-issue`
- One-line version bump:
  `library-release`

### Deliverables

1. Add the approved definitions to the controlled-taxonomy documentation.
2. Add concise definitions and contrastive examples to the summarization prompt.
3. Add an event-type policy version to generated taxonomy metadata.

### Completion criteria

- Every event type has a positive definition and at least one exclusion example.
- `product-release` is no longer used as a generic publication label.
- Multi-event assignments can be justified from the card's represented facts.

## Step 2: Fix Deterministic Event and Release-Candidate Contradictions

This step should be implemented only after Step 1 definitions are approved.

### Repository-release rules

Treat configured defaults as authoritative for versioned release feeds unless the
source explicitly represents an additional event:

| Source | Primary event default |
|---|---|
| vLLM | `library-release` |
| LangGraph | `library-release` |
| Qdrant | `library-release` |
| Transformers | `library-release` |
| LiteLLM | `library-release`, plus `api-change` when represented |
| PyTorch version release | `library-release` |

Ollama requires an explicit policy choice. The current configuration uses
`product-release`; treating its downloadable runtime as `library-release` is also
defensible. Keep the current default until that choice is made.

### Known corrections

- Seven Qdrant releases currently use `product-release`.
- One vLLM release currently uses `product-release`.
- One LangGraph release currently uses `product-release`.
- Three Transformers releases currently include `model-launch`.
- PyTorch 2.13 currently includes `model-launch` and lacks `library-release`.

### Release-candidate parsing

Recognize version forms including:

- `1.2.0rc1`
- `1.2.0-rc1`
- `1.2.0_rc1`
- `1.2.0-rc.1`
- Uppercase equivalents

The parser must be version-aware. It must not treat `rc` inside words such as
`research`, `architecture`, `source`, or `PyTorch` as a release-candidate marker.

Known affected vLLM titles include:

- `v0.23.1rc0`
- `v0.24.0rc1`
- `v0.24.0rc2`
- `v0.25.0rc1`
- `v0.25.0rc2`
- `v0.25.0rc3`

### Implementation sequence

1. Add unit tests for accepted RC forms and false-positive words.
2. Fix `infer_maturity`.
3. Add deterministic event normalization for configured versioned release feeds.
4. Run a read-only regression over every affected stored record.
5. Human-review corrections before database mutation.
6. Backfill only approved fields.

### Completion criteria

- All known RC titles return `release-candidate`.
- False-positive words remain unaffected.
- No framework version is labeled only as `product-release`.
- No library release is labeled `model-launch` merely because it supports models.
- Before-and-after values are saved with a change note.

## Step 3: Define Maturity as Artifact Lifecycle

### Decision gate

Approve what maturity describes:

> Recommended: maturity describes the principal announced artifact or capability, not
> the publication type.

### Recommended meanings

| Maturity | Meaning |
|---|---|
| `stable` | Usable release with no explicit pre-release status |
| `general-availability` | Explicitly announced as GA |
| `beta` | Explicit beta lifecycle |
| `preview` | Explicit preview or early-access lifecycle |
| `release-candidate` | Versioned RC build |
| `development` | Alpha, experimental, prototype, or active-development artifact |
| `research` | Proposed or demonstrated research artifact not presented as production-ready |
| `deprecated` | Marked for retirement or already deprecated |

### Important distinctions

- A research paper evaluating a deployed stable product may still describe a stable
  artifact.
- A blog post from an engineering source may announce a beta or preview capability.
- A research result with no deployable artifact should normally be `research`.
- Publication source type must not directly force maturity.

### Implementation sequence

1. Add maturity definitions and examples to the prompt.
2. Extend deterministic inference for explicit lifecycle language.
3. Decide how research-only records are detected.
4. Create a stratified maturity sample containing every non-stable class plus stable
   controls.
5. Compare deterministic inference, model suggestions, and human labels.
6. Backfill only after agreement.

### Completion criteria

- `stable` is not used merely because no classification effort occurred.
- Explicit GA, beta, preview, RC, development, research, and deprecated language maps
  consistently.
- Human-reviewed maturity accuracy meets the agreed threshold.

## Step 4: Revisit Primary Topics

Primary topics are deferred until event and maturity semantics are stable because they
contain the most subjective decisions.

### Decision gate

Approve the role of source defaults:

> Recommended: source defaults are strong priors for narrow sources and weak priors
> for broad editorial or engineering publications.

### Narrow-source policy

Examples:

- vLLM → `inference-serving`
- LangGraph → `agents-orchestration`
- Qdrant → `retrieval-data`
- GitHub Changelog → `developer-tools`

Override only when the individual record clearly belongs elsewhere.

### Broad-source policy

The individual article should drive classification for:

- The Batch
- Import AI
- Hugging Face Blog
- AWS Machine Learning Blog
- Google Developers
- NVIDIA Technical Blog
- PyTorch Blog
- OpenAI, Anthropic, and DeepMind news or research posts

### Borderline cases to calibrate

- Retrieval research:
  `retrieval-data` versus `evaluation-observability`
- Production agent architecture:
  `agents-orchestration` versus `infrastructure-hardware`
- Model-serving framework changes:
  `inference-serving` versus `models-apis`
- Training framework releases:
  `training-fine-tuning` versus `developer-tools`
- End-user AI programs:
  `models-apis` versus a possible future application/adoption topic

### Implementation sequence

1. Write inclusion and exclusion guidance for all nine primary topics.
2. Build a human-labeled calibration set emphasizing borderline pairs.
3. Measure agreement between configured defaults, deterministic keyword inference,
   model assignment, and human labels.
4. Adjust prompts or defaults only where the calibration supports a change.
5. Run a collection-wide read-only preview.
6. Backfill approved topic corrections.

### Completion criteria

- Every primary topic has explicit boundaries against its nearest alternatives.
- Narrow-source defaults remain stable unless direct evidence supports an override.
- Broad publications demonstrate meaningful content-based topic diversity.
- Borderline cases have documented adjudication rules.

## Step 5: Regression, Backfill, and Sign-Off

### Required artifacts

1. Preserve the current taxonomy baseline.
2. Save an event-type regression report.
3. Save a maturity regression report.
4. Save a primary-topic calibration report.
5. Give every human-review artifact a `change_history` entry.
6. Record prompt version, policy version, and deterministic-rule version.

### Safe backfill sequence

1. Dry-run and report proposed changes by field and source.
2. Inspect unexpected high-volume changes.
3. Apply approved deterministic corrections.
4. Regenerate model-derived taxonomy only for the targeted set first.
5. Human-review the targeted set.
6. Expand to the full collection only after regression approval.

### Final completion criteria

- No known deterministic contradictions remain.
- Event, maturity, and primary-topic policies are documented separately.
- Human review validates all changed rule families.
- Search and dashboard filters remain backward compatible.
- Before-and-after distributions and per-source changes are saved.
- No full-database mutation occurs without a reviewed dry-run.

## Recommended Decision Order

1. Approve event-type definitions.
2. Decide whether Ollama is a `product-release` or `library-release` source.
3. Implement deterministic repository-release and RC fixes.
4. Approve artifact-lifecycle maturity semantics.
5. Calibrate maturity.
6. Approve source-prior behavior for primary topics.
7. Calibrate primary topics.
8. Run reviewed backfills and save final regression reports.
