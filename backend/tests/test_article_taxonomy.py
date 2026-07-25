import asyncio

import httpx
import pytest

from app.services.article_summary import ArticleSummaryService
from app.services.taxonomy import classify_topic, infer_event_types, infer_maturity
from app.services.update_collector import UpdateCollectorService


def test_topic_classification_prefers_inference_signals() -> None:
    topic, tags = classify_topic(
        "Continuous batching improves inference throughput and KV cache efficiency.",
        "developer-tools",
    )

    assert topic == "inference-serving"
    assert isinstance(tags, list)


def test_event_and_maturity_inference() -> None:
    assert "deprecation" in infer_event_types("This API endpoint is deprecated and will sunset.")
    assert infer_maturity("v2.0.0-rc.2") == "release-candidate"
    assert infer_maturity("v2.0.0-rc1: fix download handling") == "release-candidate"
    assert infer_maturity("Feature now in general availability") == "general-availability"


def test_deterministic_summary_keeps_source_facts() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    article = service._fallback(
        title="vLLM adds prefill controls",
        raw_text=(
            "vLLM adds prefill controls\n\n"
            "The release adds throttled prefill scheduling. It also improves KV cache handling."
        ),
        organization="vLLM Project",
        tool="vLLM",
        default_topic="inference-serving",
        default_event_types=["library-release"],
    )

    assert article.primary_topic == "inference-serving"
    assert article.display_headline == "vLLM adds prefill controls"
    assert "throttled prefill" in article.summary
    assert article.event_types[0] == "library-release"


def test_feed_filtering_uses_title_and_body() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    config = {"include_terms": ["agent", "inference"]}

    assert collector._matches_config(config, {"title": "New inference runtime", "summary": ""})
    assert not collector._matches_config(config, {"title": "Cloud billing update", "summary": ""})


def test_feed_filtering_uses_term_boundaries() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    config = {"include_terms": ["ai"]}

    assert collector._matches_config(config, {"title": "New AI model", "summary": ""})
    assert not collector._matches_config(
        config,
        {"title": "Patch release available", "summary": ""},
    )


def test_html_listing_adapter_deduplicates_and_resolves_links() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
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

    entries = collector._html_listing_entries(config, html)

    assert entries == [
        {
            "title": "Jul 21, 2026 New model release",
            "link": "https://example.com/news/model-release",
            "summary": "Jul 21, 2026 New model release",
            "published": "Jul 21, 2026",
        }
    ]


def test_html_listing_can_name_and_sort_image_only_links() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    config = {
        "feed_url": "https://example.com/the-batch",
        "homepage_url": "https://example.com/the-batch",
        "link_pattern": r"^/the-batch/issue-\d+$",
        "allow_empty_link_text": True,
        "sort_links_by_path_number": True,
    }
    html = """
    <a href="/the-batch/issue-100"><img alt="Issue cover"></a>
    <a href="/the-batch/issue-25"><img alt="Popular old issue"></a>
    <a href="/the-batch/issue-101"><img alt="Issue cover"></a>
    """

    entries = collector._html_listing_entries(config, html)

    assert [entry["title"] for entry in entries] == [
        "Issue 101",
        "Issue 100",
        "Issue 25",
    ]


def test_nested_html_listing_discovers_story_pages() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    issue_html = """
    <html><body><main>
      <h1 id="news">News</h1>
      <h1 id="first-story">First story</h1>
      <p>First story details.</p>
      <h1 id="second-story%E2%80%99s-update">Second story</h1>
      <p>Second story details.</p>
    </main></body></html>
    """
    transport = httpx.MockTransport(
        lambda request: httpx.Response(200, text=issue_html, request=request)
    )
    config = {
        "nested_entry_selector": "main h1[id]",
        "nested_entry_exclude_ids": ["news"],
        "nested_link_template": "/the-batch/{id}",
    }
    parents = [
        {
            "title": "Issue 10",
            "link": "https://example.com/the-batch/issue-10",
            "published": "2026-07-24",
        }
    ]

    async def expand() -> list[dict]:
        async with httpx.AsyncClient(transport=transport) as client:
            return await collector._nested_html_listing_entries(
                client,
                config,
                parents,
                max_items=10,
            )

    entries = asyncio.run(expand())

    assert [entry["title"] for entry in entries] == ["First story", "Second story"]
    assert entries[0]["link"] == "https://example.com/the-batch/first-story"
    assert entries[1]["link"] == "https://example.com/the-batch/second-storys-update"
    assert entries[0]["_parent_url"] == "https://example.com/the-batch/issue-10"
    assert "First story details" in entries[0]["content"][0]["value"]
    assert "Second story details" not in entries[0]["content"][0]["value"]


def test_newsletter_sections_are_split_and_fiction_is_excluded() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    config = {
        "section_title_selector": "strong",
        "section_exclude_title_prefixes": ["Tech Tales"],
    }
    entry = {
        "title": "Newsletter 10",
        "link": "https://example.com/newsletter-10",
        "content": [
            {
                "value": """
                <p>Newsletter introduction.</p>
                <p><strong>First research story:</strong><br>Details about the result.</p>
                <p>More evidence.</p>
                <p>***</p>
                <p><strong>Second policy story:</strong><br>Policy details.</p>
                <p>***</p>
                <p><strong>Tech Tales:</strong></p>
                <p>A fictional story.</p>
                """
            }
        ],
    }

    sections = collector._split_entry_sections(config, entry, "***")

    assert [section["title"] for section in sections] == [
        "First research story",
        "Second policy story",
    ]
    assert sections[0]["_canonical_url"] == entry["link"]
    assert sections[0]["link"].startswith(f"{entry['link']}#story-1-")
    assert "Newsletter introduction" not in sections[0]["content"][0]["value"]
    assert "fictional" not in " ".join(
        section["content"][0]["value"] for section in sections
    )


def test_html_entry_date_parser_supports_listing_and_iso_dates() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)

    assert collector._entry_datetime({"published": "Jul 21, 2026"}).isoformat() == "2026-07-21T00:00:00"
    assert (
        collector._entry_datetime({"published": "2026-07-21T08:15:41-07:00"}).isoformat()
        == "2026-07-21T15:15:41"
    )
    assert collector._entry_datetime({}) is None


def test_full_article_hydration_uses_configured_content_and_json_ld_date() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {"@type": "Article", "datePublished": "2026-07-20"}
        </script>
      </head>
      <body>
        <h1>Ray on TPU <span>Technical subtitle</span></h1>
        <div class="article-body">
          <time datetime="June 2025">Archive date</time>
          <p>Technical article body with enough useful detail for extraction.</p>
          <p>Additional implementation guidance.</p>
          <div class="related">Unrelated recommendation</div>
        </div>
      </body>
    </html>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    config = {
        "content_selector": ".article-body",
        "content_remove_selectors": [".related"],
        "minimum_full_article_characters": 50,
        "title_direct_text": True,
    }
    entry = {
        "title": "Feed title",
        "link": "https://example.com/article",
        "published_parsed": (2026, 7, 22, 0, 0, 0, 0, 0, 0),
    }

    async def hydrate() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await collector._hydrate_html_entry(client, config, entry)

    hydrated = asyncio.run(hydrate())

    assert hydrated["title"] == "Ray on TPU"
    assert hydrated["published"] == "2026-07-20"
    assert collector._entry_datetime(hydrated).isoformat() == "2026-07-20T00:00:00"
    assert hydrated["_hydration_status"] == "full_article"
    assert "Technical article body" in hydrated["content"][0]["value"]
    assert "Unrelated recommendation" not in hydrated["content"][0]["value"]


def test_full_article_hydration_rejects_challenge_page() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    html = "<html><body><main>Enable JavaScript and cookies to continue</main></body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    entry = {"title": "Blocked article", "link": "https://example.com/article"}

    async def hydrate() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await collector._hydrate_html_entry(
                client,
                {"content_selector": "main", "minimum_full_article_characters": 10},
                entry,
            )

    with pytest.raises(ValueError, match="Full article extraction"):
        asyncio.run(hydrate())


def test_full_article_hydration_preserves_feed_date_when_page_has_none() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    html = """
    <html><body><main>
      <h1>Article without a page date</h1>
      <p>This full article body has enough technical detail to pass content validation.</p>
      <p>It intentionally has no time element, publication metadata, or JSON-LD date.</p>
    </main></body></html>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    entry = {
        "title": "Feed title",
        "link": "https://example.com/article",
        "published_parsed": (2026, 7, 18, 12, 30, 0, 0, 0, 0),
    }

    async def hydrate() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await collector._hydrate_html_entry(
                client,
                {"content_selector": "main", "minimum_full_article_characters": 50},
                entry,
            )

    hydrated = asyncio.run(hydrate())

    assert collector._entry_datetime(hydrated).isoformat() == "2026-07-18T12:30:00"
