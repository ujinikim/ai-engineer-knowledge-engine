"""Remove source-config copies, derivable values, and audit-only metadata.

Source attributes are read from update_sources.yml by source_name, the excerpt is
derived from raw_text, and classifier audit details are logged instead of stored.

Revision ID: 20260925_0013
Revises: 20260925_0012
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0013"
down_revision: str | None = "20260925_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REMOVED_KEYS = (
    "organization",
    "tool",
    "source_type",
    "credibility_weight",
    "excerpt",
    "hydration_status",
    "ingestion_failure_codes",
    "relevance_generated_by",
    "relevance_agent_focus",
    "relevance_agent_evidence_quote",
    "taxonomy_generated_by",
)


def upgrade() -> None:
    keys = ", ".join(f"'{key}'" for key in REMOVED_KEYS)
    op.execute(f"UPDATE documents SET doc_metadata = doc_metadata - ARRAY[{keys}]")


def downgrade() -> None:
    # Source attributes and excerpts are derivable; audit details were not retained.
    pass
