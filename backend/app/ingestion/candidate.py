"""Prepare a feed entry for ingestion: text, fingerprint, dates, and provisional labels."""

import hashlib
from dataclasses import dataclass
from datetime import datetime

from app.ingestion.content_detail import classify_content_detail
from app.ingestion.parsing import clean_html, compact_excerpt, entry_datetime, entry_html
from app.ingestion.store import normalize_url
from app.ingestion.taxonomy import (
    classify_topic_with_method,
    infer_event_types,
    normalize_event_types,
)


@dataclass(frozen=True)
class ArticleCandidate:
    source_slug: str
    raw_url: str
    url: str
    title: str
    raw_text: str
    content_hash: str
    published_at: datetime | None
    fetched_at: datetime
    hydration_status: str
    extraction_status: str
    content_detail: str
    excerpt: str
    default_topic: str
    default_event_types: list[str]
    # Deterministic labels used until, or instead of, model classification.
    provisional_topic: str
    provisional_events: list[str]


def prepare_candidate(source_slug: str, config: dict, entry, *, now: datetime) -> ArticleCandidate:
    raw_url = str(entry.get("link") or entry.get("id") or "").strip()
    url = normalize_url(raw_url)
    if not url:
        raise ValueError(f"Feed entry from {source_slug} has no URL")
    title = str(entry.get("title") or "Untitled update").strip()

    body_text = clean_html(entry_html(entry))
    raw_text = f"{title}\n\n{body_text}".strip()
    hydration_status = str(entry.get("_hydration_status") or "not_requested")
    extraction_status = str(
        entry.get("_extraction_status")
        or {
            "full_article": "full_article",
            "failed": "feed_excerpt_only" if body_text else "title_only",
        }.get(hydration_status, "source_entry")
    )
    default_topic = config.get("default_primary_topic", config["category"])
    default_event_types = config.get("default_event_types", ["analysis"])
    provisional_topic, _ = classify_topic_with_method(f"{title}\n{title}\n{raw_text}", default_topic)

    return ArticleCandidate(
        source_slug=source_slug,
        raw_url=raw_url,
        url=url,
        title=title,
        raw_text=raw_text,
        content_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        published_at=entry_datetime(entry),
        fetched_at=now,
        hydration_status=hydration_status,
        extraction_status=extraction_status,
        content_detail=classify_content_detail(title, raw_text),
        excerpt=compact_excerpt(body_text or title),
        default_topic=default_topic,
        default_event_types=default_event_types,
        provisional_topic=provisional_topic,
        provisional_events=normalize_event_types(
            source_slug, infer_event_types(raw_text, default_event_types)
        ),
    )
