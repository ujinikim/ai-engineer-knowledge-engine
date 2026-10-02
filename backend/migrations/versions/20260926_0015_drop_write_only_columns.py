"""Drop columns that were written but never read.

`relevance_status` repeated what the tier already says (a failed classification
leaves the tier empty; corrections and failures are logged). `taxonomy_policy_version`
was never compared with anything.

Revision ID: 20260926_0015
Revises: 20260925_0014
Create Date: 2026-09-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "20260926_0015"
down_revision: str | None = "20260925_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_constraint("ck_documents_relevance_status", "documents", type_="check")
    op.drop_column("documents", "relevance_status")
    op.drop_column("documents", "taxonomy_policy_version")


def downgrade() -> None:
    op.add_column("documents", sa.Column("taxonomy_policy_version", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("relevance_status", sa.String(32), nullable=True))
    # Approximate: the original status is gone; an empty tier is how failures were stored.
    op.execute(
        "UPDATE documents SET relevance_status = "
        "CASE WHEN relevance_tier IS NULL THEN 'failed' ELSE 'classified' END"
    )
    op.create_check_constraint(
        "ck_documents_relevance_status",
        "documents",
        "relevance_status IS NULL OR relevance_status IN "
        "('classified', 'corrected_unsupported_core', 'failed')",
    )
