"""Move the article card, taxonomy, and pipeline versions into typed columns.

Replaces doc_metadata with columns, merges evidence_level into extraction_status
(the published feed-excerpt case is derived from ingestion_status), and removes
redundant indexes and the unread chunks.created_at column.

Revision ID: 20260925_0014
Revises: 20260925_0013
Create Date: 2026-09-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260925_0014"
down_revision: str | None = "20260925_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


EVENT_TYPES = ("release-update", "research", "guide", "analysis", "alert")
EVENT_TYPE_LIST = ", ".join(f"'{value}'" for value in EVENT_TYPES)


def upgrade() -> None:
    op.add_column("documents", sa.Column("extraction_status", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("relevance_status", sa.String(32), nullable=True))
    op.add_column("documents", sa.Column("relevance_policy_version", sa.String(64), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "event_types",
            postgresql.ARRAY(sa.String(32)),
            nullable=False,
            server_default=sa.text("'{}'::varchar[]"),
        ),
    )
    op.add_column("documents", sa.Column("taxonomy_policy_version", sa.String(64), nullable=True))
    op.add_column("documents", sa.Column("display_headline", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("summary", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("why_it_matters", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "key_points",
            postgresql.ARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
    )
    op.add_column("documents", sa.Column("summary_generated_by", sa.String(120), nullable=True))

    op.execute(
        f"""
        UPDATE documents SET
          extraction_status = COALESCE(
            doc_metadata->>'extraction_status',
            CASE evidence_level
              WHEN 'full_article' THEN 'full_article'
              WHEN 'official_feed_excerpt' THEN 'feed_excerpt_only'
              ELSE 'source_entry'
            END
          ),
          relevance_status = CASE doc_metadata->>'relevance_classification_status'
            WHEN 'fail_open' THEN 'failed'
            ELSE doc_metadata->>'relevance_classification_status'
          END,
          relevance_policy_version = doc_metadata->>'relevance_policy_version',
          event_types = ARRAY(
            SELECT value FROM jsonb_array_elements_text(
              CASE WHEN jsonb_typeof(doc_metadata->'event_types') = 'array'
                THEN doc_metadata->'event_types' ELSE '[]'::jsonb END
            ) AS value
            WHERE value IN ({EVENT_TYPE_LIST})
          )::varchar[],
          taxonomy_policy_version = doc_metadata->>'taxonomy_policy_version',
          display_headline = doc_metadata->>'display_headline',
          summary = doc_metadata->>'summary',
          why_it_matters = doc_metadata->>'why_it_matters',
          key_points = ARRAY(
            SELECT jsonb_array_elements_text(
              CASE WHEN jsonb_typeof(doc_metadata->'key_points') = 'array'
                THEN doc_metadata->'key_points' ELSE '[]'::jsonb END
            )
          ),
          summary_generated_by = doc_metadata->>'summary_generated_by'
        """
    )
    op.alter_column(
        "documents",
        "extraction_status",
        nullable=False,
        server_default="source_entry",
    )
    op.create_check_constraint(
        "ck_documents_extraction_status",
        "documents",
        "extraction_status IN ('full_article', 'source_entry', 'feed_excerpt_only', 'title_only')",
    )
    op.create_check_constraint(
        "ck_documents_relevance_status",
        "documents",
        "relevance_status IS NULL OR relevance_status IN "
        "('classified', 'corrected_unsupported_core', 'failed')",
    )
    op.create_check_constraint(
        "ck_documents_event_types",
        "documents",
        f"event_types <@ ARRAY[{EVENT_TYPE_LIST}]::varchar[]",
    )

    op.drop_constraint("ck_documents_evidence_level", "documents", type_="check")
    op.drop_column("documents", "evidence_level")
    op.drop_column("documents", "doc_metadata")
    op.drop_index("documents_ingestion_status_idx", table_name="documents")
    op.drop_index("documents_relevance_tier_idx", table_name="documents")
    op.drop_column("chunks", "created_at")


def downgrade() -> None:
    op.add_column(
        "chunks",
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("documents_relevance_tier_idx", "documents", ["relevance_tier"])
    op.create_index("documents_ingestion_status_idx", "documents", ["ingestion_status"])
    op.add_column(
        "documents",
        sa.Column(
            "doc_metadata",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "documents",
        sa.Column(
            "evidence_level",
            sa.String(32),
            nullable=False,
            server_default="source_entry",
        ),
    )
    op.execute(
        """
        UPDATE documents SET
          evidence_level = CASE
            WHEN extraction_status = 'full_article' THEN 'full_article'
            WHEN extraction_status = 'feed_excerpt_only' AND ingestion_status = 'published'
              THEN 'official_feed_excerpt'
            ELSE 'source_entry'
          END,
          doc_metadata = jsonb_strip_nulls(jsonb_build_object(
            'extraction_status', extraction_status,
            'relevance_classification_status', relevance_status,
            'relevance_policy_version', relevance_policy_version,
            'event_types', to_jsonb(event_types),
            'taxonomy_policy_version', taxonomy_policy_version,
            'display_headline', display_headline,
            'summary', summary,
            'why_it_matters', why_it_matters,
            'key_points', to_jsonb(key_points),
            'summary_generated_by', summary_generated_by
          ))
        """
    )
    op.create_check_constraint(
        "ck_documents_evidence_level",
        "documents",
        "evidence_level IN ('full_article', 'source_entry', 'official_feed_excerpt')",
    )
    op.drop_constraint("ck_documents_event_types", "documents", type_="check")
    op.drop_constraint("ck_documents_relevance_status", "documents", type_="check")
    op.drop_constraint("ck_documents_extraction_status", "documents", type_="check")
    for column in (
        "summary_generated_by",
        "key_points",
        "why_it_matters",
        "summary",
        "display_headline",
        "taxonomy_policy_version",
        "event_types",
        "relevance_policy_version",
        "relevance_status",
        "extraction_status",
    ):
        op.drop_column("documents", column)
