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

| Slug | Organization | Source type | Default topic |
|---|---|---|---|
| `vllm` | vLLM Project | Official release | Inference & Serving |
| `langgraph` | LangChain | Official release | Agents & Orchestration |
| `transformers` | Hugging Face | Official release | Models & APIs |
| `litellm` | BerriAI | Official release | Models & APIs |
| `qdrant` | Qdrant | Official release | Retrieval & Data |
| `ollama` | Ollama | Official release | Inference & Serving |
| `openai-news` | OpenAI | Official product news | Models & APIs |
| `google-developers` | Google | Official engineering blog | Developer Tools |
| `github-changelog` | GitHub | Official changelog | Developer Tools |
| `huggingface-blog` | Hugging Face | Official engineering blog | Models & APIs |
| `pytorch-blog` | PyTorch Foundation | Official engineering blog | Training & Fine-Tuning |
| `nvidia-technical-blog` | NVIDIA | Official engineering blog | Infrastructure & Hardware |
| `aws-machine-learning` | Amazon Web Services | Official engineering blog | Infrastructure & Hardware |
| `anthropic-news` | Anthropic | Official product news | Models & APIs |
| `deepmind-blog` | Google DeepMind | Official engineering blog | Models & APIs |
| `the-batch` | DeepLearning.AI | Editorial analysis | Developer Tools |
| `import-ai` | Import AI | Editorial analysis | Models & APIs |

Source-specific boundaries:

- The Batch issue pages are discovery parents; each news story is stored under its individual story URL. The matching issue section is retained as an extraction fallback.
- Import AI newsletters are split at explicit section delimiters. The original newsletter remains the canonical parent URL.
- Anthropic news pages use the nested article body and exclude related-content cards.
- GitHub Changelog relevance terms use token boundaries, so `ai` does not match unrelated words such as `available`.

## Controlled Taxonomy

Primary topics:

```text
models-apis
agents-orchestration
inference-serving
retrieval-data
training-fine-tuning
evaluation-observability
developer-tools
infrastructure-hardware
safety-security
```

Additional axes are event types, source type, maturity, topic tags, and entity tags. Allowed values are defined in `backend/app/services/taxonomy.py`.

## Stored Layers

Original evidence:

```text
title, canonical_url, raw_text, content_hash
published_at, fetched_at, original chunks, embeddings
```

Derived feed content:

```text
display_headline, summary, why_it_matters, key_points
primary_topic, topic_tags, event_types, entity_tags
source_type, maturity, summary_generated_by
```

Derived fields can be regenerated. Original evidence remains the source for RAG answers and citations.

## Deferred Sources

- Hugging Face Trending Papers or another filtered research signal. A popularity page needs dated ranking snapshots; treating an old paper as newly published would be misleading.
- Community discovery signals such as Hacker News and GitHub velocity

Independent and community sources should follow cross-source story clustering so the same announcement does not dominate the feed several times.
