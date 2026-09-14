# Data Sources

## Source Policy

The feed targets engineers building LLM applications and infrastructure. Sources must be first-party, dated, canonically linkable, and useful for models, APIs, agents, inference, retrieval, training, evaluation, developer tools, infrastructure, or security.

The collector accepts RSS, Atom, and curated HTML listing pages. Broad feeds use configured engineering terms before an item is stored or summarized. HTML sources use explicit link patterns and article-content selectors instead of a general crawler.

Stored documents must represent one retrievable content unit. Discovery, tag, category, and search pages are not valid article documents. Multi-story publications are split at source-defined boundaries when those boundaries are stable.

Sources are assigned one of two quality tiers:

- `primary`: first-party releases, changelogs, product news, research, and engineering posts
- `curated`: publications selected for consistent technical synthesis and editorial judgment

Primary sources use a credibility weight of `1.0` by default. Curated analysis is weighted below original evidence and is visibly labeled in the feed.

## Configured Sources

The registry lives in `backend/data/update_sources.yml` and is copied into `update_sources` during collection.

| Slug | Organization | Source type | Default topic | Active |
|---|---|---|---|---|
| `vllm` | vLLM Project | Official release | AI Products, Engineering & Infrastructure | No |
| `langgraph` | LangChain | Official release | Agentic & Generative AI | No |
| `transformers` | Hugging Face | Official release | Machine Learning & Classical AI | No |
| `litellm` | BerriAI | Official release | AI Products, Engineering & Infrastructure | No |
| `qdrant` | Qdrant | Official release | Data, Search & Retrieval | No |
| `ollama` | Ollama | Official release | Agentic & Generative AI | No |
| `openai-news` | OpenAI | Official product news | Agentic & Generative AI | Yes |
| `langchain-blog` | LangChain | Official engineering blog | Agentic & Generative AI | Yes |
| `microsoft-foundry` | Microsoft | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `google-developers` | Google | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `github-changelog` | GitHub | Official changelog | AI Products, Engineering & Infrastructure | Yes |
| `huggingface-blog` | Hugging Face | Official engineering blog | Agentic & Generative AI | Yes |
| `pytorch-blog` | PyTorch Foundation | Official engineering blog | Machine Learning & Classical AI | Yes |
| `nvidia-technical-blog` | NVIDIA | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `aws-machine-learning` | Amazon Web Services | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `anthropic-news` | Anthropic | Official product news | Agentic & Generative AI | Yes |
| `deepmind-blog` | Google DeepMind | Official engineering blog | Machine Learning & Classical AI | Yes |
| `the-batch` | DeepLearning.AI | Editorial analysis | AI Products, Engineering & Infrastructure | Yes |
| `import-ai` | Import AI | Editorial analysis | Machine Learning & Classical AI | Yes |

Raw GitHub repository release feeds remain configured but disabled. Their existing
documents and chunks are retained for later evaluation. Scheduled collection, the
dashboard, and RAG use only enabled sources. Passing a disabled slug explicitly with
`--source` remains available for controlled experiments.

Source-specific boundaries:

- The Batch issue pages are discovery parents; each news story is stored under its individual story URL. The matching issue section is retained as an extraction fallback.
- Import AI newsletters are split at explicit section delimiters. The original newsletter remains the canonical parent URL.
- Anthropic news pages use the nested article body and exclude related-content cards.
- LangChain Blog uses its official RSS feed and hydrates only the article body. The feed supplies dated, canonical article URLs; filtering keeps the vendor's broader marketing and customer-story mix from overwhelming agent-engineering coverage.
- Microsoft Foundry Blog uses its official RSS feed and full-article extraction. The terms focus its broader Azure AI coverage on agent services, tools, retrieval, evaluation, deployment, safety, and related platform engineering.
- GitHub Changelog relevance terms use token boundaries, so `ai` does not match unrelated words such as `available`.

## Controlled Taxonomy

Primary topics:

```text
agentic-generative-ai
machine-learning-classical-ai
vision-speech-robotics
data-search-retrieval
ai-products-engineering-infrastructure
safety-evaluation-governance
```

Each taxonomy-v2 article has exactly one broad primary topic and at most one event:
`release-update`, `research`, `guide`, `analysis`, or `alert`. `topic_tags` remains
an empty compatibility field. Entity tags, source type, and maturity remain metadata,
not additional reader-facing topic categories. Allowed values are defined in
`backend/app/services/taxonomy.py`.

## Stored Layers

Original evidence:

```text
title, canonical_url, raw_text, content_hash
published_at, fetched_at, original chunks, embeddings
```

Derived feed content:

```text
display_headline, summary, why_it_matters, key_points
primary_topic, event_types, entity_tags, taxonomy_policy_version
source_type, maturity, summary_generated_by
```

Derived fields can be regenerated. Original evidence remains the source for RAG answers and citations.

## Deferred Sources

- Google Cloud AI and ML Blog has no verified, stable public feed or server-rendered article listing suitable for the current deterministic collector. Add it only with a paginated, date-aware listing adapter and a focused pilot.
- LlamaIndex Blog has no verified public feed and its listing has a commercial/SEO-heavy mix. It remains a tightly filtered HTML-listing pilot candidate after the current sources establish an acceptance baseline.
- Hugging Face Trending Papers or another filtered research signal. A popularity page needs dated ranking snapshots; treating an old paper as newly published would be misleading.
- Community discovery signals such as Hacker News and GitHub velocity

Independent and community sources should follow cross-source story clustering so the same announcement does not dominate the feed several times.
