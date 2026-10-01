import asyncio
from unittest.mock import MagicMock

import httpx

from app.core.model_usage import ModelUsage
from app.db.models import CollectionSourceRun
from app.ingestion import fetch
from app.ingestion.ingest import ArticleIngestor
from app.ingestion.pipeline import IngestionPipeline
from tests.fakes import MustNotRun


def test_collection_records_success_and_failure_for_one_run(monkeypatch) -> None:
    feed = b"<rss version='2.0'><channel><item><title>Agent tools</title><link>https://example.com/article</link><description>Agent tool details</description></item></channel></rss>"

    def respond(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500 if request.url.path == "/broken" else 200, content=feed)

    async def no_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr(fetch.asyncio, "sleep", no_sleep)
    transport = httpx.MockTransport(respond)
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        httpx,
        "AsyncClient",
        lambda **kwargs: original_client(transport=transport, **kwargs),
    )
    monkeypatch.setattr(ArticleIngestor, "ingest", lambda self, slug, config, entry: ("created", 2))
    db = MagicMock()
    collector = IngestionPipeline.__new__(IngestionPipeline)
    collector.db = db
    collector.usage = ModelUsage()
    collector.run_id = None
    for name in ("relevance", "summarizer", "chunker", "embedder"):
        setattr(collector, name, MustNotRun(name))

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
