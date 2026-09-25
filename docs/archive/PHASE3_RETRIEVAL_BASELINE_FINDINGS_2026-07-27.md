# Phase 3 Retrieval Baseline Findings — July 27, 2026

## Scope

The first Phase 3 checkpoint is complete:

- Frozen update snapshot: 240 documents and 1,134 original-text chunks
- Corpus hash: `d12684ca90a0651eb3d80638d12b17df745ac780b9c3fefac5b86737db5eda73`
- Question set: 30 cases
- Split: 20 calibration and 10 holdout
- Ground truth: exact relevant document IDs plus source and required-text diagnostics
- Search matrix: vector/standard, keyword/standard, hybrid/standard, and
  hybrid/source-balanced

The three insufficient-evidence cases have no relevant document IDs. They are included
in filter and result-availability metrics but excluded from relevance averages. Final
abstention behavior will be graded during answer evaluation.

## Question Distribution

| Intent | Cases |
|---|---:|
| Exact lookup | 8 |
| Temporal | 5 |
| Comparison | 5 |
| Filter | 5 |
| Synthesis | 4 |
| Insufficient evidence | 3 |

## Untouched Baseline

| Configuration | Recall@K | MRR | All relevant docs | Required sources | Filter correctness | Required text | Total ms |
|---|---:|---:|---:|---:|---:|---:|---:|
| Vector / standard | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.858 | 368 |
| Keyword / standard | 0.765 | 0.747 | 0.704 | 0.815 | 1.000 | 0.833 | 421 |
| Hybrid / standard | 0.895 | 0.875 | 0.852 | 1.000 | 1.000 | 0.957 | 762 |
| Hybrid / source-balanced | 0.889 | 0.889 | 0.889 | 1.000 | 1.000 | 0.938 | 937 |

## Finding 1: Vector Search Had the Best Document Recall

Pure vector retrieval found every judged relevant document and ranked a relevant
document first for every answerable case.

This does not mean vector-only is automatically the best answer configuration.
Required-text coverage was lower than hybrid because the top chunks from the correct
document did not always contain every fact needed by the question.

Decision:

- Keep vector/standard as the document-recall reference.
- Keep hybrid as the product default only if its exact-document regression is fixed
  without losing its stronger lexical/fact coverage.

## Finding 2: The Original Hybrid Lexical Score Penalized Sparse Exact Releases

The calibration miss was `lookup_vllm_dp_supervisor`.

The exact `v0.24.0rc2` release had the strongest vector similarity, but long stable
release pages repeated more generic query words and received larger normalized keyword
scores. Recency then pushed the older sparse release farther down.

Implemented measured correction:

- Remove generic question/update terms such as `changed`, `release`, `published`, and
  `update` from lexical terms.
- Normalize `fixed`/`fixes`/`fixing` to `fix`.
- Score distinctive title matches separately from body matches.

The correction is general; it does not encode benchmark titles or document IDs.

## Tuned Hybrid Result

| Set | Recall@K | MRR | All relevant docs | Required sources | Filter correctness | Required text |
|---|---:|---:|---:|---:|---:|---:|
| Calibration, before | 0.926 | 0.944 | 0.889 | 1.000 | 1.000 | 0.963 |
| Calibration, after | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 0.907 |
| Holdout, after | 0.944 | 0.861 | 0.889 | 1.000 | 1.000 | 0.889 |
| Full set, after | 0.982 | 0.954 | 0.963 | 1.000 | 1.000 | 0.901 |

The exact-lookup rerun at a fixed `K=5` achieved:

- Recall@5: 1.000
- MRR: 0.938
- All relevant documents hit: 1.000

The initial Phase 3 exact-lookup and holdout targets are satisfied.

## Finding 3: Source-Level Success Can Hide a Wrong Document

The remaining holdout document miss is `compare_agent_security_research`.

Hybrid retrieval found the required DeepMind and Hugging Face source names, so the
source-coverage metric passed. It retrieved a different DeepMind agent-safety article
instead of the judged `Securing the future of AI agents` document.

This validates the move from source-name evaluation to exact document judgments.

Decision:

- Do not tune on this single holdout miss.
- Carry it into the answer review. If the alternate evidence answers the question
  well, expand graded relevance rather than forcing one document.
- If it does not answer the question, retain it as a comparison-retrieval failure for
  later targeted work.

### Post-holdout separator-normalization diagnostic — July 28, 2026

Content review confirmed that `Investing in multi-agent AI safety research` is useful
supplementary evidence but is not a replacement for the judged `Securing the future
of AI agents` document. The latter contains the AI Control Roadmap, insider-threat
model, monitoring, detection, prevention, and response evidence required by the
intended comparison.

The review also exposed a general lexical-normalization defect: the query token
`agent-security` did not match the article phrase `agent security`. Retrieval now
canonicalizes hyphens, underscores, and slashes to spaces in the query, title, and
chunk text before tokenization and lexical scoring. No document ID, title, source, or
benchmark-specific synonym was added to the ranking code.

The original holdout result above remains unchanged. A separately labeled diagnostic
reran the two holdout comparison cases after the correction:

- Comparison Recall@K: 1.000
- All relevant documents hit: 1.000
- Required-source coverage: 1.000
- Required-text coverage: 1.000
- `compare_agent_security_research`: Recall@K improved from 0.500 to 1.000
- The judged DeepMind document appeared at chunk rank 8; the first relevant document
  appeared at rank 2 because MosaicLeaks was already relevant.

Artifact:
`backend/data/eval/retrieval/updates_post_holdout_separator_normalized_hybrid_standard.json`

Interpretation:

- Treat the change as a product regression fix and post-holdout diagnostic, not as an
  untouched holdout result.
- Keep the alternate DeepMind article as partially relevant supplementary evidence.
- Use a more explicit AI Control Roadmap wording in the next versioned benchmark.

## Finding 4: Correct Documents Do Not Guarantee Complete Answer Context

Three questions exposed incomplete required-text coverage despite retrieving the
correct document:

- TensorRT progress/cancellation
- The Batch web-retrieval research
- monday.com production-agent architecture

The retriever limits repeated chunks from one document to two. For long synthesis
articles, those two chunks may identify the correct document but omit a later API,
measurement, or architecture section.

Decision:

- Do not increase global top-k or remove diversification yet.
- During answer evaluation, inspect which facts are actually missing from model
  context.
- Consider query-aware within-document expansion only if the answer sample confirms
  material omissions.

First answer-review result — July 28, 2026:

- `compare_agent_security_research` retrieved both judged documents after separator
  normalization, but the intended DeepMind AI Control Roadmap chunk was ranked eighth.
- The greedy 3,500-token context builder filled the prompt with earlier long chunks
  and did not supply the judged DeepMind chunk to the answer model.
- The generated answer was factually grounded in its supplied context and all
  citation IDs were valid, but required-fact coverage failed because it compared
  MosaicLeaks with the partially relevant multi-agent safety funding article.
- This confirms an answer-context selection failure rather than a hallucination or an
  exact-document retrieval failure.
- Review artifact:
  `backend/data/eval/retrieval/updates_answer_review_sample.json`

### General retrieval and answer remediation — July 29, 2026

The saved results and targeted answer runs identified four general defects:

1. Title-only placeholder chunks could consume both per-document result slots.
2. Comparison context was packed greedily, allowing repeated documents to exhaust the
   prompt before later judged evidence.
3. The answer prompt allowed a related metric or model memory to fill an unsupported
   exact-number request.
4. The frontend requested 350 completion tokens while the backend silently capped
   generation at 300, allowing detailed answers to end mid-sentence.

Implemented corrections:

- Skip title-only chunks during final retrieval selection when substantive candidates
  from the same document are available. Keep them when a sparse document has no
  substantive candidate.
- For comparisons, pack the first chunk from distinct normalized document URLs before
  repeated chunks. Exact lookups retain rank order so they can use multiple chunks
  from one article.
- Continue trying later, smaller chunks when an earlier candidate does not fit the
  remaining context budget.
- Return `context_chunks` separately from `retrieved_chunks`, so citation numbering
  and the actual model prompt are inspectable in the API and UI.
- Require the answer model to use only supplied context, avoid substituting related
  metrics, abstain when an exact number is absent, and keep ordinary answers concise.
- Raise the backend completion ceiling to 500 tokens and expose a generation warning
  when the model still stops for length.
- Normalize trailing slashes during future collection and match both URL variants to
  prevent `/article` and `/article/` from creating new duplicates.

Post-remediation 30-question retrieval result:

| Metric | Prior tuned hybrid | July 29 context-ready hybrid |
|---|---:|---:|
| Recall@K | 0.982 | 1.000 |
| MRR | 0.954 | 0.982 |
| All relevant documents hit | 0.963 | 1.000 |
| Required sources | 1.000 | 1.000 |
| Filter correctness | 1.000 | 1.000 |
| Required text | 0.901 | 0.988 |

Artifact:
`backend/data/eval/retrieval/updates_tuned_hybrid_standard_context_ready_2026-07-29.json`

Targeted answer outcomes:

- Agent-security comparison: changed from incomplete to a grounded, cited comparison
  containing the AI Control Roadmap and MosaicLeaks.
- All three insufficient-evidence cases abstained or qualified correctly after prompt
  hardening. The original unsupported Presence answer remains recorded in the human
  review artifact.
- TensorRT coverage improved from 0.000 to 1.000 and produced a complete cited answer
  containing `IProgressMonitor` and `step_complete`.
- The Batch coverage improved from 0.000 to 1.000 and produced a cited research
  explanation.
- monday.com coverage improved from 0.333 to 0.667. The answer is now materially
  useful, but the selected chunks still omit `SQS`; retain this as a within-document
  depth diagnostic instead of tuning global weights to one calibration question.

Existing duplicate rows were not deleted or merged. Context packing now treats
trailing-slash variants as one document identity, and future collection will reuse
either stored URL form. A separate reviewed data migration is required if historical
duplicate records are to be consolidated.

## Finding 5: Source-Balanced Retrieval Is Not a Better Global Default

Source-balanced hybrid retrieval was slower and had slightly lower recall than
standard hybrid in this benchmark. When no sources are specified, it searches across
every available source, which adds work and can introduce lower-ranked material.

Decision:

- Keep standard hybrid as the product default.
- Reserve source-balanced retrieval for explicit comparisons or cases with a defined
  source set.
- Do not enable it globally.

## Finding 6: Keyword Search Is Not the Fast Path

The current keyword implementation scans filtered chunks in Python. It was slower than
the pgvector database query while producing lower recall.

Decision:

- Retain keyword mode as a diagnostic and hybrid signal.
- Do not market it as a low-latency alternative.
- Consider PostgreSQL full-text search only if hosted measurements or corpus growth
  show the Python scan becoming material.

## Legacy Documentation Smoke Test

The legacy 15-question runner previously allowed `collection=all`, so update articles
could leak into documentation questions. It now defaults explicitly to `docs`.

Corrected smoke result:

- Source hit rate: 100%
- All expected sources hit rate: 93%
- Top-3 source hit rate: 100%
- Title-hint hit rate: 100%
- Average keyword coverage: 96%
- One remaining partial comparison: LangGraph versus OpenAI streaming

## Next Phase 3 Work

1. Review the alternate evidence for the agent-security holdout case.
2. Run the full answer path on 12 selected cases.
3. Human-grade groundedness, required-fact coverage, comparison balance, citations,
   and insufficient-evidence behavior.
4. Decide whether query-aware within-document expansion is justified.
5. Save the answer-review artifact and Phase 3 closeout result.
