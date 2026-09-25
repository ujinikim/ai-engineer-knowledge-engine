# Agent-focused source and filtering audit

Research date: September 25, 2026. The audit below records the pre-change source list. PyTorch Blog, The Batch, and Import AI were subsequently removed from the local source configuration; stored database rows were not changed. Evidence: the checkout at audit time, saved September 13–14 evaluations, and public publisher pages. Production deployment and database state were not inspected.

## Local pilot update

Anthropic Newsroom, OpenAI News, Hugging Face Blog, NVIDIA Technical Blog, and DeepMind Blog were disabled, then removed from the local update registry along with the six repository-release feeds. Previously removed PyTorch Blog, The Batch, and Import AI records were also purged from the local update database. Anthropic Engineering, the MCP blog, Letta, CrewAI, and Simon Willison's agentic-engineering tag are enabled. Historical migrations and evaluation artifacts were retained.

A manual local pilot collected two articles per new source: 10 created, 0 quarantined, 0 collection errors. Anthropic Engineering, MCP, Letta, and CrewAI each had two model-assigned core articles. Simon's two articles were excluded and contextual, respectively. These are initial pipeline results, not human-verified precision; inspect a larger sample before increasing collection volume.

## Recommendation

Prioritize LangChain, Anthropic Engineering, MCP, Letta, and Microsoft Foundry. Pause the broadest low-yield feeds; retain selected broad publishers behind article-level filtering. Fix classification fallback behavior before expanding collection.

## Source decisions at audit time

At audit time, the registry had 13 enabled sources and six disabled repository-release sources. Counts below are **model-assigned core labels in saved, already-collected samples**, not human-verified precision or whole-publisher acceptance rates. The 174-article evaluation is separate from the LangChain and Foundry pilots.

| Current source | Saved core / evaluated | Recommendation |
|---|---:|---|
| LangChain Blog | 16/20 | Keep as a main source; exclude promotion without technical substance. |
| Microsoft Foundry | 7/9 | Keep; target agent runtime, tools, memory, evaluation, and security. |
| Anthropic Newsroom | 1/13 | Replace as the main Anthropic source with Engineering; retain selected technical announcements if useful. |
| AWS ML Blog | 16/21 | Keep selectively; concentrate on agent orchestration and operation, not all Bedrock/SageMaker posts. |
| NVIDIA Technical Blog | 11/17 | Narrow to explicit agent systems; remove standalone GPU/CUDA/inference eligibility. |
| Hugging Face Blog | 12/20 | Narrow to agent frameworks, tools, environments, and agent benchmarks. |
| Google Developers | 9/15 | Narrow to agent development, tools, and protocols; generic Gemini/model news is insufficient. |
| GitHub Changelog | 5/14 | Keep agent/MCP changes; ordinary Copilot or model availability is not automatically relevant. |
| OpenAI News | 6/26 | Keep only technical agent/tool changes; 22 sampled articles were evidence-blocked, a separate extraction concern. |
| DeepMind Blog | 6/13 | Move to an optional research lane or pause during the focused pilot; retain selected agent evaluation/safety research. |
| PyTorch Blog | 3/11 | Pause default collection. General training/compiler coverage is outside the intended scope. |
| The Batch | 2/12 | Pause default collection; broad editorial coverage and multi-story extraction add work. |
| Import AI | 3/12 | Pause default collection; optional research discovery later. |

These are source-fit judgments, not judgments of publisher quality. [PyTorch's current listing](https://pytorch.org/blog/) emphasizes training, kernels, ecosystem announcements, and events. [Import AI](https://jack-clark.net/) spans research and policy. The Batch's page returned 403 during this research; its recommendation rests on local configuration and saved samples. Broad sources can still contain valuable agent articles: source selection must not replace article review.

Local evaluation artifacts (retained outside the public repository):

- `backend/data/eval/summaries/article_relevance_evaluation_2026-09-13-v2-final.json`
- `backend/data/eval/source_expansion_2026-09-13/langchain/relevance_review.json`
- `backend/data/eval/source_expansion_2026-09-13/microsoft-foundry/relevance_review.json`

Disabling a source currently removes it from enabled-source feed/retrieval queries while retaining stored data. A separate optional source lane would require a small extension; it is not already implemented by the contextual toggle.

## Better additions

| Source | Evidence of fit | Ingestion assessment |
|---|---|---|
| [Anthropic Engineering](https://www.anthropic.com/engineering) | Agent evaluations, tool design, context management, harnesses, and containment. Example: [agent evaluation guide](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents). | Highest-priority addition. Existing HTML-listing collector is a starting point; validate dates and selectors. Current newsroom link pattern excludes `/engineering/`. |
| [MCP official blog](https://blog.modelcontextprotocol.io/) | Protocol releases, SDK changes, and implementation guidance from maintainers. | Publisher exposes RSS. Validate the linked feed and article extraction before enabling. Exclude community announcements without an engineering change. |
| [Letta](https://www.letta.com/blog/) | Stateful agents, memory, context, and agent runtimes. Example: [memory and harness design](https://www.letta.com/blog/why-memory-isnt-a-plugin/). | HTML-listing pilot; no feed verified here. Check full article dates and bodies. |
| [CrewAI](https://blog.crewai.com/) | Multi-agent implementation and operation. Example: [agent database access](https://blog.crewai.com/stop-giving-your-agents-database-credentials/). | RSS endpoint `/rss/` responded as RSS to the web tool, but parsing was not verified. Filter customer promotion and events. |
| [Simon Willison: agentic engineering](https://simonwillison.net/tags/agentic-engineering/) | Practitioner observations about coding agents; adds a perspective outside framework vendors. | Optional curated pilot. [Author documents tag Atom feeds](https://simonwillison.net/about/); validate `/tags/agentic-engineering.atom`. Exclude event notices and short link posts lacking useful evidence; deduplicate canonical URLs across tags. |
| [LlamaIndex](https://www.llamaindex.ai/blog) | Some useful agent workflows, but current listing also contains extensive OCR, extraction, and commercial content. | Defer the broad feed. Pilot selected engineering articles only; no feed verified here. |

LangChain and Foundry are already enabled, not new additions. Their public listings continue to show relevant material: [LangChain](https://www.langchain.com/blog), [Foundry](https://devblogs.microsoft.com/foundry/).

The source candidates were subsequently checked with direct feed/listing requests and article extraction, then ingested in the limited local pilot described above. No new source has received a representative acceptance-rate evaluation.

## Filtering findings and changes

1. **Stop treating uncertainty as core.** `ArticleRelevanceService._fail_open()` returns core on missing credentials, model errors, or invalid output. `stored_relevance_tier()` treats missing/malformed labels as core; retrieval also admits null labels. Preserve these articles for retry/review, but keep them out of the default feed and default RAG until classified. This is a proposed behavior change, not proof of the current production cause.
2. **Require meaningful evidence, not just a matching quote.** The current quote validator checks that text exists in the article/title; it cannot establish agent relevance. The saved evaluation labels “Triton Plugin Extensions” core, cites its non-agent title, and invents an agent-infrastructure justification. Make this a negative regression case and require a passage showing the actual agent mechanism and the article's engineering contribution. Do not merely demand the word “agent.”
3. **Keep discovery and publication separate.** Broad terms such as model, AI, GPU, and training admit many candidates. For broad feeds, use explicit agent phrases and maintained framework/protocol aliases; support plurals because the current boundary matcher does not make `agent` match `agents` or `agentic`. For focused sources, allow broader discovery, then classify the extracted article. Audit rejected candidates so a strict prefilter does not silently lose relevant posts.
4. **Use the existing tiers consistently.** Core requires a central contribution to building, operating, evaluating, or securing an LLM agent. Contextual is related background and stays opt-in. Excluded covers unrelated material, generic marketing, and event promotion. Do not conflate distributed actors, ordinary ML training, or generic RAG with LLM agents. A technical agent release, measured failure analysis, or concrete workflow can qualify; code is not mandatory.
5. **Preserve decision provenance.** Record source/body hash, policy and model versions, reason, and evidence passage. The unchanged-content reuse branch currently copies tier/reason/status but omits agent focus/evidence fields. Preserve them and retry previous failures. A policy update must re-evaluate existing rows, not only future articles. The saved evaluation is read-only; it does not demonstrate a database backfill.

## Benchmark before changing the pipeline

Create a frozen, human-labeled set of roughly 100 articles spanning clear positives, general AI negatives, marketing that mentions agents, and difficult boundary cases. Include broad-source prefilter rejects and focused-source posts. Keep a holdout separate from prompt tuning.

For each proposed change, compare:

- Core precision: how many included articles humans consider agent-relevant.
- Core recall: how many human-labeled agent articles survive discovery and classification.
- Errors by source and reason; extraction failures and unclassified counts separately.
- Newly included/excluded article URLs, previous/new decisions, and supporting passages.
- Duplicate rate and useful unique articles per source, alongside processing cost.

Suggested initial gates, subject to baseline review: at least 90% core precision, at least 85% core recall on the labeled set, and zero unknown/error classifications appearing as core. Report counts and sample size, not percentages alone. These are proposed targets, not achieved results.

Order: verify deployed policy/backfill state → label baseline → fix fallback/evidence issues → pilot Anthropic Engineering and MCP → compare before/after → add Letta or CrewAI if they contribute useful coverage. Source changes and classifier changes should be evaluated separately to identify what helped.
