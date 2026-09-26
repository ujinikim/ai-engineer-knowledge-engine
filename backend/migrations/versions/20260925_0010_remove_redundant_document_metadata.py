"""Remove redundant and unused document metadata keys.

Revision ID: 20260925_0010
Revises: 20260925_0009
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0010"
down_revision: str | None = "20260925_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REMOVED_KEYS = (
    "ingestion_status",
    "evidence_level",
    "relevance_tier",
    "relevance_reason",
    "primary_topic",
    "ingestion_warning_codes",
    "taxonomy_main_theme",
    "extraction_metadata_version",
)


def upgrade() -> None:
    keys = ", ".join(f"'{key}'" for key in REMOVED_KEYS)
    op.execute(f"UPDATE documents SET doc_metadata = doc_metadata - ARRAY[{keys}]")


def downgrade() -> None:
    # Typed columns still contain the canonical values; restore only those mirrors.
    op.execute(
        """
        UPDATE documents
        SET doc_metadata = doc_metadata || jsonb_build_object(
            'ingestion_status', ingestion_status,
            'evidence_level', evidence_level,
            'relevance_tier', relevance_tier,
            'relevance_reason', relevance_reason,
            'primary_topic', primary_topic
        )
        """
    )
