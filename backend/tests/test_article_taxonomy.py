import asyncio

import httpx
import pytest

from app.services.article_summary import ArticleSummaryService
from app.services.taxonomy import (
    classify_topic,
    infer_event_types,
    infer_maturity,
    normalize_event_types,
)
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
    assert infer_maturity("v0.26.0rc1") == "release-candidate"
    assert infer_maturity("V1.2.0_RC.3") == "release-candidate"
    assert infer_maturity("Feature now in general availability") == "general-availability"


def test_maturity_does_not_treat_rc_inside_words_as_release_candidate() -> None:
    for title in ("Research update", "Architecture notes", "Source release", "PyTorch"):
        assert infer_maturity(title) == "stable"


def test_research_events_infer_research_maturity_without_release_event() -> None:
    assert (
        infer_maturity(
            "Web retrieval study",
            event_types=["research-result", "engineering-analysis"],
        )
        == "research"
    )
    assert (
        infer_maturity(
            "Benchmark library v1.0",
            event_types=["library-release", "benchmark-result"],
        )
        == "stable"
    )


def test_versioned_library_event_normalization() -> None:
    assert normalize_event_types(
        "transformers",
        ["product-release", "model-launch", "breaking-change"],
    ) == ["library-release", "breaking-change"]
    assert normalize_event_types("ollama", ["product-release"]) == ["product-release"]


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


def test_sparse_source_prompt_prohibits_speculative_benefits() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    raw_text = "v1.18.3\n\nFix query errors when using shard keys while resharding."

    detail_level = service._source_detail_level("v1.18.3", raw_text)
    prompt = service._user_prompt(
        title="v1.18.3",
        raw_text=raw_text,
        organization="Qdrant",
        tool="Qdrant",
        source_type="official-release",
        default_topic="retrieval-data",
        default_event_types=["library-release"],
        detail_level=detail_level,
    )

    assert detail_level == "sparse"
    assert "Use near-extractive wording" in prompt
    assert "do not claim it improves general reliability" in prompt
    assert "Do not recommend an action" in prompt
    assert "The change applies to users" in prompt
    assert "Default event types: ['library-release']" in prompt


def test_detailed_source_does_not_receive_sparse_instructions() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    body = "\n".join(
        [
            "The release adds a new cache implementation for production inference workloads.",
            "Production tests reduced median latency by 25 percent across three deployments.",
            "Operators can enable the cache through the existing runtime configuration.",
            "The source provides benchmark methodology and compatibility details for adopters.",
            "Compatibility is documented for existing deployments using the prior cache configuration.",
            "The release notes also identify rollout steps and the supported runtime versions.",
        ]
    )
    raw_text = f"Runtime cache release\n\n{body}"

    detail_level = service._source_detail_level("Runtime cache release", raw_text)
    prompt = service._user_prompt(
        title="Runtime cache release",
        raw_text=raw_text,
        organization="Example",
        tool="Runtime",
        source_type="official-engineering-blog",
        default_topic="inference-serving",
        default_event_types=["engineering-analysis"],
        detail_level=detail_level,
    )

    assert detail_level == "detailed"
    assert "Sparse-source instructions" not in prompt
    assert "Production tests reduced median latency" in prompt


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
    assert hydrated["_extraction_status"] == "full_article"
    assert hydrated["_summary_input_source"] == "full_article"
    assert hydrated["_full_article_fetch_http_status"] == 200
    assert hydrated["_full_article_fetch_error_code"] is None
    assert hydrated["_full_article_fetch_attempted_at"]
    assert "Technical article body" in hydrated["content"][0]["value"]
    assert "Unrelated recommendation" not in hydrated["content"][0]["value"]


def test_forbidden_article_fetch_becomes_structured_feed_excerpt_fallback() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    request = httpx.Request("GET", "https://example.com/article")
    response = httpx.Response(403, request=request)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        response.raise_for_status()

    result = collector._full_article_fallback_entry(
        {
            "title": "Feed title",
            "link": str(request.url),
            "summary": "A short but usable feed excerpt.",
        },
        caught.value,
    )

    assert result["_hydration_status"] == "failed"
    assert result["_extraction_status"] == "feed_excerpt_only"
    assert result["_summary_input_source"] == "feed_excerpt"
    assert result["_full_article_fetch_http_status"] == 403
    assert result["_full_article_fetch_error_code"] == "http_forbidden"
    assert result["_full_article_fetch_attempted_at"]


def test_incomplete_article_without_excerpt_becomes_title_only() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)

    result = collector._full_article_fallback_entry(
        {"title": "Feed title", "link": "https://example.com/article"},
        ValueError("Full article extraction produced only 20 characters"),
    )

    assert result["_extraction_status"] == "title_only"
    assert result["_summary_input_source"] == "title"
    assert result["_full_article_fetch_http_status"] is None
    assert result["_full_article_fetch_error_code"] == "content_incomplete"


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
