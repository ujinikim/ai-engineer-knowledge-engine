# Phase 2 Remediation Backlog

This backlog translates the regenerated 194-document summary baseline and completed
ten-item human review into actionable work. Items are ordered by impact and dependency.

## P0: Fix Before the Prompt Regression Run

### 1. Suppress speculative benefits for sparse sources

**Implementation status (July 24, 2026):** completed through saved regression and
human review; database summaries have not yet been regenerated, so the completed
ten-item human-review sample remains the before-change baseline.

**Finding:** Ollama, LangGraph, vLLM, and Qdrant release notes contain only a title or
one concrete change. Their summaries add unsupported claims about reliability,
stability, user experience, consistency, or workflow improvement.

**Fix:**

- Add an explicit prompt rule: do not infer benefits that the source does not state.
- When source detail is insufficient, make `why_it_matters` describe only the named
  compatibility or implementation impact.
- Allow a neutral value such as "The source does not provide enough detail to assess
  broader impact."
- Add sparse-source examples to the summarization prompt regression tests.

**Acceptance criteria:**

- Ollama, LangGraph, vLLM, and Qdrant summaries contain no unsupported benefit claims.
- Human faithfulness ratings improve from `minor_issue` to `faithful`.

**Read-only prompt preview:**

- A deterministic detail signal classifies sources with fewer than 50 body words or
  fewer than two substantive sentences as `sparse`.
- The first preview removed generic reliability, stability, and workflow claims but
  still produced unstated recommendations or guarantees such as "should update" and
  "will no longer experience."
- The revised prompt now also prohibits recommendations and guaranteed outcomes unless
  the source states them.
- A second preview produced neutral scope statements for all four regression cases:
  Ollama agent UI, LangGraph delta-channel state, vLLM DP Supervisor, and Qdrant
  shard-key resharding.
- Focused tests cover sparse classification, sparse prompt instructions, configured
  taxonomy priors, and preservation of normal behavior for detailed sources.
- The saved `sparse_prompt_regression.json` compares stored and revised outputs. All
  four revised summaries received `faithful` and `complete` human ratings. They remain
  `not_useful` because source detail is insufficient, confirming that prompt
  faithfulness and feed inclusion are separate concerns.

### 2. Detect and handle low-detail patch notes

**Finding:** Four of ten reviewed cards were not useful because the source contained
too little information for a standalone feed card.

**Implementation status (July 25, 2026):** completed in collection metadata, dashboard
filtering, API behavior, backfill tooling, and tests.

**Agreed product policy (July 25, 2026):**

- Retain sparse documents in storage, embeddings, search, RAG, citations, and source-
  or tool-specific timelines.
- Exclude sparse documents from the default dashboard feed.
- Include sparse documents when the user explicitly filters by source or tool, requests
  them directly, or opts into sparse updates.
- Always include sparse records for `security-issue`, `breaking-change`, `deprecation`,
  and `incident` events.
- Do not use `low_lexical_grounding` as a product-visibility rule. It remains an
  internal summary-review signal because faithful paraphrases and short sources can
  still fall below the overlap threshold.
- Consider grouping retained sparse records into a compact "Minor releases" section
  in a later UI phase instead of rendering each as a full feed card.

**Fix:**

- Introduce a source-detail score using cleaned text length and substantive sentence
  count.
- Mark low-detail records explicitly with metadata such as `content_detail = sparse`,
  `default_feed_eligible = false`, and
  `default_feed_exclusion_reason = low_source_detail`.
- Exclude low-detail patch notes from the default feed while retaining them for search,
  RAG, citations, explicit inclusion, and source- or tool-specific filters.
- Add an `include_sparse` API option for callers that intentionally want the full
  release stream.
- Add important-event overrides for security issues, breaking changes, deprecations,
  and incidents.
- Do not exclude GitHub-originated content wholesale; detailed changelogs such as the
  GitHub AI credit-pool update remain useful.

**Acceptance criteria:**

- Sparse patch notes do not dominate the default feed.
- Detailed and actionable GitHub changelogs remain eligible for normal ranking.
- Users can retrieve sparse patch notes through search, direct lookup, `include_sparse`,
  and relevant source or tool filters.
- Sparse security, breaking-change, deprecation, and incident records remain visible
  in the default feed.
- `low_lexical_grounding` never controls feed visibility.

**Verification:**

- Backfilled all 194 stored release documents without changing summaries, chunks, or
  embeddings.
- Classified 166 records as detailed and 28 as sparse.
- Suppressed 27 sparse records from the default feed.
- Retained one sparse OpenAI/Hugging Face security-incident record through the
  important-event override.
- Verified 167 default-feed records versus all 194 records with
  `include_sparse=true`.

### 3. Correct taxonomy assignment

**Implementation status (July 27, 2026):** completed. The controlled vocabulary was
kept stable, the 43-item/129-axis regression passed, reviewed corrections were
backfilled, and the refreshed ten-item summary sample is 10/10 `correct` after two
follow-up decisions.

**Finding:** Five of ten sampled cards received `partial` taxonomy ratings after a
second review against the controlled definitions and configured source defaults.

The detailed decision gates, implementation order, regression requirements, and
backfill safeguards are maintained in `TAXONOMY_REMEDIATION_PLAN.md`. Taxonomy work
must follow that plan rather than applying the example corrections below ad hoc.

**Known corrections:**

| Item | Current | Better assignment |
|---|---|---|
| Web Retrieval Flusters LLMs | `developer-tools` | `retrieval-data` primary; `evaluation-observability` is a reasonable secondary topic |
| Web Retrieval Flusters LLMs | `stable` | `research` |
| monday.com AI Teammates | `engineering-analysis`, `product-release` | Keep `engineering-analysis`; remove `product-release` unless a launch is explicitly identified |
| vLLM rc2 | `stable`, `product-release` | `release-candidate`, `library-release` |
| Qdrant patch | `product-release` | `library-release` |
| PyTorch 2.13 | `model-launch`, `product-release` | `library-release`; add other event types only for changes represented in the card |

**Assignments retained after review:**

- monday.com may remain `infrastructure-hardware`: the article is substantially about
  AWS deployment architecture. `agents-orchestration` is a strong secondary topic,
  not an objectively superior primary topic.
- ChatGPT for Small Businesses may remain `models-apis`: the controlled taxonomy has
  no end-user application or AI-adoption topic, and `developer-tools` would imply a
  developer-specific product.
- Ollama may remain `inference-serving` plus `product-release`: those values match the
  configured source policy, and the sparse release text does not provide enough
  evidence to override them.

**Fix:**

- Add clearer topic and event-type definitions to the summarization prompt.
- Add examples distinguishing models, products, libraries, research, and engineering
  analysis.
- Treat configured source defaults as strong priors. Override them only when the
  individual article provides clear evidence, and record the reason for the override.
- Evaluate primary topic, event types, and maturity separately in future human samples
  so one ambiguous axis does not make the entire taxonomy judgment opaque.
- Validate maturity independently of model output.
- Add regression fixtures for the known corrections above.

**Acceptance criteria:**

- At least 8 of 10 equivalent regression cases receive `correct` taxonomy ratings,
  with ambiguous primary-topic choices judged against documented source policy.
- No library/framework version is labeled `model-launch`.
- Release candidates are not stored as `stable`.

### 4. Fix release-candidate maturity parsing

**Implementation status (July 26, 2026):** completed in deterministic maturity
inference, collector normalization, backfill policy, and unit tests.

**Finding:** `v0.24.0rc2` was classified as `stable`. The current regular expression
does not recognize `rc` when it directly follows a version number.

**Fix:**

- Recognize forms such as `1.2.0rc1`, `1.2.0-rc1`, `1.2.0_rc1`, and `RC2`.
- Add unit tests for each supported form.

**Acceptance criteria:**

- All supported RC formats return `release-candidate`.
- Stable versions containing unrelated `rc` text do not produce false positives.

## P1: Improve Evaluator Precision

### 5. Normalize equivalent percentage formats

**Implementation status (July 27, 2026):** completed. Percent words/symbols and
numeric trailing-zero equivalents are normalized. Semantic conversions, rounding,
and number words intentionally remain review candidates.

**Finding:** Supported claims produced `unsupported_number` warnings:

- `90%` versus `90 percent`
- `50%` versus `more than half`

**Fix:**

- Normalize `N percent` and `N%` to the same representation.
- Keep semantic conversions such as `half` to `50%` as review candidates unless the
  evaluator records them separately as derived equivalents.
- Distinguish exact-format mismatches from genuinely absent numbers.

**Acceptance criteria:**

- `90%` versus `90 percent` does not warn.
- A genuinely absent percentage still produces `unsupported_number`.
- Derived expressions such as `half` remain visible without being treated as proven
  fabrication.

### 6. Make lexical-grounding warnings source-length aware

**Implementation status (July 27, 2026):** completed as a calibrated triage signal.
Evaluation now records source detail, normalizes basic word forms and punctuation,
uses separate detailed/sparse thresholds, and never controls product visibility.

**Finding:** Exact token overlap correctly exposed speculation in sparse releases, but
it also penalized valid paraphrases and morphological variants.

**Fix:**

- Preserve lexical grounding as a review heuristic.
- Report the source-detail score alongside lexical overlap.
- Normalize basic word forms such as `release`/`released` and `improve`/`improves`.
- Consider separate thresholds for short release notes and long articles.
- Do not replace the check with uncalibrated semantic similarity.

**Acceptance criteria:**

- Sparse speculative summaries remain warnings.
- Faithful paraphrases produce fewer false positives.
- Before-and-after warning counts are saved in the regression report.

### 7. Treat preview-only source content explicitly

**Implementation status (July 27, 2026):** completed for collection provenance,
prompt behavior, evaluation, and sparse visibility. Existing preview-derived cards
remain auditable; new generation is constrained by available source detail.

**Finding:** The ChatGPT for Small Businesses card was generated from a one-sentence
preview. Its core facts were supported, but its impact statement became promotional
and generic.

**Fix:**

- Prevent preview-only records from making impact claims beyond the preview.
- Ensure hydration status is carried into prompt behavior and evaluation.
- Continue excluding known-incomplete previews from normal human calibration unless
  they are intentionally sampled as a limitation case.

**Acceptance criteria:**

- Preview summaries remain strictly bounded to available facts.
- Preview records are visibly labeled and do not silently look like full articles.

## P2: Product and Process Improvements

### 8. Separate summary usefulness from personal relevance

**Implementation status (July 27, 2026):** completed in the review definitions and
the separate feed-relevance policy. Usefulness measures open/skip value; relevance
controls routing.

**Finding:** A technically accurate card may be useful even when it applies to a narrow
audience. The earlier GHES review mixed audience relevance with card quality.

**Fix:**

- Keep human `usefulness` focused on whether the card supports an open/skip decision.
- Handle personal relevance through followed tools, topics, filters, and ranking.
- Document this distinction in the human-review runbook.

**Acceptance criteria:**

- Reviewers apply usefulness consistently regardless of personal tool preferences.
- Narrow but actionable updates can still receive `useful`.

### 9. Preserve multi-story document boundaries

**Implementation status (July 25, 2026):** completed for The Batch and Import AI,
with deterministic splitting, parent provenance, and regression tests.

**Finding:** The old sample exposed whole-catalog The Batch and whole-newsletter Import
AI records. The refreshed sample confirms that the Phase 1 split corrections removed
those cases.

**Fix:**

- Retain the current The Batch and Import AI splitting behavior.
- Add a regression test ensuring a feed catalog or newsletter does not reappear as one
  multi-topic document.
- Monitor boundary quality in future collection baselines.

**Acceptance criteria:**

- Each sampled The Batch record represents one story.
- Each sampled Import AI record represents one deterministic section.

### 10. Tighten headline compliance

**Implementation status (July 27, 2026):** completed. Model and fallback headlines
are shortened on word boundaries to at most 90 characters, and three stored
headlines were backfilled.

**Finding:** The PyTorch 2.13 headline was clear but measured 91 characters against a
90-character target.

**Fix:**

- Enforce the configured headline limit during validation instead of relying only on
  the prompt.
- Prefer a word-boundary shortening strategy.

**Acceptance criteria:**

- Generated headlines never exceed 90 characters.
- Shortening does not remove the release name or principal change.

## Regression Deliverables

**Closeout status (July 27, 2026):** complete for the MVP. The preserved
194-document baseline, sparse prompt regression, taxonomy regression, 240-document
post-remediation report, completed human sample, and dated backfill reports provide
the before/after evidence. Full forced LLM regeneration is intentionally skipped
because the affected legacy summaries are sparse/preview records already handled by
visibility policy.

After implementing P0 and P1:

1. Preserve the current 194-document report as the before-fix baseline.
2. Regenerate summaries for a targeted sample before a full forced run.
3. Rerun the automated evaluator.
4. Human-review the known regression fixtures.
5. Save before-and-after counts by warning type, source type, and taxonomy failure.
6. Confirm that improvements do not regress the four already-faithful summaries.
