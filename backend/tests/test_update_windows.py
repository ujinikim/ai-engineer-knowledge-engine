from types import SimpleNamespace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.serving.feed import FeedService
from app.ingestion.store import find_existing_article, normalize_url, url_candidates


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


def test_document_urls_normalize_trailing_slashes_without_losing_fragments():

    assert (
        normalize_url("https://example.com/releases/item/#details")
        == "https://example.com/releases/item#details"
    )
    assert url_candidates(
        "https://example.com/releases/item/"
    ) == [
        "https://example.com/releases/item",
        "https://example.com/releases/item/",
    ]


def test_document_urls_normalize_hosts_queries_and_tracking_parameters():

    assert normalize_url(
        "HTTPS://Example.COM:443/article/?b=2&utm_source=email&a=1#section"
    ) == "https://example.com/article?a=1&b=2#section"


def test_existing_document_lookup_uses_url_without_duplicate_column():
    db = MagicMock()
    db.scalar.return_value = None

    find_existing_article(
        db,
        SimpleNamespace(
            source_slug="example",
            raw_url="https://example.com/article/",
            title="Agent article",
            content_hash="hash",
        ),
    )

    statement = db.scalar.call_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "documents.url IN ('https://example.com/article', 'https://example.com/article/')" in sql
    assert "canonical_url" not in sql
