from datetime import datetime, timedelta, timezone

from app.services.updates import UpdateService
from app.services.update_collector import UpdateCollectorService


def test_update_windows_are_rolling_ranges():
    end = datetime(2026, 7, 21, 12, tzinfo=timezone.utc)

    assert UpdateService.window_start("day", end) == end - timedelta(days=1)
    assert UpdateService.window_start("week", end) == end - timedelta(days=7)
    assert UpdateService.window_start("month", end) == end - timedelta(days=30)
    assert UpdateService.window_start("all", end) is None


def test_release_channels_distinguish_prereleases():
    collector = UpdateCollectorService.__new__(UpdateCollectorService)

    assert collector._release_channel("v1.4.0") == "stable"
    assert collector._release_channel("v1.5.0-rc.2") == "prerelease"
    assert collector._release_channel("v2.0.0-beta1") == "prerelease"
    assert collector._release_channel("v3.0.0-dev.4") == "prerelease"


def test_document_urls_normalize_trailing_slashes_without_losing_fragments():
    collector = UpdateCollectorService.__new__(UpdateCollectorService)

    assert (
        collector._normalize_document_url("https://example.com/releases/item/#details")
        == "https://example.com/releases/item#details"
    )
    assert collector._document_url_candidates(
        "https://example.com/releases/item/"
    ) == [
        "https://example.com/releases/item",
        "https://example.com/releases/item/",
    ]
