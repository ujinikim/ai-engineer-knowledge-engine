from app.domain import article_excerpt
from app.ingestion.parsing import entry_datetime, html_listing_entries, matches_config


def test_feed_filtering_uses_title_and_body() -> None:
    config = {"include_terms": ["agent", "inference"]}

    assert matches_config(config, {"title": "New inference runtime", "summary": ""})
    assert not matches_config(config, {"title": "Cloud billing update", "summary": ""})


def test_feed_filtering_uses_term_boundaries() -> None:
    config = {"include_terms": ["ai"]}

    assert matches_config(config, {"title": "New AI model", "summary": ""})
    assert not matches_config(
        config,
        {"title": "Patch release available", "summary": ""},
    )


def test_html_listing_adapter_deduplicates_and_resolves_links() -> None:
    config = {
        "feed_url": "https://example.com/news",
        "homepage_url": "https://example.com/news",
        "link_pattern": r"^/news/[^/]+$",
    }
    html = """
    <main>
      <a href="/news/model-release">Jul 21, 2026 New model release</a>
      <a href="/news/model-release">Duplicate card</a>
      <a href="/company">Company page</a>
    </main>
    """

    entries = html_listing_entries(config, html)

    assert entries == [
        {
            "title": "Jul 21, 2026 New model release",
            "link": "https://example.com/news/model-release",
            "summary": "Jul 21, 2026 New model release",
            "published": "Jul 21, 2026",
        }
    ]


def test_source_filter_can_skip_quote_and_event_posts() -> None:
    config = {"exclude_title_prefixes": ["Quoting"], "exclude_tags": ["events"]}

    assert not matches_config(
        config, {"title": "Quoting an agent engineer", "summary": "Useful details"}
    )
    assert not matches_config(
        config,
        {"title": "Agent engineering meetup", "tags": [{"term": "events"}]},
    )
    assert matches_config(config, {"title": "Building reliable coding agents"})


def test_html_entry_date_parser_supports_listing_and_iso_dates() -> None:

    assert entry_datetime({"published": "Jul 21, 2026"}).isoformat() == "2026-07-21T00:00:00"
    assert (
        entry_datetime({"published": "2026-07-21T08:15:41-07:00"}).isoformat()
        == "2026-07-21T15:15:41"
    )
    assert entry_datetime({}) is None


def test_excerpt_is_derived_from_body_after_title() -> None:
    assert article_excerpt("Title", "Title\n\nBody   text here.") == "Body text here."
    assert article_excerpt("Title only", "Title only") == "Title only"
    long_excerpt = article_excerpt("T", "T\n\n" + "word " * 200)
    assert long_excerpt == article_excerpt("T", "T\n\n" + "word " * 300)
    assert len(long_excerpt) <= 422
    assert long_excerpt.endswith("...")
