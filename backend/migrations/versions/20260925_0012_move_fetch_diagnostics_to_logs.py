"""Remove per-attempt fetch diagnostics from document metadata.

Fetch attempts, retries, and retained-refresh outcomes are now collector log events.

Revision ID: 20260925_0012
Revises: 20260925_0011
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0012"
down_revision: str | None = "20260925_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REMOVED_KEYS = (
    "hydration_error",
    "full_article_fetch_attempted_at",
    "full_article_fetch_http_status",
    "full_article_fetch_error_code",
    "last_ingestion_attempt_status",
    "last_ingestion_failure_codes",
    "last_ingestion_warning_codes",
    "last_ingestion_evidence_level",
    "last_ingestion_attempted_at",
    "last_relevance_attempt_status",
    "last_relevance_attempted_at",
)


def upgrade() -> None:
    keys = ", ".join(f"'{key}'" for key in REMOVED_KEYS)
    op.execute(f"UPDATE documents SET doc_metadata = doc_metadata - ARRAY[{keys}]")


def downgrade() -> None:
    # Attempt diagnostics are historical log data and are not reconstructed.
    pass
