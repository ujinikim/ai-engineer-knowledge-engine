from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.db.models import CollectionSourceRun
from app.serving.feed import FeedService
from tests.factories import make_article


def make_document(
    *,
    title: str = "v1.2.3",
    body: str = "Fix query errors when using shard keys while resharding.",
    event_types: list[str] | None = None,
):
    return make_article(
        title=title,
        raw_text=f"{title}\n\n{body}",
        event_types=event_types or ["release-update"],
        extraction_status="source_entry",
    )


def test_source_list_comes_from_yaml_without_run_history() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    sources = FeedService(db).list_sources()

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

    source = next(source for source in FeedService(db).list_sources() if source.slug == "mcp-blog")

    assert source.last_collected_at == datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    assert source.last_error == "HTTP 500"


def test_sparse_detail_alone_does_not_hide_published_core_document() -> None:
    service = FeedService.__new__(FeedService)
    document = make_document()

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_explicit_inclusion_and_source_or_tool_context_show_sparse_document() -> None:
    service = FeedService.__new__(FeedService)
    document = make_document()

    assert service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=False,
    )
    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=True,
    )


def test_quarantined_document_stays_hidden_even_when_sparse_is_requested() -> None:
    service = FeedService.__new__(FeedService)
    document = make_document(event_types=["security-issue"])
    document.ingestion_status = "quarantined"

    assert not service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=True,
    )
    assert not service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=True,
    )


def test_approved_official_sparse_excerpt_can_appear_in_feed() -> None:
    service = FeedService.__new__(FeedService)
    document = make_document()
    document.extraction_status = "feed_excerpt_only"

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_contextual_feed_entries_require_explicit_inclusion() -> None:
    service = FeedService.__new__(FeedService)
    document = make_document()
    document.relevance_tier = "contextual"

    assert not service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )
    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
        include_contextual=True,
    )


def test_excluded_feed_entries_stay_hidden_when_contextual_is_included() -> None:
    service = FeedService.__new__(FeedService)
    document = make_document()
    document.relevance_tier = "excluded"

    assert not service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=True,
        include_contextual=True,
    )


def test_empty_updates_query_builds_enabled_source_filters():
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    response = FeedService(db).list_updates(window="week", limit=1, offset=0)

    assert response.stats.total_updates == 0
    assert db.scalars.call_count == 2


def test_update_windows_are_rolling_ranges():
    end = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)

    assert FeedService.window_start("day", end) == end - timedelta(days=1)
    assert FeedService.window_start("week", end) == end - timedelta(days=7)
    assert FeedService.window_start("month", end) == end - timedelta(days=30)
    assert FeedService.window_start("all", end) is None
