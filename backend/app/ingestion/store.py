"""Database reads and writes for ingested articles and their chunks."""

import hashlib
import uuid

from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.ingestion.candidate import ArticleCandidate
from app.ingestion.urls import url_candidates


# Every column ingestion manages, with the value it takes when a write omits it.
FIELD_DEFAULTS: dict = {
    "ingestion_status": "published",
    "extraction_status": "source_entry",
    "relevance_tier": None,
    "relevance_reason": None,
    "relevance_policy_version": None,
    "primary_topic": None,
    "event_types": [],
    "display_headline": None,
    "summary": None,
    "why_it_matters": None,
    "key_points": [],
    "summary_generated_by": None,
}


def apply_fields(document: Document, fields: dict) -> None:
    """Write every managed column; a field absent from this write is reset."""
    for name, default in FIELD_DEFAULTS.items():
        value = fields.get(name)
        setattr(document, name, list(value or []) if isinstance(default, list) else value or default)


def current_fields(document: Document) -> dict:
    return {name: getattr(document, name) for name in FIELD_DEFAULTS}


def find_existing_article(db: Session, candidate: ArticleCandidate) -> Document | None:
    """Match by normalized URL, or by the same source, title, and content."""
    same_url = Document.url.in_(url_candidates(candidate.raw_url))
    same_content = and_(
        Document.source_name == candidate.source_slug,
        Document.title == candidate.title[:500],
        Document.content_hash == candidate.content_hash,
    )
    return db.scalar(select(Document).where(or_(same_url, same_content)).limit(1))


def save_article(
    db: Session,
    existing: Document | None,
    candidate: ArticleCandidate,
    fields: dict,
    *,
    update_url: bool = False,
) -> Document:
    """Create the article or overwrite the stored one; an update drops its old chunks."""
    if existing is None:
        document = Document(
            id=uuid.uuid4(),
            source_name=candidate.source_slug,
            title=candidate.title[:500],
            url=candidate.url,
            raw_text=candidate.raw_text,
            content_hash=candidate.content_hash,
            fetched_at=candidate.fetched_at,
            published_at=candidate.published_at,
        )
        apply_fields(document, fields)
        db.add(document)
        db.flush()
        return document

    existing.source_name = candidate.source_slug
    existing.title = candidate.title[:500]
    if update_url:
        existing.url = candidate.url
    existing.raw_text = candidate.raw_text
    existing.content_hash = candidate.content_hash
    existing.fetched_at = candidate.fetched_at
    existing.published_at = candidate.published_at
    apply_fields(existing, fields)
    delete_chunks(db, existing)
    return existing


def delete_chunks(db: Session, document: Document) -> None:
    db.execute(delete(Chunk).where(Chunk.document_id == document.id))


def add_chunks(db: Session, document: Document, chunks, embeddings) -> int:
    for chunk, embedding in zip(chunks, embeddings, strict=True):
        db.add(
            Chunk(
                id=uuid.uuid4(),
                document_id=document.id,
                chunk_index=chunk.index,
                content=chunk.content,
                embedding=embedding,
                token_count=chunk.token_count,
                content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
            )
        )
    return len(chunks)
