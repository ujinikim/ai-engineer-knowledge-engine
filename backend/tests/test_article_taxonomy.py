import asyncio

import httpx
import pytest

from app.services.article_summary import MAIN_THEME_RESPONSE_FORMAT, ArticleSummaryService
from app.services.taxonomy import (
    classify_topic,
    classify_topic_with_method,
    infer_event_types,
    normalize_event_types,
)
from app.services.update_collector import UpdateCollectorService


def test_topic_classification_prefers_inference_signals() -> None:
    topic, tags = classify_topic(
        "Continuous batching improves inference throughput and KV cache efficiency.",
        "developer-tools",
    )

    assert topic == "ai-products-engineering-infrastructure"
    assert tags == []


def test_topic_classification_exposes_when_source_default_was_used() -> None:
    topic, method = classify_topic_with_method(
        "A short announcement without any category evidence.",
        "agentic-generative-ai",
    )

    assert topic == "agentic-generative-ai"
    assert method == "source-default"


def test_topic_classification_uses_evidence_before_source_default() -> None:
    topic, method = classify_topic_with_method(
        "A safety evaluation benchmark for model security.",
        "agentic-generative-ai",
    )

    assert topic == "safety-evaluation-governance"
    assert method == "deterministic-keyword"


def test_generic_search_does_not_imply_retrieval_infrastructure() -> None:
    topic, method = classify_topic_with_method(
        "A researcher uses an AI assistant to search genomes for antimicrobial molecules.",
        "agentic-generative-ai",
    )

    assert topic == "agentic-generative-ai"
    assert method == "source-default"


def test_specific_information_retrieval_language_is_still_detected() -> None:
    topic, method = classify_topic_with_method(
        "The study measures web retrieval quality for an LLM search engine.",
        "agentic-generative-ai",
    )

    assert topic == "data-search-retrieval"
    assert method == "deterministic-keyword"


def test_event_inference() -> None:
    assert infer_event_types("This API endpoint is deprecated and will sunset.") == ["alert"]


def test_event_normalization_keeps_at_most_one_v2_event() -> None:
    assert normalize_event_types(
        "transformers",
        ["release-update", "alert"],
    ) == ["release-update"]
    assert normalize_event_types("ollama", ["product-release"]) == []


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
        default_topic="ai-products-engineering-infrastructure",
        default_event_types=["release-update"],
    )

    assert article.primary_topic == "ai-products-engineering-infrastructure"
    assert article.display_headline == "vLLM adds prefill controls"
    assert "throttled prefill" in article.summary
    assert article.event_types == ["release-update"]


def test_generated_and_fallback_headlines_are_capped_at_90_characters() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    long_title = (
        "PyTorch 2.13 adds FlexAttention on Apple Silicon and introduces a new "
        "distributed communications backend"
    )
    fallback = service._fallback(
        title=long_title,
        raw_text=f"{long_title}\n\nThe release adds two documented runtime capabilities.",
        organization="PyTorch",
        tool="PyTorch",
        default_topic="training-fine-tuning",
        default_event_types=["library-release"],
    )
    validated = service._validated(
        {"display_headline": long_title},
        fallback,
        "official-release",
        title=long_title,
        raw_text=f"{long_title}\n\nThe release adds two documented runtime capabilities.",
    )

    assert len(fallback.display_headline) <= 90
    assert len(validated.display_headline) <= 90
    assert fallback.display_headline.endswith("...")
    assert validated.display_headline.endswith("...")


def test_validated_taxonomy_has_one_category_and_one_event() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    fallback = service._fallback(
        title="Agent tool-use research",
        raw_text="Agent tool-use research\n\nA research paper studies tool use by agents.",
        organization="Example",
        tool="Example",
        default_topic="agentic-generative-ai",
        default_event_types=["research"],
    )

    validated = service._validated(
        {
            "primary_topic": "agentic-generative-ai",
            "event_types": ["research", "analysis"],
        },
        fallback,
        "research-paper",
        title="Agent tool-use research",
        raw_text="A research paper studies tool use by agents.",
    )

    assert validated.primary_topic == "agentic-generative-ai"
    assert validated.event_types == ["research"]
    assert "topic_tags" not in validated.fields()


def test_event_default_is_only_used_when_content_has_no_event_signal() -> None:
    assert infer_event_types("This paper presents a new study.", ["release-update"]) == ["research"]
    assert infer_event_types("A concise source with no event language.", ["analysis"]) == ["analysis"]


def test_taxonomy_prompt_prioritizes_main_theme_over_product_mentions() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    prompt = service._taxonomy_prompt()
    event_prompt = service._event_prompt()

    assert "main theme" in prompt
    assert "merely the setting" in prompt
    assert "A product mention does not make an article a release" in event_prompt
    assert "detecting failures" in prompt
    assert "TPU or GPU kernel authoring" in prompt
    assert "recommendation, prediction, classification" in prompt
    assert "'get started' steps" in event_prompt


def test_main_theme_prompt_does_not_repeat_relevance_classification() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    prompt = service._main_theme_prompt()

    assert "main_theme" in prompt
    assert "decision was made upstream" in prompt
    assert "Do not classify whether the article belongs in the feed" in prompt
    assert "Core requires" not in prompt
    schema = MAIN_THEME_RESPONSE_FORMAT["json_schema"]["schema"]
    assert list(schema["properties"]) == ["main_theme"]


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
        detail_level=detail_level,
    )

    assert detail_level == "sparse"
    assert "Use near-extractive wording" in prompt
    assert "do not claim it improves general reliability" in prompt
    assert "Do not recommend an action" in prompt
    assert "The change applies to users" in prompt
    assert "Default topic" not in prompt
    assert "Default event" not in prompt


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


def test_source_filter_can_skip_quote_and_event_posts() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    config = {"exclude_title_prefixes": ["Quoting"], "exclude_tags": ["events"]}

    assert not collector._matches_config(
        config, {"title": "Quoting an agent engineer", "summary": "Useful details"}
    )
    assert not collector._matches_config(
        config,
        {"title": "Agent engineering meetup", "tags": [{"term": "events"}]},
    )
    assert collector._matches_config(config, {"title": "Building reliable coding agents"})


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

    assert hydrated["title"] == "Feed title"
    assert hydrated["published"] == "2026-07-20"
    assert collector._entry_datetime(hydrated).isoformat() == "2026-07-20T00:00:00"
    assert hydrated["_hydration_status"] == "full_article"
    assert hydrated["_extraction_status"] == "full_article"
    assert "Technical article body" in hydrated["content"][0]["value"]
    assert "Unrelated recommendation" not in hydrated["content"][0]["value"]


def test_listing_hydration_uses_article_title_but_feed_hydration_keeps_feed_title() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    html = "<html><body><h1>Site name</h1><article><h1>Article title</h1><p>Useful agent implementation details.</p></article></body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    entry = {"title": "Listing title", "link": "https://example.com/article"}

    async def hydrate(config: dict) -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await collector._hydrate_html_entry(client, config, entry)

    assert asyncio.run(hydrate({"source_kind": "html_listing", "content_selector": "article", "minimum_full_article_characters": 10}))["title"] == "Article title"
    assert asyncio.run(hydrate({"source_kind": "rss", "content_selector": "article", "minimum_full_article_characters": 10}))["title"] == "Listing title"

    generic_site_heading = "<html><body><h1>Site name</h1><div class='entryPage'><p>Useful agent implementation details.</p></div></body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=generic_site_heading, request=request))

    async def hydrate_without_article_heading() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await collector._hydrate_html_entry(client, {"source_kind": "atom", "content_selector": ".entryPage", "minimum_full_article_characters": 10}, entry)

    assert asyncio.run(hydrate_without_article_heading())["title"] == "Listing title"


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
    assert result["_full_article_fetch_http_status"] == 403
    assert result["_full_article_fetch_error_code"] == "http_forbidden"


def test_incomplete_article_without_excerpt_becomes_title_only() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)

    result = collector._full_article_fallback_entry(
        {"title": "Feed title", "link": "https://example.com/article"},
        ValueError("Full article extraction produced only 20 characters"),
    )

    assert result["_extraction_status"] == "title_only"
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
