# Summary Evaluation Runbook

Phase 2 measures whether stored article summaries are grounded, useful, and categorized correctly. The evaluator is read-only: it does not call an LLM, regenerate summaries, or update the database.

## Run the Evaluation

From `backend`:

```bash
uv run python scripts/evaluate_summaries.py
```

Every evaluation that replaces a human-review artifact should describe what changed:

```bash
uv run python scripts/evaluate_summaries.py \
  --change-note "Regenerated after sparse-source prompt revision; summaries are otherwise unchanged."
```

Optional filters:

```bash
uv run python scripts/evaluate_summaries.py --source github-changelog
uv run python scripts/evaluate_summaries.py --status warning --sample-size 10
```

The command writes:

- `data/eval/summaries/summary_report.json`: every evaluated document, automated findings, and aggregate counts
- `data/eval/summaries/human_review_sample.json`: a stratified sample for manual calibration

Existing human ratings are preserved when the source text and generated summary have not changed.
The human-review artifact also preserves a top-level `change_history` containing the
timestamp, change note, document count, sample size, and filters for every generation.
Use a specific `--change-note`; the default note records that no description was supplied
so undocumented regenerations remain visible.

## Automated Checks

The report checks:

- Required summary and taxonomy fields
- Headline, summary, rationale, and key-point length limits
- Key-point count
- Primary topic, event type, and maturity values against the configured taxonomy
- Numbers in generated text that do not appear in the source
- Lexical overlap between generated claims and source text
- Deterministic fallback summaries
- Documents retained from incomplete source previews

These checks find candidates for review; they are not a semantic quality judgment.

- `unsupported_number` normalizes `N percent`/`N%` and numerically equivalent
  trailing-zero forms. Semantic conversions such as `half`/`50%`, number words,
  derived totals, and rounding remain review candidates.
- `low_lexical_grounding` detects summaries with little vocabulary overlap. It
  records `source_detail`, normalizes a small set of basic word forms, and applies a
  stricter threshold to sparse sources. It remains a triage signal, not a visibility
  rule or semantic judgment.
- `source_content_incomplete` means the collector retained a preview after full-page extraction failed. These records remain visible and link to the original article, but they are excluded from the normal human sample.

## Human Review

Open `data/eval/summaries/human_review_sample.json`. For every item, open `url` or
query the locally stored document, compare it with all fields under
`generated_summary`, then replace each `not_reviewed` value. Full source text is
deliberately excluded from tracked review artifacts so the repository remains safe
to publish.

### Faithfulness

- `faithful`: every material claim is supported by the source
- `minor_issue`: a small imprecision or weakly supported detail does not change the main meaning
- `major_issue`: a fabricated, contradicted, or materially misleading claim is present

### Coverage

- `complete`: captures the main update and its important supporting details
- `partial`: captures the main update but omits a meaningful detail
- `misses_main_point`: emphasizes a secondary detail or fails to represent the source

### Usefulness

- `useful`: gives a developer enough context to decide whether to open the source
- `somewhat_useful`: understandable but generic, repetitive, or missing practical significance
- `not_useful`: confusing, promotional, or too inaccurate to support a decision

### Headline Quality

- `good`: concise, specific, and representative
- `acceptable`: accurate but generic, awkward, or slightly too long
- `poor`: misleading, vague, promotional, or focused on the wrong detail

### Taxonomy Accuracy

- `correct`: primary topic, tags, event types, entities, and maturity fit the source
- `partial`: broadly useful classification with one meaningful omission or incorrect label
- `incorrect`: primary classification or several labels misrepresent the source

Add a concise explanation to `human_notes`, especially for any rating below the strongest option. Cite the unsupported phrase or missing subject rather than only saying that it “looks wrong.”

## Initial Baseline

The July 24, 2026 baseline evaluated 187 stored summaries:

- 144 pass
- 43 warning
- 0 fail
- Average lexical grounding: 0.5729
- 28 low-lexical-grounding warnings
- 9 incomplete-source warnings
- 8 unsupported-number warnings
- 1 headline-length warning

The ten-item review sample is stratified across source types, summary generators, and sources. It intentionally includes warnings and clean cases. OpenAI News preview-only records are excluded because their source content is known to be incomplete.

## July 27 Closeout Baseline

The post-remediation baseline evaluates 240 stored summaries:

- 196 pass
- 44 warning
- 0 fail
- Average lexical grounding: 0.6329
- 29 low-lexical-grounding warnings
- 19 known incomplete-source warnings
- 4 unsupported-number review candidates
- 0 headline-length warnings after a three-record backfill

Twenty-eight of the 29 low-grounding warnings are sparse records; the remaining item
is a narrow LangGraph CLI release. The four numeric candidates are deliberate review
cases involving a word-to-number conversion, a derived percentage, or rounding—not
confirmed fabrication.

The refreshed ten-item sample has no `not_reviewed` fields. All ten taxonomy ratings
are `correct` after applying two follow-up decisions:

- Cloudflare crawler controls: `retrieval-data` primary topic
- monday.com production-agent architecture: `engineering-analysis` without
  `product-release`

The remaining `minor_issue` faithfulness ratings belong to already-stored sparse or
preview-derived summaries. The revised prompt prevents the identified speculative
benefits for newly generated summaries, and sparse visibility keeps low-detail cards
out of the default feed. A forced full-corpus LLM regeneration is not required for
Phase 2 closure.

## Completion Criteria

Phase 2 is complete when:

1. The review sample has no `not_reviewed` ratings.
2. Human findings are summarized by source type and failure mode.
3. Any prompt or fallback changes have a before-and-after regression report.
4. If an optional LLM judge is introduced, it is tested against human labels before
   its scores are trusted.

Phase 2 satisfies these criteria as of July 27, 2026. The optional LLM judge remains
deferred.
