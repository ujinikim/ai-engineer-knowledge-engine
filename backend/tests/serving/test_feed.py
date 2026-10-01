from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

from app.db.models import CollectionSourceRun
from app.serving.feed import FeedService
from tests.factories import make_article


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


def test_equal_scores_are_ordered_newest_first_then_by_id_whatever_the_row_order() -> None:
    same_day = datetime(2026, 9, 20)
    older = make_article(source_name="mcp-blog", published_at=same_day - timedelta(hours=1), id="a")
    first = make_article(source_name="mcp-blog", published_at=same_day, id="b")
    second = make_article(source_name="mcp-blog", published_at=same_day, id="c")

    def ordered(rows):
        db = MagicMock()
        db.scalars.return_value.all.side_effect = [rows, []]
        response = FeedService(db).list_updates(window="all", limit=10, offset=0)
        return [item.id for item in response.items]

    assert ordered([older, first, second]) == ordered([second, older, first]) == ["c", "b", "a"]
