import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock

import httpx

from app.core.model_usage import ModelUsage
from app.db.models import CollectionSourceRun
from app.services import source_extraction
from app.services.update_collector import UpdateCollectorService
from app.services.updates import UpdateService


def test_collection_records_success_and_failure_for_one_run(monkeypatch) -> None:
    feed = b"<rss version='2.0'><channel><item><title>Agent tools</title><link>https://example.com/article</link><description>Agent tool details</description></item></channel></rss>"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500 if request.url.path == "/broken" else 200, content=feed)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(source_extraction.asyncio, "sleep", no_sleep)
    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    db = MagicMock()
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = db
    collector.usage = ModelUsage()
    collector._upsert_entry = lambda source_slug, config, entry: ("created", 2)

    result = asyncio.run(
        collector.collect(
            [
                {"slug": "working", "feed_url": "https://example.com/feed", "source_kind": "rss"},
                {"slug": "broken", "feed_url": "https://example.com/broken", "source_kind": "rss"},
            ],
            max_items_per_source=1,
            run_id="test-run",
        )
    )

    runs = [call.args[0] for call in db.add.call_args_list]
    assert all(isinstance(run, CollectionSourceRun) for run in runs)
    assert [(run.source_slug, run.status) for run in runs] == [
        ("working", "completed"),
        ("broken", "failed"),
    ]
    assert runs[0].run_id == runs[1].run_id == "test-run"
    assert (runs[0].matched_items, runs[0].updates_created, runs[0].chunks_written) == (1, 1, 2)
    assert runs[1].error and "500" in runs[1].error
    assert (result.sources_processed, result.updates_created, result.errors) == (1, 1, 1)
    assert db.rollback.call_count == 1


def test_source_list_comes_from_yaml_without_run_history() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    sources = UpdateService(db).list_sources()

    assert len(sources) == 10
    assert any(source.slug == "mcp-blog" and source.last_collected_at is None for source in sources)


def test_source_list_keeps_last_success_time_after_failure() -> None:
    db = MagicMock()
    failed = CollectionSourceRun(
        source_slug="mcp-blog", status="failed", error="HTTP 500",
        finished_at=datetime(2026, 9, 25, 12, 0),
    )
    succeeded = CollectionSourceRun(
        source_slug="mcp-blog", status="completed",
        finished_at=datetime(2026, 9, 24, 12, 0),
    )
    db.scalars.return_value.all.side_effect = [[failed], [succeeded]]

    source = next(source for source in UpdateService(db).list_sources() if source.slug == "mcp-blog")

    assert source.last_collected_at == datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    assert source.last_error == "HTTP 500"
