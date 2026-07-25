import uuid
from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_name: Mapped[str] = mapped_column(String(120), index=True)
    source_type: Mapped[str] = mapped_column(String(80), default="docs")
    title: Mapped[str] = mapped_column(String(500))
    url: Mapped[str] = mapped_column(Text, unique=True)
    canonical_url: Mapped[str | None] = mapped_column(Text)
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)

    chunks: Mapped[list["Chunk"]] = relationship(back_populates="document")


class UpdateSource(Base):
    __tablename__ = "update_sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200))
    organization: Mapped[str] = mapped_column(String(200))
    tool: Mapped[str] = mapped_column(String(200), index=True)
    category: Mapped[str] = mapped_column(String(120), index=True)
    source_kind: Mapped[str] = mapped_column(String(80), default="atom")
    feed_url: Mapped[str] = mapped_column(Text, unique=True)
    homepage_url: Mapped[str] = mapped_column(Text)
    credibility_weight: Mapped[float] = mapped_column(Float, default=1.0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime)
    last_error: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)


class Chunk(Base):
    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("documents.id"), index=True)
    chunk_index: Mapped[int] = mapped_column(Integer)
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    token_count: Mapped[int] = mapped_column(Integer)
    content_hash: Mapped[str] = mapped_column(String(128), index=True)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped[Document] = relationship(back_populates="chunks")
