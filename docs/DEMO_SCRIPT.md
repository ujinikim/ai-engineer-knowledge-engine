# Demo Script

## Positioning

> Developer Update Radar is a time-aware multi-source RAG system. A scheduled collector stores official release evidence in PostgreSQL, the dashboard exposes ranked time windows, and the LLM analyzes only evidence retrieved from the selected period.

## Demo Flow

1. Show the seventeen quality-tiered sources and latest collection status.
2. Switch between 24-hour, 7-day, and 30-day windows.
3. Filter by tool and category.
4. Open an original release citation.
5. Ask what changed during the selected period.
6. Inspect cited sources, all retrieved chunks, ranking scores, latency, and cost.
7. Explain how publication filtering prevents old but semantically similar content from answering a current question.

## Demo Questions

```text
What are the most significant updates in this period?
Which releases changed model serving or inference behavior?
What updates mention tool calling, MCP, or structured output?
Compare recent changes across the selected tools.
```

## Interview Topics

- Collection freshness versus query-time browsing
- URL/hash deduplication and idempotent embedding
- Time filters before vector retrieval
- Recency-aware hybrid ranking
- Deterministic feed ranking versus LLM synthesis
- Citation correctness and retrieval observability
- Why story clustering is the next requirement before broad news ingestion
