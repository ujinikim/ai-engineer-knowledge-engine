import asyncio

import httpx
import pytest

from app.services import source_extraction
from app.services.update_collector import UpdateCollectorService


@pytest.fixture(autouse=True)
def no_retry_sleep(monkeypatch):
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    monkeypatch.setattr(source_extraction.asyncio, "sleep", fake_sleep)
    return delays


def fetch(handler) -> httpx.Response:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)

    async def run() -> httpx.Response:
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await collector._get_with_retries(client, "https://example.com/feed?token=x")

    return asyncio.run(run())


def test_transient_status_is_retried_until_success(no_retry_sleep, caplog) -> None:
    statuses = iter([503, 429, 200])
    calls = []

    def handler(request):
        calls.append(request)
        status = next(statuses)
        headers = {"Retry-After": "3"} if status == 429 else {}
        return httpx.Response(status, headers=headers, request=request)

    assert fetch(handler).status_code == 200
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
        fetch(handler)
    assert len(calls) == 1
    assert no_retry_sleep == []


def test_transport_errors_raise_after_final_attempt(no_retry_sleep) -> None:
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ConnectTimeout("timed out", request=request)

    with pytest.raises(httpx.ConnectTimeout):
        fetch(handler)
    assert len(calls) == source_extraction.FETCH_ATTEMPTS
    assert no_retry_sleep == [1.0, 2.0]


def test_retry_delay_is_capped() -> None:
    assert source_extraction.SourceExtractionMixin._retry_delay(1, "120") == (
        source_extraction.MAX_RETRY_DELAY_SECONDS
    )


def test_date_selector_supplies_date_outside_article_content() -> None:
    collector = UpdateCollectorService.__new__(UpdateCollectorService)
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
            return await collector._hydrate_html_entry(
                client, config, {"title": "Featured post", "link": "https://example.com/post"}
            )

    hydrated = asyncio.run(hydrate())
    assert collector._entry_datetime(hydrated).isoformat() == "2026-05-25T00:00:00"
