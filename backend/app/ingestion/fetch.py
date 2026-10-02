"""HTTP access for ingestion: retried GETs and full-article fetches."""

import asyncio
import logging

import httpx

from app.core.structured_logging import get_logger, log_event, safe_url
from app.ingestion.parsing import clean_html, entry_html, parse_article_page
from app.sources import SourceConfig


logger = get_logger("collector.fetch")

FETCH_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 10.0
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


async def get_with_retries(
    client: httpx.AsyncClient, url: str, *, run_id: str | None = None
) -> httpx.Response:
    """GET a URL, retrying timeouts, connection errors, and transient HTTP statuses."""
    for attempt in range(1, FETCH_ATTEMPTS + 1):
        http_status = None
        exception_type = None
        retry_after = None
        try:
            response = await client.get(url)
        except httpx.TransportError as error:
            if attempt == FETCH_ATTEMPTS:
                raise
            exception_type = type(error).__name__
        else:
            if response.status_code not in RETRYABLE_STATUS_CODES or attempt == FETCH_ATTEMPTS:
                response.raise_for_status()
                return response
            http_status = response.status_code
            retry_after = response.headers.get("Retry-After")

        delay = retry_delay(attempt, retry_after)
        log_event(
            logger,
            "fetch_retry",
            level=logging.WARNING,
            run_id=run_id,
            url=safe_url(url),
            attempt=attempt,
            http_status=http_status,
            exception_type=exception_type,
            delay_ms=int(delay * 1000),
        )
        await asyncio.sleep(delay)
    raise AssertionError("unreachable")


def retry_delay(attempt: int, retry_after: str | None) -> float:
    delay = RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1)
    if retry_after and retry_after.strip().isdigit():
        delay = float(retry_after.strip())
    return min(delay, MAX_RETRY_DELAY_SECONDS)


async def fetch_full_article(
    client: httpx.AsyncClient, config: SourceConfig, entry: dict, *, run_id: str | None = None
) -> dict:
    """Fetch an entry's article page and replace its content with the full text."""
    response = await get_with_retries(client, entry["link"], run_id=run_id)
    return parse_article_page(config, entry, response.text, str(response.url))


def failed_fetch_entry(entry: dict, error: Exception) -> dict:
    """Keep the feed's own text when the full-article fetch fails, with an error code."""
    feed_text = clean_html(entry_html(entry)).strip()
    extraction_status = "feed_excerpt_only" if feed_text else "title_only"

    http_status = None
    if isinstance(error, httpx.HTTPStatusError):
        http_status = error.response.status_code

    if http_status == 403:
        error_code = "http_forbidden"
    elif http_status == 404:
        error_code = "http_not_found"
    elif http_status is not None:
        error_code = "http_error"
    elif isinstance(error, httpx.RequestError):
        error_code = "network_error"
    elif isinstance(error, ValueError):
        error_code = "content_incomplete"
    else:
        error_code = "unknown_error"

    return {
        **entry,
        "_extraction_status": extraction_status,
        "_full_article_fetch_http_status": http_status,
        "_full_article_fetch_error_code": error_code,
    }
