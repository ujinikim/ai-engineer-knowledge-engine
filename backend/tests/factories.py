"""Builders for stored articles and chunks, using the real column names."""

import hashlib
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

DEFAULT_FETCHED_AT = datetime(2026, 7, 22, 12, 0, 0)


def make_article(**overrides) -> SimpleNamespace:
    """A published, full-article, core-relevance article; override any column.

    The content hash follows `raw_text` and `published_at` is a day before `fetched_at`
    unless given, so an article is internally consistent by default.
    """
    title = overrides.get("title", "Example engineering update")
    raw_text = overrides.get("raw_text", f"{title}\n\nExample body text.")
    fetched_at = overrides.get("fetched_at", DEFAULT_FETCHED_AT)
    columns = {
        "id": uuid4(),
        "source_name": "example-source",
        "title": title,
        "url": "https://example.com/update",
        "raw_text": raw_text,
        "content_hash": hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        "fetched_at": fetched_at,
        "published_at": fetched_at - timedelta(days=1),
        "ingestion_status": "published",
        "extraction_status": "full_article",
        "relevance_tier": "core",
        "relevance_reason": None,
        "relevance_policy_version": None,
        "primary_topic": "ai-products-engineering-infrastructure",
        "event_types": ["release-update"],
        "display_headline": None,
        "summary": None,
        "why_it_matters": None,
        "key_points": [],
        "summary_generated_by": None,
    }
    unknown = set(overrides) - set(columns)
    assert not unknown, f"not article columns: {sorted(unknown)}"
    return SimpleNamespace(**{**columns, **overrides})


def make_chunk(content: str, index: int = 0) -> SimpleNamespace:
    return SimpleNamespace(
        chunk_index=index,
        content=content,
        embedding=[0.1, 0.2],
        token_count=max(1, len(content.split())),
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )
