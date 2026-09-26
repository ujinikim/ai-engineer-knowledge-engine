"""Remove article-only source type and duplicate canonical URL columns.

Revision ID: 20260925_0008
Revises: 20260925_0007
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0008"
down_revision: str | None = "20260925_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_index("documents_source_type_idx", table_name="documents")
    op.drop_column("documents", "source_type")
    op.drop_column("documents", "canonical_url")


def downgrade() -> None:
    op.execute(
        "ALTER TABLE documents ADD COLUMN source_type "
        "VARCHAR(80) NOT NULL DEFAULT 'release'"
    )
    op.execute("ALTER TABLE documents ADD COLUMN canonical_url TEXT")
    op.execute("UPDATE documents SET canonical_url = url")
    op.create_index("documents_source_type_idx", "documents", ["source_type"])
