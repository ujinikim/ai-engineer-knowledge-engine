"""Hide old failed relevance decisions and remove unused document columns.

Revision ID: 20260925_0007
Revises: 20260925_0006
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0007"
down_revision: str | None = "20260925_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Old fail-open decisions must not remain in search, even before retrying them.
    op.execute(
        """
        DELETE FROM chunks
        WHERE document_id IN (
          SELECT id FROM documents
          WHERE doc_metadata->>'relevance_classification_status' = 'fail_open'
        )
        """
    )
    op.drop_index("documents_event_type_idx", table_name="documents")
    op.drop_column("documents", "event_type")
    op.drop_column("documents", "summary")
    op.drop_column("documents", "processing_metadata")
    op.execute(
        """
        UPDATE documents
        SET relevance_tier = NULL,
            doc_metadata = jsonb_set(
              jsonb_set(doc_metadata, '{relevance_tier}', 'null'::jsonb),
              '{default_feed_eligible}', 'false'::jsonb
            ) || jsonb_build_object(
              'rag_eligible', false,
              'default_feed_exclusion_reason', 'relevance_unclassified'
            )
        WHERE doc_metadata->>'relevance_classification_status' = 'fail_open'
        """
    )


def downgrade() -> None:
    op.execute("ALTER TABLE documents ADD COLUMN event_type VARCHAR(32)")
    op.execute("ALTER TABLE documents ADD COLUMN summary TEXT")
    op.execute(
        "ALTER TABLE documents ADD COLUMN processing_metadata "
        "JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.create_index("documents_event_type_idx", "documents", ["event_type"])
    op.create_check_constraint(
        "ck_documents_event_type",
        "documents",
        "event_type IS NULL OR event_type IN "
        "('release-update', 'research', 'guide', 'analysis', 'alert')",
    )
    # Deleted chunks and failed classifications cannot be reconstructed safely.
