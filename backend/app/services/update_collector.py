import hashlib
import json
import re
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from time import struct_time
from urllib.parse import unquote, urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document, UpdateSource
from app.services.article_summary import ArticleSummaryService
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService


@dataclass(frozen=True)
class CollectionResult:
    sources_processed: int = 0
    updates_created: int = 0
    updates_changed: int = 0
    updates_unchanged: int = 0
    errors: int = 0


class UpdateCollectorService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.chunker = ChunkingService()
        self.embedder = EmbeddingService()
        self.summarizer = ArticleSummaryService()

    async def collect(self, source_configs: list[dict], max_items_per_source: int = 12) -> CollectionResult:
        counts = {
            "sources_processed": 0,
            "updates_created": 0,
            "updates_changed": 0,
            "updates_unchanged": 0,
            "errors": 0,
        }
        headers = {"User-Agent": "AI-Engineer-Update-Radar/0.1 (+local RAG project)"}

        async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=headers) as client:
            for config in source_configs:
                source = self._upsert_source(config)
                try:
                    response = await client.get(config["feed_url"])
                    response.raise_for_status()
                    entries = self._source_entries(config, response)
                    entries = await self._expand_source_entries(
                        client,
                        config,
                        entries,
                        max_items_per_source,
                    )

                    matched_items = 0
                    for entry in entries:
                        if config.get("source_kind") in {"html_listing", "nested_html_listing"}:
                            try:
                                entry = await self._hydrate_html_entry(client, config, entry)
                            except (httpx.HTTPError, ValueError) as error:
                                if (
                                    config.get("source_kind") != "nested_html_listing"
                                    or not entry.get("content")
                                ):
                                    raise
                                entry = {
                                    **entry,
                                    "_hydration_status": "parent_section_fallback",
                                    "_hydration_error": str(error)[:500],
                                }
                        if not self._matches_config(config, entry):
                            continue
                        if config.get("fetch_full_article") and config.get("source_kind") != "html_listing":
                            try:
                                entry = await self._hydrate_html_entry(client, config, entry)
                            except (httpx.HTTPError, ValueError) as error:
                                entry = {
                                    **entry,
                                    "_hydration_status": "failed",
                                    "_hydration_error": str(error)[:500],
                                }
                        status = self._upsert_entry(source, config, entry)
                        counts[f"updates_{status}"] += 1
                        matched_items += 1
                        if matched_items >= max_items_per_source:
                            break

                    source.last_collected_at = datetime.utcnow()
                    source.last_error = None
                    counts["sources_processed"] += 1
                    self.db.commit()
                except Exception as error:
                    self.db.rollback()
                    source = self._upsert_source(config)
                    source.last_collected_at = datetime.utcnow()
                    source.last_error = str(error)[:1000]
                    counts["errors"] += 1
                    self.db.commit()

        return CollectionResult(**counts)

    def _upsert_source(self, config: dict) -> UpdateSource:
        source = self.db.scalar(select(UpdateSource).where(UpdateSource.slug == config["slug"]))
        values = {
            "name": config["name"],
            "organization": config["organization"],
            "tool": config["tool"],
            "category": config.get("default_primary_topic", config["category"]),
            "source_kind": config.get("source_kind", "atom"),
            "feed_url": config["feed_url"],
            "homepage_url": config["homepage_url"],
            "credibility_weight": float(config.get("credibility_weight", 1.0)),
            "enabled": bool(config.get("enabled", True)),
            "source_metadata": {
                "source_type": config.get("source_type", "official-release"),
                "default_event_types": config.get("default_event_types", ["library-release"]),
                "include_terms": config.get("include_terms", []),
                "quality_tier": config.get("quality_tier", "primary"),
            },
        }
        if source:
            for field, value in values.items():
                setattr(source, field, value)
            return source

        source = UpdateSource(id=uuid.uuid4(), slug=config["slug"], **values)
        self.db.add(source)
        self.db.flush()
        return source

    def _upsert_entry(self, source: UpdateSource, config: dict, entry) -> str:
        url = str(entry.get("link") or entry.get("id") or "").strip()
        canonical_url = str(entry.get("_canonical_url") or url).strip()
        title = str(entry.get("title") or "Untitled update").strip()
        if not url:
            raise ValueError(f"Feed entry from {source.slug} has no URL")

        body_html = self._entry_html(entry)
        body_text = self._clean_html(body_html)
        raw_text = f"{title}\n\n{body_text}".strip()
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        published_at = self._entry_datetime(entry)
        now = datetime.utcnow()
        default_topic = config.get("default_primary_topic", config["category"])
        source_type = config.get("source_type", "official-release")
        default_event_types = config.get("default_event_types", ["library-release"])
        base_metadata = {
            "organization": config["organization"],
            "tool": config["tool"],
            "category": default_topic,
            "primary_topic": default_topic,
            "version": title[:120],
            "release_channel": self._release_channel(title),
            "excerpt": self._excerpt(body_text or title),
            "source_kind": config.get("source_kind", "atom"),
            "source_type": source_type,
            "credibility_weight": float(config.get("credibility_weight", 1.0)),
            "quality_tier": config.get("quality_tier", "primary"),
            "hydration_status": str(entry.get("_hydration_status") or "not_requested"),
        }
        if entry.get("_parent_url"):
            base_metadata["parent_url"] = str(entry["_parent_url"])
        if entry.get("_parent_title"):
            base_metadata["parent_title"] = str(entry["_parent_title"])
        if entry.get("_section_index") is not None:
            base_metadata["section_index"] = int(entry["_section_index"])
        hydration_error = str(entry.get("_hydration_error") or "").strip()
        if hydration_error:
            base_metadata["hydration_error"] = hydration_error

        document = self.db.scalar(select(Document).where(Document.url == url))
        if document and document.content_hash == content_hash:
            document.fetched_at = now
            document.published_at = published_at
            document.doc_metadata = {**document.doc_metadata, **base_metadata}
            return "unchanged"

        article = self.summarizer.summarize(
            title=title,
            raw_text=raw_text,
            organization=config["organization"],
            tool=config["tool"],
            source_type=source_type,
            default_topic=default_topic,
            default_event_types=default_event_types,
        )
        metadata = {**base_metadata, **article.metadata()}

        status = "changed" if document else "created"
        if document:
            document.source_name = source.slug
            document.source_type = "release"
            document.title = title[:500]
            document.raw_text = raw_text
            document.canonical_url = canonical_url
            document.content_hash = content_hash
            document.fetched_at = now
            document.published_at = published_at
            document.doc_metadata = metadata
            self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        else:
            document = Document(
                id=uuid.uuid4(),
                source_name=source.slug,
                source_type="release",
                title=title[:500],
                url=url,
                canonical_url=canonical_url,
                raw_text=raw_text,
                content_hash=content_hash,
                fetched_at=now,
                published_at=published_at,
                doc_metadata=metadata,
            )
            self.db.add(document)
            self.db.flush()

        chunks = self.chunker.chunk_text(raw_text, max_tokens=650, overlap_tokens=80)
        embeddings = self.embedder.embed_texts([chunk.content for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self.db.add(
                Chunk(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=embedding,
                    token_count=chunk.token_count,
                    content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                    chunk_metadata={"collection": "updates"},
                )
            )
        return status

    def _source_entries(self, config: dict, response: httpx.Response) -> list[dict]:
        if config.get("source_kind") in {"html_listing", "nested_html_listing"}:
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
            if not text and config.get("allow_empty_link_text"):
                text = path.rstrip("/").rsplit("/", 1)[-1].replace("-", " ").title()
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
        if config.get("sort_links_by_path_number"):
            entries.sort(
                key=lambda entry: self._last_path_number(str(entry["link"])),
                reverse=True,
            )
        return entries

    def _last_path_number(self, value: str) -> int:
        numbers = re.findall(r"\d+", urlparse(value).path)
        return int(numbers[-1]) if numbers else -1

    async def _expand_source_entries(
        self,
        client: httpx.AsyncClient,
        config: dict,
        entries: list[dict],
        max_items: int,
    ) -> list[dict]:
        if config.get("source_kind") == "nested_html_listing":
            entries = await self._nested_html_listing_entries(
                client,
                config,
                entries,
                max_items,
            )

        delimiter = str(config.get("section_delimiter") or "").strip()
        if not delimiter:
            return entries

        expanded: list[dict] = []
        for entry in entries:
            expanded.extend(self._split_entry_sections(config, entry, delimiter))
            if len(expanded) >= max_items:
                break
        return expanded[:max_items]

    async def _nested_html_listing_entries(
        self,
        client: httpx.AsyncClient,
        config: dict,
        parents: list[dict],
        max_items: int,
    ) -> list[dict]:
        selector = str(config["nested_entry_selector"])
        link_template = str(config["nested_link_template"])
        excluded_ids = {
            str(value).strip().lower()
            for value in config.get("nested_entry_exclude_ids", [])
            if str(value).strip()
        }
        entries: list[dict] = []
        seen_urls: set[str] = set()

        for parent in parents:
            response = await client.get(parent["link"])
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            parent_published = self._published_value(soup, soup) or parent.get("published")

            for element in soup.select(selector):
                entry_id = str(element.get("id") or "").strip()
                title = " ".join(element.get_text(" ", strip=True).split())
                if not entry_id or not title or entry_id.lower() in excluded_ids:
                    continue

                normalized_id = (
                    unicodedata.normalize("NFKD", unquote(entry_id))
                    .encode("ascii", "ignore")
                    .decode("ascii")
                )
                path = link_template.format(id=normalized_id)
                url = urljoin(str(response.url), path)
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                section_nodes = [element]
                for sibling in element.next_siblings:
                    if (
                        getattr(sibling, "name", None) == element.name
                        and sibling.get("id")
                    ):
                        break
                    if getattr(sibling, "name", None):
                        section_nodes.append(sibling)
                entries.append(
                    {
                        "title": title[:500],
                        "link": url,
                        "summary": title,
                        "content": [
                            {"value": "".join(str(node) for node in section_nodes)}
                        ],
                        "published": parent_published,
                        "_parent_url": str(response.url),
                        "_parent_title": str(parent.get("title") or ""),
                    }
                )
                if len(entries) >= max_items:
                    return entries
        return entries

    def _split_entry_sections(
        self,
        config: dict,
        entry: dict,
        delimiter: str,
    ) -> list[dict]:
        soup = BeautifulSoup(self._entry_html(entry), "html.parser")
        groups: list[list] = [[]]
        for element in soup.children:
            if not getattr(element, "name", None):
                continue
            if " ".join(element.get_text(" ", strip=True).split()) == delimiter:
                groups.append([])
            else:
                groups[-1].append(element)

        title_selector = str(config.get("section_title_selector") or "strong")
        excluded_prefixes = tuple(
            str(value).strip().lower()
            for value in config.get("section_exclude_title_prefixes", [])
            if str(value).strip()
        )
        parent_url = str(entry.get("link") or entry.get("id") or "").strip()
        parent_title = str(entry.get("title") or "").strip()
        sections: list[dict] = []

        for group in groups:
            title_node = None
            title_position = 0
            for index, element in enumerate(group):
                title_node = (
                    element
                    if element.name == title_selector
                    else element.select_one(title_selector)
                )
                if title_node:
                    title_position = index
                    break
            if not title_node:
                continue

            title = " ".join(title_node.get_text(" ", strip=True).split()).rstrip(":")
            if not title or any(title.lower().startswith(prefix) for prefix in excluded_prefixes):
                continue

            section_number = len(sections) + 1
            slug = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:80]
            section_url = f"{parent_url}#story-{section_number}-{slug or 'section'}"
            section_html = "".join(str(element) for element in group[title_position:])
            sections.append(
                {
                    **entry,
                    "title": title[:500],
                    "link": section_url,
                    "content": [{"value": section_html}],
                    "_canonical_url": parent_url,
                    "_parent_url": parent_url,
                    "_parent_title": parent_title,
                    "_section_index": section_number,
                }
            )
        return sections

    async def _hydrate_html_entry(
        self,
        client: httpx.AsyncClient,
        config: dict,
        entry: dict,
    ) -> dict:
        response = await client.get(entry["link"])
        response.raise_for_status()
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

        heading = content.select_one("h1") or soup.select_one("h1")
        if heading and config.get("title_direct_text"):
            title = " ".join(
                str(value).strip()
                for value in heading.find_all(string=True, recursive=False)
                if str(value).strip()
            )
        else:
            title = " ".join(heading.get_text(" ", strip=True).split()) if heading else entry["title"]
        title_prefix = str(config.get("title_prefix") or "").strip()
        if title_prefix and not title.lower().startswith(title_prefix.lower()):
            title = f"{title_prefix} {title}"

        article_published = self._published_value(soup, content)
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
            "_hydration_error": "",
        }

    def _matches_config(self, config: dict, entry) -> bool:
        include_terms = [str(term).lower() for term in config.get("include_terms", [])]
        exclude_terms = [str(term).lower() for term in config.get("exclude_terms", [])]
        if not include_terms and not exclude_terms:
            return True
        value = " ".join(
            [
                str(entry.get("title") or ""),
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

    def _excerpt(self, text: str, limit: int = 420) -> str:
        compact = " ".join(text.split())
        if len(compact) <= limit:
            return compact
        return compact[: limit - 1].rstrip() + "..."

    def _release_channel(self, title: str) -> str:
        prerelease_pattern = r"(?:^|[.\-_])(rc|dev|alpha|beta|preview|canary)\d*(?:$|[.\-_])"
        return "prerelease" if re.search(prerelease_pattern, title.lower()) else "stable"
