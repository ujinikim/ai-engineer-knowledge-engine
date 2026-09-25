import asyncio
import json
from contextlib import contextmanager, nullcontext
from pathlib import Path

import pytest
import yaml

from app.services.update_collector import CollectionResult
from app.services.update_visibility import configured_active_source_slugs
from scripts import collect_updates


def events(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def install_runner_fakes(monkeypatch, result: CollectionResult) -> None:
    @contextmanager
    def acquired_lock(_engine):
        yield True

    class FakeCollector:
        def __init__(self, _db) -> None:
            pass

        async def collect(self, _sources, max_items_per_source, run_id):
            return result

    monkeypatch.setattr(collect_updates, "collector_run_lock", acquired_lock)
    monkeypatch.setattr(collect_updates, "load_sources", lambda _slugs: [{"slug": "source"}])
    monkeypatch.setattr(collect_updates, "SessionLocal", lambda: nullcontext(object()))
    monkeypatch.setattr(collect_updates, "UpdateCollectorService", FakeCollector)


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


def test_overlapping_collection_is_a_successful_skip(monkeypatch, capsys) -> None:
    @contextmanager
    def unavailable_lock(_engine):
        yield False

    monkeypatch.setattr(collect_updates, "collector_run_lock", unavailable_lock)

    assert asyncio.run(collect_updates.collect_once(12)) is False
    log_events = events(capsys.readouterr().out)

    assert [event["event"] for event in log_events] == ["collection_skipped"]
    assert log_events[0]["reason"] == "collection_already_running"


def test_partial_collection_is_reported_without_failing_process(monkeypatch, capsys) -> None:
    install_runner_fakes(
        monkeypatch,
        CollectionResult(
            sources_processed=1,
            updates_created=2,
            updates_quarantined=4,
            chunks_written=3,
            errors=1,
        ),
    )

    assert asyncio.run(collect_updates.collect_once(12)) is True
    completed = next(
        event
        for event in events(capsys.readouterr().out)
        if event["event"] == "collection_completed"
    )

    assert completed["status"] == "partial_success"
    assert completed["updates_created"] == 2
    assert completed["updates_quarantined"] == 4
    assert completed["chunks_written"] == 3


def test_all_source_failure_marks_the_job_failed(monkeypatch, capsys) -> None:
    install_runner_fakes(monkeypatch, CollectionResult(errors=2))

    with pytest.raises(collect_updates.CollectionRunFailed):
        asyncio.run(collect_updates.collect_once(12))

    log_events = events(capsys.readouterr().out)
    assert any(
        event["event"] == "collection_completed" and event["status"] == "failed"
        for event in log_events
    )
    assert any(
        event["event"] == "collection_failed"
        and event["exception_type"] == "CollectionRunFailed"
        for event in log_events
    )
