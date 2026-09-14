"""Promote canonical document decisions to typed columns.

Revision ID: 20260913_0004
Revises: 20260912_0003
Create Date: 2026-09-13
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "20260913_0004"
down_revision: str | None = "20260912_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


PRIMARY_TOPICS = (
    "agentic-generative-ai",
    "machine-learning-classical-ai",
    "vision-speech-robotics",
    "data-search-retrieval",
    "ai-products-engineering-infrastructure",
    "safety-evaluation-governance",
)
EVENT_TYPES = ("release-update", "research", "guide", "analysis", "alert")


def upgrade() -> None:
    # Keep doc_metadata during the rolling migration. Readers can fall back to it
    # until every writer populates the typed columns directly.
    op.add_column(
        "documents",
        sa.Column("ingestion_status", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "documents",
        sa.Column("evidence_level", sa.String(length=32), nullable=True),
    )
    op.add_column("documents", sa.Column("relevance_tier", sa.String(length=32)))
    op.add_column("documents", sa.Column("relevance_reason", sa.Text()))
    op.add_column("documents", sa.Column("primary_topic", sa.String(length=80)))
    op.add_column("documents", sa.Column("event_type", sa.String(length=32)))
    op.add_column("documents", sa.Column("summary", sa.Text()))
    op.add_column(
        "documents",
        sa.Column(
            "processing_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("chunks", sa.Column("embedding_model", sa.String(length=120)))
    op.add_column("chunks", sa.Column("chunking_version", sa.String(length=80)))

    op.execute(
        """
        UPDATE documents
        SET
          ingestion_status = CASE
            WHEN doc_metadata->>'ingestion_status' IN ('published', 'quarantined')
              THEN doc_metadata->>'ingestion_status'
            ELSE 'published'
          END,
          evidence_level = CASE
            WHEN doc_metadata->>'evidence_level'
              IN ('full_article', 'source_entry', 'official_feed_excerpt')
              THEN doc_metadata->>'evidence_level'
            ELSE 'source_entry'
          END,
          relevance_tier = CASE
            WHEN coalesce(
              doc_metadata->>'relevance_tier',
              doc_metadata->>'feed_relevance_tier'
            ) IN ('core', 'contextual', 'excluded')
              THEN coalesce(
                doc_metadata->>'relevance_tier',
                doc_metadata->>'feed_relevance_tier'
              )
            ELSE NULL
          END,
          relevance_reason = nullif(coalesce(
            doc_metadata->>'relevance_reason',
            doc_metadata->>'feed_relevance_reason'
          ), ''),
          primary_topic = CASE
            WHEN doc_metadata->>'primary_topic' IN (
              'agentic-generative-ai',
              'machine-learning-classical-ai',
              'vision-speech-robotics',
              'data-search-retrieval',
              'ai-products-engineering-infrastructure',
              'safety-evaluation-governance'
            ) THEN doc_metadata->>'primary_topic'
            ELSE NULL
          END,
          event_type = CASE
            WHEN coalesce(
              doc_metadata->>'event_type',
              doc_metadata->'event_types'->>0
            ) IN ('release-update', 'research', 'guide', 'analysis', 'alert')
              THEN coalesce(
                doc_metadata->>'event_type',
                doc_metadata->'event_types'->>0
              )
            ELSE NULL
          END,
          summary = nullif(doc_metadata->>'summary', ''),
          processing_metadata = coalesce(
            doc_metadata->'processing_metadata',
            '{}'::jsonb
          ) || jsonb_build_object(
            'classification', jsonb_strip_nulls(jsonb_build_object(
              'taxonomy_policy_version', doc_metadata->>'taxonomy_policy_version',
              'taxonomy_generated_by', doc_metadata->>'taxonomy_generated_by',
              'summary_generated_by', doc_metadata->>'summary_generated_by'
            )),
            'extraction', jsonb_build_object(
              'failure_codes', coalesce(
                doc_metadata->'ingestion_failure_codes', '[]'::jsonb
              ),
              'warning_codes', coalesce(
                doc_metadata->'ingestion_warning_codes', '[]'::jsonb
              )
            )
          )
        """
    )
    op.execute(
        """
        UPDATE chunks
        SET
          embedding_model = nullif(chunk_metadata->>'embedding_model', ''),
          chunking_version = nullif(chunk_metadata->>'chunking_version', '')
        """
    )

    op.alter_column(
        "documents",
        "ingestion_status",
        nullable=False,
        server_default="published",
    )
    op.alter_column(
        "documents",
        "evidence_level",
        nullable=False,
        server_default="source_entry",
    )

    op.drop_index("documents_ingestion_status_idx", table_name="documents")
    op.create_index(
        "documents_ingestion_status_idx", "documents", ["ingestion_status"]
    )
    op.create_index("documents_relevance_tier_idx", "documents", ["relevance_tier"])
    op.create_index("documents_primary_topic_idx", "documents", ["primary_topic"])
    op.create_index("documents_event_type_idx", "documents", ["event_type"])
    op.execute(
        """
        CREATE INDEX documents_feed_scope_idx
        ON documents (ingestion_status, relevance_tier, source_name, published_at DESC)
        """
    )

    op.create_check_constraint(
        "ck_documents_ingestion_status",
        "documents",
        "ingestion_status IN ('published', 'quarantined')",
    )
    op.create_check_constraint(
        "ck_documents_evidence_level",
        "documents",
        "evidence_level IN ('full_article', 'source_entry', 'official_feed_excerpt')",
    )
    op.create_check_constraint(
        "ck_documents_relevance_tier",
        "documents",
        "relevance_tier IS NULL OR relevance_tier IN ('core', 'contextual', 'excluded')",
    )
    op.create_check_constraint(
        "ck_documents_primary_topic",
        "documents",
        "primary_topic IS NULL OR primary_topic IN "
        f"{PRIMARY_TOPICS!r}",
    )
    op.create_check_constraint(
        "ck_documents_event_type",
        "documents",
        "event_type IS NULL OR event_type IN "
        f"{EVENT_TYPES!r}",
    )


def downgrade() -> None:
    op.drop_constraint("ck_documents_event_type", "documents", type_="check")
    op.drop_constraint("ck_documents_primary_topic", "documents", type_="check")
    op.drop_constraint("ck_documents_relevance_tier", "documents", type_="check")
    op.drop_constraint("ck_documents_evidence_level", "documents", type_="check")
    op.drop_constraint("ck_documents_ingestion_status", "documents", type_="check")

    op.drop_index("documents_feed_scope_idx", table_name="documents")
    op.drop_index("documents_event_type_idx", table_name="documents")
    op.drop_index("documents_primary_topic_idx", table_name="documents")
    op.drop_index("documents_relevance_tier_idx", table_name="documents")
    op.drop_index("documents_ingestion_status_idx", table_name="documents")
    op.execute(
        """
        CREATE INDEX documents_ingestion_status_idx
        ON documents ((doc_metadata->>'ingestion_status'))
        """
    )

    op.drop_column("chunks", "chunking_version")
    op.drop_column("chunks", "embedding_model")
    op.drop_column("documents", "processing_metadata")
    op.drop_column("documents", "summary")
    op.drop_column("documents", "event_type")
    op.drop_column("documents", "primary_topic")
    op.drop_column("documents", "relevance_reason")
    op.drop_column("documents", "relevance_tier")
    op.drop_column("documents", "evidence_level")
    op.drop_column("documents", "ingestion_status")
