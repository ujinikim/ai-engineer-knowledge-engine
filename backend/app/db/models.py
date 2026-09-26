import uuid
from datetime import datetime
from typing import Any

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        Index("documents_source_name_idx", "source_name"),
        Index("documents_content_hash_idx", "content_hash"),
        Index("documents_published_at_idx", literal_column("published_at DESC")),
        Index("documents_ingestion_status_idx", "ingestion_status"),
        Index("documents_relevance_tier_idx", "relevance_tier"),
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
            "evidence_level IN ('full_article', 'source_entry', 'official_feed_excerpt')",
            name="ck_documents_evidence_level",
        ),
        CheckConstraint(
            "relevance_tier IS NULL OR relevance_tier IN ('core', 'contextual', 'excluded')",
            name="ck_documents_relevance_tier",
        ),
        CheckConstraint(
            "primary_topic IS NULL OR primary_topic IN "
            "('agentic-generative-ai', 'machine-learning-classical-ai', "
            "'vision-speech-robotics', 'data-search-retrieval', "
            "'ai-products-engineering-infrastructure', 'safety-evaluation-governance')",
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
    evidence_level: Mapped[str] = mapped_column(
        String(32), default="source_entry", server_default="source_entry"
    )
    relevance_tier: Mapped[str | None] = mapped_column(String(32))
    relevance_reason: Mapped[str | None] = mapped_column(Text)
    primary_topic: Mapped[str | None] = mapped_column(String(80))
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

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
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
