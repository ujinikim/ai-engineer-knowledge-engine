from pathlib import Path

import pytest
import yaml

from app.sources import configured_active_source_slugs, source_attribute, source_slugs_with
from scripts import collect_updates


def test_default_collection_contains_only_selected_agent_sources() -> None:
    sources = collect_updates.load_sources()
    slugs = {source["slug"] for source in sources}

    assert slugs == {
        "langchain-blog", "microsoft-foundry", "google-developers",
        "github-changelog", "aws-machine-learning", "anthropic-engineering",
        "mcp-blog", "letta-blog", "crewai-blog", "simon-agentic-engineering",
    }


def test_removed_sources_are_not_in_the_registry() -> None:
    for slug in (
        "vllm", "langgraph", "transformers", "litellm", "qdrant", "ollama",
        "openai-news", "huggingface-blog", "nvidia-technical-blog",
        "anthropic-news", "deepmind-blog", "pytorch-blog", "the-batch", "import-ai",
    ):
        with pytest.raises(ValueError, match="Unknown source slug"):
            collect_updates.load_sources([slug])


def test_feed_visibility_uses_only_current_registry() -> None:
    active = set(configured_active_source_slugs())
    assert "anthropic-engineering" in active
    assert "anthropic-news" not in active
    assert "openai-news" not in active


def test_new_agent_engineering_sources_use_official_rss_and_full_article_hydration() -> None:
    source_file = Path(__file__).resolve().parents[1] / "data" / "update_sources.yml"
    sources = {
        source["slug"]: source
        for source in yaml.safe_load(source_file.read_text(encoding="utf-8"))["sources"]
    }

    langchain = sources["langchain-blog"]
    assert langchain["source_kind"] == "rss"
    assert langchain["feed_url"] == "https://www.langchain.com/blog/rss.xml"
    assert langchain["fetch_full_article"] is True
    assert langchain["content_selector"] == ".text-rich-text-v2-blog-post"

    foundry = sources["microsoft-foundry"]
    assert foundry["source_kind"] == "rss"
    assert foundry["feed_url"] == "https://devblogs.microsoft.com/foundry/feed/"
    assert foundry["fetch_full_article"] is True
    assert foundry["content_selector"] == "main"

    assert sources["mcp-blog"]["feed_url"] == "https://blog.modelcontextprotocol.io/index.xml"
    assert sources["crewai-blog"]["feed_url"] == "https://blog.crewai.com/rss/"
    assert sources["simon-agentic-engineering"]["feed_url"].endswith("/agentic-engineering.atom")
    assert sources["anthropic-engineering"]["require_published_date"] is True
    assert sources["letta-blog"]["require_published_date"] is True


def test_source_attributes_come_from_configuration() -> None:
    assert source_attribute("github-changelog", "source_type") == "official-changelog"
    assert source_attribute("github-changelog", "tool") == "GitHub Copilot"
    assert source_attribute("retired-source", "tool") is None
    assert source_attribute("retired-source", "credibility_weight", 1.0) == 1.0
    assert source_slugs_with("tool", ["GitHub Copilot"]) == ["github-changelog"]
    assert "simon-agentic-engineering" in source_slugs_with("source_type", ["editorial-analysis"])
