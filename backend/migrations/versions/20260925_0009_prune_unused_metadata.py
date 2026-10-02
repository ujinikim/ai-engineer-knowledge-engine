"""Prune unused article metadata and unpopulated chunk provenance columns.

Revision ID: 20260925_0009
Revises: 20260925_0008
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0009"
down_revision: str | None = "20260925_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


UNUSED_KEYS = (
    "version",
    "release_channel",
    "topic_tags",
    "entity_tags",
    "category",
    "default_feed_eligible",
    "default_feed_exclusion_reason",
    "rag_eligible",
    "quarantine_reason",
)


def upgrade() -> None:
    keys = ", ".join(f"'{key}'" for key in UNUSED_KEYS)
    op.execute(f"UPDATE documents SET doc_metadata = doc_metadata - ARRAY[{keys}]")
    op.drop_column("chunks", "embedding_model")
    op.drop_column("chunks", "chunking_version")
    op.drop_column("chunks", "chunk_metadata")


def downgrade() -> None:
    op.execute("ALTER TABLE chunks ADD COLUMN embedding_model VARCHAR(120)")
    op.execute("ALTER TABLE chunks ADD COLUMN chunking_version VARCHAR(80)")
    op.execute(
        "ALTER TABLE chunks ADD COLUMN chunk_metadata JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    # Discarded metadata was derived, empty, or unused; do not recreate stale values.
