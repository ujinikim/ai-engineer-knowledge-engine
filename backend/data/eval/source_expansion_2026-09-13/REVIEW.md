# Source Expansion Pilot Review

## Scope

- Local-only collection of `langchain-blog` and `microsoft-foundry`
- Requested maximum: 20 entries per source
- Collected: 20 LangChain articles and all 9 entries currently exposed by the
  Microsoft Foundry feed
- No production collection, deployment, or database change

## Collection Result

| Source | Stored | Core | Contextual | Excluded | Quarantined |
|---|---:|---:|---:|---:|---:|
| LangChain Blog | 20 | 14 | 5 | 1 | 0 |
| Microsoft Foundry | 9 | 7 | 2 | 0 | 0 |
| Total | 29 | 21 | 7 | 1 | 0 |

The expansion run created 19 new records, refreshed one changed LangChain article,
and retained nine unchanged records. It wrote 126 chunks with no collector errors.
The run used 106,057 chat input tokens, 6,569 chat output tokens, and 53,149 embedding
tokens, for an estimated model cost of $0.053996.

## Extraction Result

- Microsoft Foundry: 9 pass, 0 warning, 0 fail
- LangChain: 19 pass, 1 warning, 0 fail after accounting for intentionally unchunked
  excluded records
- The LangChain newsletter warning exposed a Unicode boundary defect in long-block
  chunking. The splitter now uses character-safe token-bounded slices; existing stored
  pilot chunks were retained so the report continues to document the original warning.

Detailed reports and human-review samples are retained locally in the
`langchain/` and `microsoft-foundry/` directories beside this file. They are
not committed to the public repository.

## Relevance Replay

A read-only GPT-4.1-mini replay agreed with 27 of 29 stored decisions. Its resulting
tier counts were 16 core and 4 contextual for LangChain, and 7 core and 2 contextual
for Microsoft. Two individual LangChain decisions warrant human review:

1. `Introducing Interrupt: The AI Agent Conference by LangChain` was stored as
   `excluded` but replayed as `core`. The stored exclusion better matches the policy:
   this is event promotion rather than technical agent-engineering evidence.
2. `Aligning LLM-as-a-Judge with Human Preferences` was stored as `contextual` but
   replayed as `core`. The article is valuable evaluation background, but agent systems
   are not clearly its central subject, so `contextual` is the safer default.

The read-only relevance replay cost an estimated $0.031572 across both sources.

## Decision

Both sources are suitable for a controlled production collection. Keep the existing
relevance gate and review the first production batch before using the expanded corpus
as the baseline for agentic Ask evaluation. Do not broaden LangChain title exclusions
from this single conference example yet; retain it as a regression case instead.
