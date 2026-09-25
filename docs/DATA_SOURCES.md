# Data Sources

## Source Policy

The feed targets engineers building, operating, evaluating, and securing LLM agents. Sources must be dated, canonically linkable, and useful for that scope. A tagged practitioner feed is allowed as a curated source.

The collector accepts RSS, Atom, and curated HTML listing pages. Broad feeds use configured engineering terms before an item is stored or summarized. HTML sources use explicit link patterns and article-content selectors instead of a general crawler.

Stored documents must represent one retrievable content unit. Discovery, tag, category, and search pages are not valid article documents. Multi-story publications are split at source-defined boundaries when those boundaries are stable.

Sources are assigned one of two quality tiers:

- `primary`: first-party releases, changelogs, product news, research, and engineering posts
- `curated`: publications selected for consistent technical synthesis and editorial judgment

Primary sources use a credibility weight of `1.0` by default. Curated analysis is weighted below original evidence and is visibly labeled in the feed.

## Configured Sources

`backend/data/update_sources.yml` is the sole source registry. Collection writes per-source outcomes to `collection_source_runs`; the database does not hold another copy of source configuration.

| Slug | Organization | Source type | Default topic | Active |
|---|---|---|---|---|
| `langchain-blog` | LangChain | Official engineering blog | Agentic & Generative AI | Yes |
| `microsoft-foundry` | Microsoft | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `google-developers` | Google | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `github-changelog` | GitHub | Official changelog | AI Products, Engineering & Infrastructure | Yes |
| `aws-machine-learning` | Amazon Web Services | Official engineering blog | AI Products, Engineering & Infrastructure | Yes |
| `anthropic-engineering` | Anthropic | Official engineering blog | Agentic & Generative AI | Yes |
| `mcp-blog` | Model Context Protocol | Official engineering blog | Agentic & Generative AI | Yes |
| `letta-blog` | Letta | Official engineering blog | Agentic & Generative AI | Yes |
| `crewai-blog` | CrewAI | Official engineering blog | Agentic & Generative AI | Yes |
| `simon-agentic-engineering` | Simon Willison | Curated analysis | Agentic & Generative AI | Yes |

Retired update sources have been removed from this registry and the local update database. Historical migrations and archived evaluations still document earlier source decisions. Collection, the dashboard, and RAG use only configured sources.

Source-specific boundaries:

- Anthropic Engineering and Letta use dated article listings and extract the article body; undated listing entries are skipped.
- MCP, CrewAI, and Simon Willison use their RSS or Atom feeds and hydrate individual articles. Feed titles are preserved when a page has a generic site heading. Simon's event and quote posts are skipped.
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
