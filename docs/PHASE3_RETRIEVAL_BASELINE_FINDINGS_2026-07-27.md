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
