# Evaluation

## Update Dashboard Checks

- Every displayed item has a publication time and canonical URL.
- Window queries exclude out-of-range releases.
- Tool, category, and source facets match stored metadata.
- Recollection does not duplicate unchanged entries.
- Ranking is deterministic for the same database snapshot.

## Retrieval Checks

- Retrieved chunks fall inside the requested publication range.
- Retrieved tools and categories respect active filters.
- Exact release terms are recoverable through keyword or hybrid search.
- Recent evidence receives a visible recency score.
- Several results do not merely repeat chunks from one release when alternatives exist.

## Answer Checks

- Factual claims cite retrieved evidence.
- Returned citations are actually referenced in the answer.
- Unknown citation IDs produce warnings.
- The answer identifies insufficient evidence rather than using ungrounded model knowledge.
- Statements about recency are supported by publication dates in context.

## Next Evaluation Work

Create a dated update question set after the first stable source snapshot. Store expected tools, categories, date ranges, release titles, and facts. Run deterministic retrieval checks first, then manually grade groundedness and completeness before adding an LLM judge.
