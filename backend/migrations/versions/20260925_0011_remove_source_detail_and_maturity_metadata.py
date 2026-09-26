"""Remove derived source and lifecycle metadata from documents.

Revision ID: 20260925_0011
Revises: 20260925_0010
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0011"
down_revision: str | None = "20260925_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REMOVED_KEYS = (
    "quality_tier",
    "source_kind",
    "content_detail",
    "summary_input_source",
    "maturity",
)


def upgrade() -> None:
    keys = ", ".join(f"'{key}'" for key in REMOVED_KEYS)
    op.execute(f"UPDATE documents SET doc_metadata = doc_metadata - ARRAY[{keys}]")


def downgrade() -> None:
    # These values come from source configuration or derivation rules and are not
    # reconstructed during downgrade.
    pass
