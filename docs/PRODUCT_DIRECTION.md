# Product Direction

## Intended Use Case

The product is moving toward a personal AI engineering intelligence dashboard:

> Help a developer identify important AI engineering changes, understand their impact, and decide what to learn or try next.

It is not intended to become a general news reader or an open-ended chatbot. The article feed is the primary experience. RAG is the evidence-backed analysis layer attached to the current feed context.

## Core User Loop

1. See what changed today, this week, this month, or since the last visit.
2. Narrow the feed to followed tools, topics, event types, or sources.
3. Generate a short cited brief over the current view.
4. Inspect original sources or ask a focused follow-up question.
5. Save useful updates and concepts to a learning queue.

## Candidate Product Modes

- Personal update digest: important changes since the last visit
- Developer learning radar: recurring concepts and skills worth learning
- Release impact monitor: breaking changes, migrations, and effects on a configured stack
- Trend explorer: cross-source patterns over longer time windows
- Contextual research assistant: cited answers over the currently selected updates

## Recommended Feature Order

1. Contextual `Brief me` synthesis over the active filters
2. Today, week, month, and since-last-visit navigation
3. Lightweight followed tools and topics
4. Saved articles and a learning queue
5. Developer-impact and learning-guide brief modes
6. Cross-source story clustering

These features are intentionally deferred while source quality, extraction quality, and summary grounding are improved.
