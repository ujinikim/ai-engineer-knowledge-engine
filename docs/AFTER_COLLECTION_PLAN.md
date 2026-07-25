# After Collection Plan

This document preserves the execution plan used for the original documentation RAG prototype. It is historical; the active update-dashboard plan is in `ROADMAP.md`.

The goal was to turn scraped pages into a searchable, inspectable RAG system without adding unnecessary complexity.

## Implementation Status

- Completed: raw collection, normalization, chunking, embeddings, pgvector storage, retrieval, cited answers, inspection UI, and automated retrieval evaluation
- Added beyond the original plan: hybrid search, source-balanced retrieval, similarity thresholds, token budgets, and latency profiling
- Next: streaming answer delivery and evaluation-driven quality improvements
- Superseded: the product has since pivoted to dated developer-tool releases while retaining documentation as a separate collection
- Still deferred: reranking, local models, code ingestion, broad news crawling, chat memory, and agents

## Phase 1: Raw Collection Review

Input:

- Curated docs URLs
- Raw fetched HTML or extracted text
- Basic source metadata

Tasks:

- Confirm each URL fetched successfully.
- Store `source_name`, `title`, `url`, `raw_text`, `content_hash`, and `fetched_at`.
- Remove failed, duplicate, or obviously low-value pages.
- Keep raw source content separate from processed chunks.

Done when:

- 20-50 documentation pages are collected.
- Each page has usable text and stable metadata.
- Collection can be re-run without creating uncontrolled duplicates.

## Phase 2: Text Normalization

Tasks:

- Strip navigation, footer, scripts, style blocks, cookie banners, and repeated boilerplate.
- Preserve headings, code blocks, and useful section text.
- Normalize whitespace.
- Compute a content hash after normalization.

Why this matters:

- Bad extraction creates bad chunks.
- Bad chunks produce noisy embeddings.
- Noisy embeddings make retrieval harder to debug.

Done when:

- Stored text is readable when inspected directly.
- Headings and code examples remain understandable.
- Repeated page chrome is mostly gone.

## Phase 3: Chunking

Start simple.

Initial chunk settings:

```text
chunk_size: 700-1000 tokens
chunk_overlap: 100-150 tokens
split_priority:
  1. headings
  2. paragraphs
  3. code block boundaries
  4. token limit fallback
```

Tasks:

- Create chunks linked to their source document.
- Store `chunk_index`, `content`, `token_count`, `content_hash`, and metadata.
- Include enough source context to support citations.

Done when:

- Each document produces stable chunks.
- Chunks are not too tiny or too broad.
- Chunk text can stand alone well enough for answer generation.

## Phase 4: Embeddings

Tasks:

- Generate embeddings for chunks.
- Store vectors in pgvector.
- Track embedding model name and dimensions.
- Avoid re-embedding unchanged chunks by checking content hashes.

Initial provider:

```text
OpenAI text-embedding-3-small
```

Done when:

- All chunks have embeddings.
- Re-running ingestion only embeds new or changed chunks.
- Embedding failures are logged clearly.

## Phase 5: Basic Retrieval

Build `POST /search`.

Request:

```json
{
  "query": "How does LangGraph memory work?",
  "top_k": 6
}
```

Response should include:

- Chunk ID
- Source name
- Document title
- URL
- Chunk text
- Similarity score
- Chunk index
- Retrieval metrics

Done when:

- Questions return relevant chunks.
- Results include enough metadata for citations.
- Latency is visible.

## Phase 6: Answer Generation With Citations

Build `POST /ask`.

Tasks:

- Retrieve top-k chunks.
- Build a grounded prompt.
- Require citation markers like `[1]`, `[2]`.
- Return answer, citations, chunks, and metrics.

Prompt rule:

```text
Answer only from the retrieved context. If the context is insufficient, say what is missing.
Use citations for claims that depend on source documents.
```

Done when:

- Answers cite source URLs.
- The UI can show which chunks supported the answer.
- The system refuses or qualifies answers when retrieval is weak.

## Phase 7: Retrieval Inspection UI

Build one useful page before adding more features.

UI sections:

- Question input
- Answer
- Citations
- Retrieved chunks
- Similarity scores
- Latency metrics
- Token usage
- Estimated cost

Done when:

- A viewer can inspect why the answer was generated.
- Retrieved chunks are visible without opening dev tools.
- Metrics are shown for each query.

## Phase 8: Manual Evaluation

Create a small evaluation set.

Fields:

```text
question
expected_source
expected_topic
top_k
retrieved_sources
useful_top_3_count
answer_grounded
notes
```

Initial test questions:

```text
How does LangGraph memory work?
What is the OpenAI Responses API?
How do FastAPI dependencies work?
How do embeddings support semantic search?
Compare LangGraph persistence and OpenAI conversation state.
Show documents mentioning streaming responses.
```

Done when:

- At least 10 seed questions have been manually reviewed.
- Obvious retrieval failures are understood.
- Next tuning step is clear.

## Phase 9: Tuning Loop

Tune in this order:

1. Text extraction quality
2. Chunk size
3. Chunk overlap
4. Top-k
5. Metadata filters
6. Embedding model

Do not add reranking until base retrieval behavior is visible and understood.

## Phase 10: Demo Polish

Tasks:

- Add README setup instructions.
- Add screenshots or demo notes.
- Add architecture diagram.
- Add known limitations.
- Add roadmap section.

Demo story:

```text
I built a production-style RAG system over AI engineering documentation.
It exposes retrieval internals so I can inspect relevance, latency, token usage, cost, and citations.
```

## Deferred Work After The MVP

Add only after the docs RAG loop works end to end:

- Reranking
- Retrieval evaluation dashboard
- Local embeddings
- Local LLM support
- Code repository ingestion
- AI news/trends collection
- Conversational history, memory, and agent capabilities
