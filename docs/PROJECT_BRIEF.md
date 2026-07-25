# Project Brief

## Goal

Build an article-style feed that tracks recent AI engineering changes across official sources and supports grounded investigation through RAG.

The feed is a deterministic database view over stored structured summaries. A separate LLM analysis layer receives only original chunks retrieved from the selected collection, time window, and facets.

## Core Questions

- What were the most significant developer-tool releases this week?
- What changed in inference and serving tools this month?
- Compare recent LangGraph and LiteLLM updates.
- Which releases mention MCP, structured output, or speculative decoding?
- What evidence supports an emerging trend across several tools?

## Strict RAG Boundary

- Collection happens before question answering.
- The LLM does not browse or call source websites.
- The question's time and facet filters are applied during retrieval.
- Answers use only retrieved evidence and expose that evidence.
- Factual claims are expected to use bracketed citations.
- Unsupported questions produce a retrieval warning or an explicit limitation.

## MVP Scope

- Seventeen quality-tiered release, changelog, newsroom, engineering, and editorial sources
- Ingestion-time structured summaries and controlled taxonomy metadata
- Idempotent periodic collection
- Publication-time metadata and deterministic ranking
- Rolling daily, weekly, and monthly dashboard windows
- Recency-aware hybrid retrieval
- Grounded answers with citations and diagnostics
- Documentation retained as a separate optional collection

## Deferred

- General technology news crawling and unlicensed full-article replication
- Story clustering across several publications
- Popularity or social-engagement ranking
- Cross-source clustering and community popularity signals
- Accounts, alerts, agents, memory, and personalized feeds

## Success Criteria

- A new collection run adds or updates releases without duplicates.
- Dashboard windows return the correct dated updates.
- Filters work consistently in the feed and RAG request.
- Answers cite only evidence retrieved from the selected period.
- Retrieval and generation internals remain inspectable.
