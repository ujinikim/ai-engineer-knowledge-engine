"""Remove the legacy documentation corpus.

Revision ID: 20260925_0005
Revises: 20260913_0004
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0005"
down_revision: str | None = "20260913_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # chunks.document_id has ON DELETE CASCADE.
    op.execute("DELETE FROM documents WHERE source_type = 'docs'")
    op.execute("ALTER TABLE documents ALTER COLUMN source_type SET DEFAULT 'release'")


def downgrade() -> None:
    # Deleted documentation cannot be reconstructed by a downgrade.
    op.execute("ALTER TABLE documents ALTER COLUMN source_type SET DEFAULT 'docs'")
