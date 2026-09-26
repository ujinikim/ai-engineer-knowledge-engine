"""Feed and article extraction helpers used by the update collector."""

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from time import struct_time
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.structured_logging import get_logger, log_event


logger = get_logger("collector.fetch")

FETCH_ATTEMPTS = 3
RETRY_BASE_DELAY_SECONDS = 1.0
MAX_RETRY_DELAY_SECONDS = 10.0
RETRYABLE_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504})


class SourceExtractionMixin:
    async def _get_with_retries(self, client: httpx.AsyncClient, url: str) -> httpx.Response:
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

            delay = self._retry_delay(attempt, retry_after)
            log_event(
                logger,
                "fetch_retry",
                level=logging.WARNING,
                run_id=getattr(self, "run_id", None),
                url=self._log_safe_url(url),
                attempt=attempt,
                http_status=http_status,
                exception_type=exception_type,
                delay_ms=int(delay * 1000),
            )
            await asyncio.sleep(delay)
        raise AssertionError("unreachable")

    @staticmethod
    def _retry_delay(attempt: int, retry_after: str | None) -> float:
        delay = RETRY_BASE_DELAY_SECONDS * 2 ** (attempt - 1)
        if retry_after and retry_after.strip().isdigit():
            delay = float(retry_after.strip())
        return min(delay, MAX_RETRY_DELAY_SECONDS)

    def _source_entries(self, config: dict, response: httpx.Response) -> list[dict]:
        if config.get("source_kind") == "html_listing":
            return self._html_listing_entries(config, response.text)

        feed = feedparser.parse(response.content)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Could not parse feed: {feed.bozo_exception}")
        return list(feed.entries)

    def _html_listing_entries(self, config: dict, html: str) -> list[dict]:
        pattern = re.compile(config["link_pattern"])
        base_url = config.get("homepage_url") or config["feed_url"]
        entries: list[dict] = []
        seen_urls: set[str] = set()
        soup = BeautifulSoup(html, "html.parser")

        for anchor in soup.select(config.get("link_selector", "a[href]")):
            href = str(anchor.get("href") or "").strip()
            absolute_url = urljoin(base_url, href)
            path = urlparse(absolute_url).path
            if not href or not pattern.search(path) or absolute_url in seen_urls:
                continue

            text = " ".join(anchor.get_text(" ", strip=True).split())
            if not text:
                continue
            seen_urls.add(absolute_url)
            entries.append(
                {
                    "title": text[:500],
                    "link": absolute_url,
                    "summary": text,
                    "published": self._date_from_text(text),
                }
            )
        return entries

    async def _hydrate_html_entry(
        self,
        client: httpx.AsyncClient,
        config: dict,
        entry: dict,
    ) -> dict:
        response = await self._get_with_retries(client, entry["link"])
        soup = BeautifulSoup(response.text, "html.parser")
        content = soup.select_one(config.get("content_selector", "main")) or soup.body or soup
        remove_selectors = ", ".join(
            [
                "script",
                "style",
                "noscript",
                "nav",
                "footer",
                "form",
                "svg",
                *config.get("content_remove_selectors", []),
            ]
        )
        for element in content.select(remove_selectors):
            element.decompose()

        content_text = " ".join(content.get_text(" ", strip=True).split())
        minimum_characters = int(config.get("minimum_full_article_characters", 500))
        blocked_markers = ("enable javascript and cookies", "challenge-error-text")
        if len(content_text) < minimum_characters or any(
            marker in content_text.lower() for marker in blocked_markers
        ):
            raise ValueError(
                f"Full article extraction produced only {len(content_text)} characters"
            )

        heading = content.select_one("h1")
        if config.get("source_kind") == "html_listing" and heading is None:
            heading = soup.select_one("h1")
        title = (
            " ".join(heading.get_text(" ", strip=True).split())
            if heading and config.get("source_kind") == "html_listing"
            else str(entry.get("title") or "").strip()
        )
        if not title and heading:
            title = " ".join(heading.get_text(" ", strip=True).split())
        title_prefix = str(config.get("title_prefix") or "").strip()
        if title_prefix and not title.lower().startswith(title_prefix.lower()):
            title = f"{title_prefix} {title}"

        article_published = self._published_value(soup, content)
        date_element = soup.select_one(config["date_selector"]) if config.get("date_selector") else None
        if not article_published and date_element:
            article_published = self._date_from_text(date_element.get_text(" ", strip=True))
        published = article_published or entry.get("published")
        if not published:
            published = self._date_from_text(content.get_text(" ", strip=True)[:500])

        return {
            **entry,
            "title": title[:500],
            "link": str(response.url),
            "content": [{"value": str(content)}],
            "published": published,
            "published_parsed": None if article_published else entry.get("published_parsed"),
            "updated_parsed": None if article_published else entry.get("updated_parsed"),
            "_hydration_status": "full_article",
            "_extraction_status": "full_article",
        }

    def _full_article_fallback_entry(
        self,
        entry: dict,
        error: Exception,
    ) -> dict:
        feed_text = self._clean_html(self._entry_html(entry)).strip()
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
            "_hydration_status": "failed",
            "_extraction_status": extraction_status,
            "_full_article_fetch_http_status": http_status,
            "_full_article_fetch_error_code": error_code,
        }

    def _matches_config(self, config: dict, entry) -> bool:
        title = str(entry.get("title") or "").strip().lower()
        if any(
            title.startswith(str(prefix).strip().lower())
            for prefix in config.get("exclude_title_prefixes", [])
        ):
            return False
        excluded_tags = {str(tag).strip().lower() for tag in config.get("exclude_tags", [])}
        if any(
            str(tag.get("term") or "").strip().lower() in excluded_tags
            for tag in entry.get("tags", [])
        ):
            return False
        include_terms = [str(term).lower() for term in config.get("include_terms", [])]
        exclude_terms = [str(term).lower() for term in config.get("exclude_terms", [])]
        if not include_terms and not exclude_terms:
            return True
        value = " ".join(
            [
                title,
                self._clean_html(self._entry_html(entry)),
            ]
        ).lower()
        if exclude_terms and any(self._contains_term(value, term) for term in exclude_terms):
            return False
        return not include_terms or any(self._contains_term(value, term) for term in include_terms)

    def _contains_term(self, value: str, term: str) -> bool:
        escaped = re.escape(term.strip()).replace(r"\ ", r"\s+")
        if not escaped:
            return False
        return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", value))

    def _entry_html(self, entry) -> str:
        content = entry.get("content") or []
        if content and isinstance(content, list):
            return str(content[0].get("value") or "")
        return str(entry.get("summary") or entry.get("description") or "")

    def _clean_html(self, value: str) -> str:
        soup = BeautifulSoup(value, "html.parser")
        return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())

    def _entry_datetime(self, entry) -> datetime | None:
        parsed: struct_time | None = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed:
            return datetime(*parsed[:6], tzinfo=timezone.utc).replace(tzinfo=None)
        value = str(entry.get("published") or entry.get("updated") or "").strip()
        if value:
            normalized = value.replace("Z", "+00:00")
            try:
                parsed_date = datetime.fromisoformat(normalized)
                if parsed_date.tzinfo:
                    parsed_date = parsed_date.astimezone(timezone.utc).replace(tzinfo=None)
                return parsed_date
            except ValueError:
                for date_format in ("%b %d, %Y", "%B %d, %Y", "%Y-%m-%d"):
                    try:
                        return datetime.strptime(value, date_format)
                    except ValueError:
                        continue
        return None

    def _published_value(self, soup: BeautifulSoup, content) -> str:
        meta_selectors = (
            'meta[property="article:published_time"]',
            'meta[name="datePublished"]',
            'meta[itemprop="datePublished"]',
            'meta[name="date"]',
        )
        for selector in meta_selectors:
            element = soup.select_one(selector)
            if element and element.get("content"):
                return str(element["content"])

        for element in soup.select('script[type="application/ld+json"]'):
            try:
                payload = json.loads(element.string or element.get_text())
            except (TypeError, ValueError, json.JSONDecodeError):
                continue
            published = self._json_ld_value(payload, "datePublished")
            if published:
                return published

        time_element = content.select_one("time[datetime]") or soup.select_one("time[datetime]")
        if time_element and time_element.get("datetime"):
            return str(time_element["datetime"])
        return ""

    def _json_ld_value(self, value, key: str) -> str:
        if isinstance(value, dict):
            candidate = value.get(key)
            if candidate:
                return str(candidate)
            for nested in value.values():
                result = self._json_ld_value(nested, key)
                if result:
                    return result
        elif isinstance(value, list):
            for nested in value:
                result = self._json_ld_value(nested, key)
                if result:
                    return result
        return ""

    def _date_from_text(self, value: str) -> str:
        match = re.search(
            r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}\b",
            value,
            re.IGNORECASE,
        )
        return match.group(0) if match else ""

    @staticmethod
    def _log_safe_url(value) -> str | None:
        if not value:
            return None
        parsed = urlparse(str(value))
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"

    def _excerpt(self, text: str, limit: int = 420) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "..."
