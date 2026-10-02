"""Turn feeds, listing pages, and article pages into entries. No network access."""

import json
import re
from datetime import datetime, timezone
from time import struct_time
from urllib.parse import urljoin, urlparse

import feedparser
from bs4 import BeautifulSoup

from app.sources import SourceConfig


BLOCKED_PAGE_MARKERS = ("enable javascript and cookies", "challenge-error-text")
ALWAYS_REMOVED_SELECTORS = ("script", "style", "noscript", "nav", "footer", "form", "svg")


def source_entries(config: SourceConfig, text: str, content: bytes) -> list[dict]:
    """Entries from a source's feed or HTML listing page."""
    if config.get("source_kind") == "html_listing":
        return html_listing_entries(config, text)

    feed = feedparser.parse(content)
    if feed.bozo and not feed.entries:
        raise ValueError(f"Could not parse feed: {feed.bozo_exception}")
    return list(feed.entries)


def html_listing_entries(config: SourceConfig, html: str) -> list[dict]:
    pattern = re.compile(config["link_pattern"])
    base_url = config.get("homepage_url") or config["feed_url"]
    entries: list[dict] = []
    seen_urls: set[str] = set()
    soup = BeautifulSoup(html, "html.parser")

    for anchor in soup.select("a[href]"):
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
                "published": date_from_text(text),
            }
        )
    return entries


def parse_article_page(config: SourceConfig, entry: dict, html: str, final_url: str) -> dict:
    """Replace an entry's content with the full article page, or raise ValueError."""
    soup = BeautifulSoup(html, "html.parser")
    content = soup.select_one(config.get("content_selector", "main")) or soup.body or soup
    for element in content.select(", ".join(ALWAYS_REMOVED_SELECTORS)):
        element.decompose()

    content_text = " ".join(content.get_text(" ", strip=True).split())
    minimum_characters = int(config.get("minimum_full_article_characters", 500))
    if len(content_text) < minimum_characters or any(
        marker in content_text.lower() for marker in BLOCKED_PAGE_MARKERS
    ):
        raise ValueError(f"Full article extraction produced only {len(content_text)} characters")

    article_published = _page_published_value(soup, content)
    date_element = soup.select_one(config["date_selector"]) if config.get("date_selector") else None
    if not article_published and date_element:
        article_published = date_from_text(date_element.get_text(" ", strip=True))
    published = article_published or entry.get("published")
    if not published:
        published = date_from_text(content.get_text(" ", strip=True)[:500])

    return {
        **entry,
        "title": _article_title(config, entry, soup, content)[:500],
        "link": final_url,
        "content": [{"value": str(content)}],
        "published": published,
        "published_parsed": None if article_published else entry.get("published_parsed"),
        "updated_parsed": None if article_published else entry.get("updated_parsed"),
        "_extraction_status": "full_article",
    }


def _article_title(config: SourceConfig, entry: dict, soup: BeautifulSoup, content) -> str:
    # Listing pages link with short anchor text, so they take the article's heading;
    # feeds already carry the publisher's title.
    is_listing = config.get("source_kind") == "html_listing"
    heading = content.select_one("h1")
    if is_listing and heading is None:
        heading = soup.select_one("h1")
    title = (
        " ".join(heading.get_text(" ", strip=True).split())
        if heading and is_listing
        else str(entry.get("title") or "").strip()
    )
    if not title and heading:
        title = " ".join(heading.get_text(" ", strip=True).split())
    return title


def matches_config(config: SourceConfig, entry) -> bool:
    """Apply a source's title-prefix, tag, and include-term filters."""
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
    if not include_terms:
        return True
    value = " ".join([title, clean_html(entry_html(entry))]).lower()
    return any(contains_term(value, term) for term in include_terms)


def contains_term(value: str, term: str) -> bool:
    escaped = re.escape(term.strip()).replace(r"\ ", r"\s+")
    if not escaped:
        return False
    return bool(re.search(rf"(?<![a-z0-9]){escaped}(?![a-z0-9])", value))


def entry_html(entry) -> str:
    content = entry.get("content") or []
    if content and isinstance(content, list):
        return str(content[0].get("value") or "")
    return str(entry.get("summary") or entry.get("description") or "")


def clean_html(value: str) -> str:
    soup = BeautifulSoup(value, "html.parser")
    return "\n".join(line.strip() for line in soup.get_text("\n").splitlines() if line.strip())


def entry_datetime(entry) -> datetime | None:
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


def _page_published_value(soup: BeautifulSoup, content) -> str:
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
        published = _json_ld_value(payload, "datePublished")
        if published:
            return published

    time_element = content.select_one("time[datetime]") or soup.select_one("time[datetime]")
    if time_element and time_element.get("datetime"):
        return str(time_element["datetime"])
    return ""


def _json_ld_value(value, key: str) -> str:
    if isinstance(value, dict):
        candidate = value.get(key)
        if candidate:
            return str(candidate)
        for nested in value.values():
            result = _json_ld_value(nested, key)
            if result:
                return result
    elif isinstance(value, list):
        for nested in value:
            result = _json_ld_value(nested, key)
            if result:
                return result
    return ""


def date_from_text(value: str) -> str:
    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}, \d{4}\b",
        value,
        re.IGNORECASE,
    )
    return match.group(0) if match else ""
