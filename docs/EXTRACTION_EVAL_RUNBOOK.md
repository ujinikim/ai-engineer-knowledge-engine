# Extraction Evaluation Runbook

Phase 1 evaluates stored update documents without changing PostgreSQL or ingestion behavior.

## Run The Evaluation

```bash
cd backend
uv run python scripts/evaluate_extraction.py
```

Outputs:

```text
data/eval/extraction/extraction_report.json
data/eval/extraction/human_review_sample.json
```

Useful filters:

```bash
uv run python scripts/evaluate_extraction.py --source deepmind-blog
uv run python scripts/evaluate_extraction.py --status warning
uv run python scripts/evaluate_extraction.py --sample-size 30
```

Filtered runs write to the same paths by default. Use `--output-dir` to preserve a separate report.

## Automated Statuses

- `pass`: no configured integrity or quality warning
- `warning`: usable document with a signal requiring review
- `fail`: structural or integrity failure that can invalidate retrieval

The evaluator is report-only. Statuses do not hide, delete, summarize, or re-embed documents.

## Metrics

Integrity checks:

- Valid canonical HTTP or HTTPS URL
- Persisted document content hash
- Sequential, nonempty chunks
- Persisted chunk hashes
- Positive chunk token counts
- Complete chunk embeddings
- Chunk text traceable to original document text

Content signals:

- Character, word, line, paragraph, chunk, and token counts
- Title presence near the beginning of the extracted text
- Suspected short feed excerpt
- Suspected collection, tag, search, or pagination page stored as an article
- Full-article hydration failure
- Duplicate-line ratio
- Duplicate-line count
- Boilerplate-line ratio
- Publication-date confidence

Thresholds are included in every report so results remain interpretable after configuration changes.

## Human Review

The review sample selects at least one document per source when the sample size permits, then prioritizes warnings, failures, shortest documents, and longest documents.

For each item, open `url`, compare it with the locally stored extracted document, and
set `human_label` to one of:

```text
complete
mostly_complete
incomplete
too_much_boilerplate
wrong_content
```

Use `human_notes` for missing sections, navigation text, date problems, or source-specific observations. Prefix observations with `Extraction`, `Relevance`, `Warning assessment`, or `Follow-up` when applicable. Rerunning the evaluator preserves labels for documents that remain in the sample.

Full extracted text is deliberately excluded from tracked review artifacts. This
keeps the repository publishable without changing the locally stored document used
by the evaluator.

## Interpreting Findings

- A hash or embedding failure is a pipeline integrity problem.
- `suspected_excerpt` means the length is unusual for that source type; short release notes can still be valid.
- `suspected_collection_page` means an HTML source stored a catalog-style URL rather than a content unit.
- GitHub release notes are exempt from article-length warnings because the original release can legitimately contain one line.
- `article_hydration_failed` means the collector retained the feed preview after a full-page request failed validation.
- `published_at_matches_collection_time` often means the source did not expose a usable publication date.
- Boilerplate and duplicate ratios are triage signals, not proof of a bad extraction.

Review real examples before changing thresholds or enabling ingestion quality gates.

## Initial Baseline

This is the pre-remediation baseline and remains useful for comparison with the next collection.

Validated July 22, 2026 against 91 update documents:

```text
Pass:    64
Warning: 27
Fail:     0

Suspected excerpts:                    15
High duplicate-line ratio:              8
Publication time matched collection:    4
```

Initial interpretation:

- No URL, content-hash, chunk, token-count, or embedding integrity failures were found.
- Hugging Face Blog and OpenAI News need human review for likely feed-only excerpts.
- Google Developers entries need publication-date review because the feed parser fell back to collection time.
- Short GitHub prereleases and patch notes may be valid even when the excerpt heuristic warns.
- Repeated GitHub changelog lines need human calibration before changing the duplicate threshold.

Human calibration reviewed 12 representative documents and found enough distinct failure modes to implement the first remediation pass. No ingestion gate should be enabled until a fresh collection is evaluated and the known regression cases pass.

## First Remediation Pass

- Google Developers uses `.blocks-container` for full article content.
- Hugging Face Blog uses `.blog-content` and removes non-article controls.
- NVIDIA Technical Blog uses `.entry-content`.
- OpenAI News attempts `article, main`; Cloudflare challenges are rejected and recorded as hydration failures rather than stored as article text.
- Hydrated pages use `time`, publication meta tags, or JSON-LD `datePublished` before feed dates.
- Missing dates are stored as unknown instead of being replaced with collection time.
- Non-release articles under 1,000 characters are flagged for review.
- Duplicate warnings require at least three repeated long prose lines as well as a high ratio; GitHub release feeds, code lines, identifiers, and URLs are excluded.

## Post-Remediation Baseline

Validated July 22, 2026 after a fresh 17-source collection:

```text
Documents: 187
Pass:      177
Warning:    10
Fail:        0

Suspected excerpts:           10
Article hydration failures:    9
```

All ten warnings are OpenAI News entries. Nine current entries record both a short feed preview and a blocked full-article hydration attempt. One older feed-preview document was outside the latest per-source collection window. All other sixteen sources pass the calibrated extraction checks.

The pre-remediation human labels and notes are preserved in:

```text
data/eval/extraction/human_review_baseline_2026-07-22.json
```

## Source-Boundary Remediation

On July 24, 2026, human summary review exposed three upstream problems that length and integrity checks did not detect:

- The Batch date-tag catalogs were stored as articles.
- Import AI newsletters were stored as one multi-story document.
- The short relevance term `ai` matched inside unrelated words such as `available`.

The remediation:

- Discovers recent The Batch issue pages, resolves their story headings to individual story URLs, and extracts each full story.
- Retains the corresponding issue section as a complete fallback when an individual story URL fails.
- Splits Import AI RSS entries at their explicit `***` boundaries and excludes the fictional `Tech Tales` section.
- Stores parent newsletter URLs as canonical evidence metadata for split stories.
- Uses token and phrase boundaries for include and exclude terms.
- Narrows Anthropic extraction to the nested article body, excluding related-content cards.
- Flags catalog-style URLs stored by HTML sources as `suspected_collection_page`.

Validated July 24, 2026 after targeted recollection:

```text
Documents: 194
Pass:      184
Warning:    10
Fail:        0
```

The Batch, Import AI, Anthropic, and GitHub Changelog have no extraction warnings. All ten remaining warnings are OpenAI News preview limitations.

The refreshed 20-document human sample was reviewed on July 24, 2026:

```text
Complete:   18
Incomplete:  2
```

Both incomplete items are OpenAI feed previews with recorded hydration failures and retained original links. The remediated source-boundary examples were complete, so Phase 1 is closed again with the OpenAI limitation documented.
