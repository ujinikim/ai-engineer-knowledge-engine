import asyncio

import httpx
import pytest

from app.ingestion import fetch
from app.ingestion.fetch import failed_fetch_entry, fetch_full_article, get_with_retries
from app.ingestion.parsing import entry_datetime


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(fetch.asyncio, "sleep", fake_sleep)
    return delays


def run_fetch(handler) -> httpx.Response:

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await get_with_retries(client, "https://example.com/feed?token=x")

    return asyncio.run(run())


def test_full_article_hydration_uses_configured_content_and_json_ld_date() -> None:
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
          <footer>Unrelated recommendation</footer>
        </div>
      </body>
    </html>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    config = {
        "content_selector": ".article-body",
        "minimum_full_article_characters": 50,
    }
    entry = {
        "title": "Feed title",
        "link": "https://example.com/article",
        "published_parsed": (2026, 7, 22, 0, 0, 0, 0, 0, 0),
    }

    async def hydrate() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_full_article(client, config, entry)

    hydrated = asyncio.run(hydrate())

    assert hydrated["title"] == "Feed title"
    assert hydrated["published"] == "2026-07-20"
    assert entry_datetime(hydrated).isoformat() == "2026-07-20T00:00:00"
    assert hydrated["_extraction_status"] == "full_article"
    assert "Technical article body" in hydrated["content"][0]["value"]
    assert "Unrelated recommendation" not in hydrated["content"][0]["value"]


def test_listing_hydration_uses_article_title_but_feed_hydration_keeps_feed_title() -> None:
    html = "<html><body><h1>Site name</h1><article><h1>Article title</h1><p>Useful agent implementation details.</p></article></body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    entry = {"title": "Listing title", "link": "https://example.com/article"}

    async def hydrate(config: dict) -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_full_article(client, config, entry)

    assert asyncio.run(hydrate({"source_kind": "html_listing", "content_selector": "article", "minimum_full_article_characters": 10}))["title"] == "Article title"
    assert asyncio.run(hydrate({"source_kind": "rss", "content_selector": "article", "minimum_full_article_characters": 10}))["title"] == "Listing title"

    generic_site_heading = "<html><body><h1>Site name</h1><div class='entryPage'><p>Useful agent implementation details.</p></div></body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=generic_site_heading, request=request))

    async def hydrate_without_article_heading() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_full_article(client, {"source_kind": "atom", "content_selector": ".entryPage", "minimum_full_article_characters": 10}, entry)

    assert asyncio.run(hydrate_without_article_heading())["title"] == "Listing title"


def test_forbidden_article_fetch_becomes_structured_feed_excerpt_fallback() -> None:
    request = httpx.Request("GET", "https://example.com/article")
    response = httpx.Response(403, request=request)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        response.raise_for_status()

    result = failed_fetch_entry(
        {
            "title": "Feed title",
            "link": str(request.url),
            "summary": "A short but usable feed excerpt.",
        },
        caught.value,
    )

    assert result["_extraction_status"] == "feed_excerpt_only"
    assert result["_full_article_fetch_http_status"] == 403
    assert result["_full_article_fetch_error_code"] == "http_forbidden"


def test_incomplete_article_without_excerpt_becomes_title_only() -> None:

    result = failed_fetch_entry(
        {"title": "Feed title", "link": "https://example.com/article"},
        ValueError("Full article extraction produced only 20 characters"),
    )

    assert result["_extraction_status"] == "title_only"
    assert result["_full_article_fetch_http_status"] is None
    assert result["_full_article_fetch_error_code"] == "content_incomplete"


def test_full_article_hydration_rejects_challenge_page() -> None:
    html = "<html><body><main>Enable JavaScript and cookies to continue</main></body></html>"
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    entry = {"title": "Blocked article", "link": "https://example.com/article"}

    async def hydrate() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_full_article(
                client,
                {"content_selector": "main", "minimum_full_article_characters": 10},
                entry,
            )

    with pytest.raises(ValueError, match="Full article extraction"):
        asyncio.run(hydrate())


def test_full_article_hydration_preserves_feed_date_when_page_has_none() -> None:
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
            return await fetch_full_article(
                client,
                {"content_selector": "main", "minimum_full_article_characters": 50},
                entry,
            )

    hydrated = asyncio.run(hydrate())

    assert entry_datetime(hydrated).isoformat() == "2026-07-18T12:30:00"


def test_transient_status_is_retried_until_success(no_retry_sleep, caplog) -> None:
    statuses = iter([503, 429, 200])
    calls = []

    def handler(request):
        calls.append(request)
        status = next(statuses)
        headers = {"Retry-After": "3"} if status == 429 else {}
        return httpx.Response(status, headers=headers, request=request)

    assert run_fetch(handler).status_code == 200
    assert len(calls) == 3
    assert no_retry_sleep == [1.0, 3.0]
    retries = [r.structured_fields for r in caplog.records if getattr(r, "event", None) == "fetch_retry"]
    assert [r["http_status"] for r in retries] == [503, 429]
    assert all(r["url"] == "https://example.com/feed" for r in retries)


def test_permanent_status_is_not_retried(no_retry_sleep) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(404, request=request)

    with pytest.raises(httpx.HTTPStatusError):
        run_fetch(handler)
    assert len(calls) == 1
    assert no_retry_sleep == []


def test_transport_errors_raise_after_final_attempt(no_retry_sleep) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(httpx.ConnectTimeout):
        run_fetch(handler)
    assert len(calls) == fetch.FETCH_ATTEMPTS
    assert no_retry_sleep == [1.0, 2.0]


def test_retry_delay_is_capped() -> None:
    assert fetch.retry_delay(1, "120") == (
        fetch.MAX_RETRY_DELAY_SECONDS
    )


def test_date_selector_supplies_date_outside_article_content() -> None:
    html = """
    <html><body><main>
      <section><p class="Hero__date">May 25, 2026</p></section>
      <article><h1>Featured post</h1><p>Agent containment details that are long enough.</p></article>
    </main></body></html>
    """
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=html, request=request))
    config = {
        "source_kind": "html_listing",
        "content_selector": "main article",
        "date_selector": "[class*='__date']",
        "minimum_full_article_characters": 10,
    }

    async def hydrate() -> dict:
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_full_article(
                client, config, {"title": "Featured post", "link": "https://example.com/post"}
            )

    hydrated = asyncio.run(hydrate())
    assert entry_datetime(hydrated).isoformat() == "2026-05-25T00:00:00"
