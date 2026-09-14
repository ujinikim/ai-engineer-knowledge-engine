import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
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
        Index("documents_source_type_idx", "source_type"),
        Index("documents_published_at_idx", literal_column("published_at DESC")),
        Index("documents_ingestion_status_idx", "ingestion_status"),
        Index("documents_relevance_tier_idx", "relevance_tier"),
        Index("documents_primary_topic_idx", "primary_topic"),
        Index("documents_event_type_idx", "event_type"),
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
        CheckConstraint(
            "event_type IS NULL OR event_type IN "
            "('release-update', 'research', 'guide', 'analysis', 'alert')",
            name="ck_documents_event_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(120))
    source_type: Mapped[str] = mapped_column(String(80), default="docs", server_default="docs")
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text, unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
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
    event_type: Mapped[str | None] = mapped_column(String(32))
    summary: Mapped[str | None] = mapped_column(Text)
    processing_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class UpdateSource(Base):
    __tablename__ = "update_sources"
    __table_args__ = (
        Index("update_sources_slug_idx", "slug"),
        Index("update_sources_tool_idx", "tool"),
        Index("update_sources_category_idx", "category"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str] = mapped_column(String(200))
    tool: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(120))
    source_kind: Mapped[str] = mapped_column(String(80), default="atom", server_default="atom")
    feed_url: Mapped[str] = mapped_column(Text, unique=True)
    homepage_url: Mapped[str] = mapped_column(Text)
    credibility_weight: Mapped[float] = mapped_column(Float, default=1.0, server_default="1.0")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )


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
    embedding_model: Mapped[str | None] = mapped_column(String(120))
    chunking_version: Mapped[str | None] = mapped_column(String(80))
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, server_default=func.now()
    )

    document: Mapped[Document] = relationship(back_populates="chunks")
