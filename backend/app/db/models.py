import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    literal_column,
    text,
)
from sqlalchemy.sql import func
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.services.taxonomy import EVENT_TYPES, PRIMARY_TOPICS


def _sql_list(values) -> str:
    return ", ".join(f"'{value}'" for value in values)


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("documents_source_name_idx", "source_name"),
        Index("documents_content_hash_idx", "content_hash"),
        Index("documents_published_at_idx", literal_column("published_at DESC")),
        Index("documents_primary_topic_idx", "primary_topic"),
        Index(
            "documents_feed_scope_idx",
            "ingestion_status",
            "relevance_tier",
            "source_name",
            literal_column("published_at DESC"),
        ),
        CheckConstraint(
            "ingestion_status IN ('published', 'quarantined')",
            name="ck_documents_ingestion_status",
        ),
        CheckConstraint(
            "extraction_status IN ('full_article', 'source_entry', 'feed_excerpt_only', 'title_only')",
            name="ck_documents_extraction_status",
        ),
        CheckConstraint(
            "relevance_status IS NULL OR relevance_status IN "
            "('classified', 'corrected_unsupported_core', 'failed')",
            name="ck_documents_relevance_status",
        ),
        CheckConstraint(
            f"event_types <@ ARRAY[{_sql_list(EVENT_TYPES)}]::varchar[]",
            name="ck_documents_event_types",
        ),
        CheckConstraint(
            "relevance_tier IS NULL OR relevance_tier IN ('core', 'contextual', 'excluded')",
            name="ck_documents_relevance_tier",
        ),
        CheckConstraint(
            f"primary_topic IS NULL OR primary_topic IN ({_sql_list(PRIMARY_TOPICS)})",
            name="ck_documents_primary_topic",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(120))
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text, unique=True)
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    ingestion_status: Mapped[str] = mapped_column(
        String(32), default="published", server_default="published"
    )
    extraction_status: Mapped[str] = mapped_column(
        String(32), default="source_entry", server_default="source_entry"
    )
    relevance_tier: Mapped[str | None] = mapped_column(String(32))
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    relevance_status: Mapped[str | None] = mapped_column(String(32))
    relevance_policy_version: Mapped[str | None] = mapped_column(String(64))
    primary_topic: Mapped[str | None] = mapped_column(String(80))
    event_types: Mapped[list[str]] = mapped_column(
        ARRAY(String(32)), default=list, server_default=text("'{}'::varchar[]")
    )
    taxonomy_policy_version: Mapped[str | None] = mapped_column(String(64))
    display_headline: Mapped[str | None] = mapped_column(Text)
    summary: Mapped[str | None] = mapped_column(Text)
    why_it_matters: Mapped[str | None] = mapped_column(Text)
    key_points: Mapped[list[str]] = mapped_column(
        ARRAY(Text), default=list, server_default=text("'{}'::text[]")
    )
    summary_generated_by: Mapped[str | None] = mapped_column(String(120))

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class CollectionSourceRun(Base):
    __tablename__ = "collection_source_runs"
    __table_args__ = (
        UniqueConstraint("run_id", "source_slug", name="uq_collection_source_runs_run_source"),
        Index("collection_source_runs_source_finished_idx", "source_slug", "finished_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(String(64))
    source_slug: Mapped[str] = mapped_column(String(120))
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime] = mapped_column(DateTime)
    status: Mapped[str] = mapped_column(String(32))
    matched_items: Mapped[int] = mapped_column(Integer, default=0)
    updates_created: Mapped[int] = mapped_column(Integer, default=0)
    updates_changed: Mapped[int] = mapped_column(Integer, default=0)
    updates_unchanged: Mapped[int] = mapped_column(Integer, default=0)
    updates_quarantined: Mapped[int] = mapped_column(Integer, default=0)
    chunks_written: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text)


class Chunk(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "chunk_index"),
        Index("chunks_document_id_idx", "document_id"),
        Index("chunks_content_hash_idx", "content_hash"),
        Index(
            "chunks_embedding_hnsw_idx",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index(
            "chunks_content_fts_idx",
            func.to_tsvector(literal_column("'english'"), literal_column("content")),
            postgresql_using="gin",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id", ondelete="CASCADE"))
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    token_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(128))

    document: Mapped[Document] = relationship(back_populates="chunks")
