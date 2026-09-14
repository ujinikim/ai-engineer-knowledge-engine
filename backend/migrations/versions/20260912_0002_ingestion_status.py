"""Backfill explicit ingestion publication status.

Revision ID: 20260912_0002
Revises: 20260802_0001
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260912_0002"
down_revision: str | None = "20260802_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE documents
        SET doc_metadata = doc_metadata || jsonb_build_object(
          'ingestion_status',
          CASE
            WHEN source_type <> 'release' THEN 'published'
            WHEN source_name = 'openai-news'
              AND doc_metadata->>'extraction_status' = 'feed_excerpt_only'
              THEN 'published'
            WHEN doc_metadata->>'hydration_status' = 'failed' THEN 'quarantined'
            WHEN doc_metadata->>'extraction_status' = 'title_only' THEN 'quarantined'
            WHEN doc_metadata->>'content_detail' = 'sparse'
              AND NOT coalesce(doc_metadata->'event_types', '[]'::jsonb)
                ?| ARRAY['security-issue', 'breaking-change', 'deprecation', 'incident']
              THEN 'quarantined'
            ELSE 'published'
          END,
          'ingestion_failure_codes',
          CASE
            WHEN source_type <> 'release' THEN '[]'::jsonb
            WHEN source_name = 'openai-news'
              AND doc_metadata->>'extraction_status' = 'feed_excerpt_only'
              THEN '[]'::jsonb
            ELSE to_jsonb(array_remove(ARRAY[
              CASE
                WHEN doc_metadata->>'hydration_status' = 'failed'
                  THEN 'article_hydration_failed'
              END,
              CASE
                WHEN doc_metadata->>'extraction_status' = 'title_only'
                  THEN 'title_only_source'
              END,
              CASE
                WHEN doc_metadata->>'content_detail' = 'sparse'
                  AND NOT coalesce(doc_metadata->'event_types', '[]'::jsonb)
                    ?| ARRAY['security-issue', 'breaking-change', 'deprecation', 'incident']
                  THEN 'insufficient_source_detail'
              END
            ], NULL))
          END,
          'ingestion_warning_codes',
          CASE
            WHEN source_name = 'openai-news'
              AND doc_metadata->>'extraction_status' = 'feed_excerpt_only'
              THEN to_jsonb(array_remove(ARRAY[
                'article_hydration_failed',
                CASE
                  WHEN doc_metadata->>'content_detail' = 'sparse'
                    THEN 'insufficient_source_detail'
                END
              ], NULL))
            ELSE '[]'::jsonb
          END,
          'evidence_level',
          CASE
            WHEN source_name = 'openai-news'
              AND doc_metadata->>'extraction_status' = 'feed_excerpt_only'
              THEN 'official_feed_excerpt'
            WHEN doc_metadata->>'extraction_status' = 'full_article' THEN 'full_article'
            ELSE 'source_entry'
          END,
          'rag_eligible',
          CASE
            WHEN source_name = 'openai-news'
              AND doc_metadata->>'extraction_status' = 'feed_excerpt_only'
              THEN false
            WHEN source_type <> 'release' THEN true
            WHEN doc_metadata->>'hydration_status' = 'failed' THEN false
            WHEN doc_metadata->>'extraction_status' = 'title_only' THEN false
            WHEN doc_metadata->>'content_detail' = 'sparse'
              AND NOT coalesce(doc_metadata->'event_types', '[]'::jsonb)
                ?| ARRAY['security-issue', 'breaking-change', 'deprecation', 'incident']
              THEN false
            ELSE true
          END
        )
        """
    )
    op.execute(
        """
        UPDATE documents
        SET doc_metadata = doc_metadata || jsonb_build_object(
          'quarantine_reason', doc_metadata->'ingestion_failure_codes'->>0,
          'default_feed_eligible', false,
          'default_feed_exclusion_reason', 'ingestion_quarantined'
        )
        WHERE doc_metadata->>'ingestion_status' = 'quarantined'
        """
    )
    op.execute(
        """
        UPDATE documents
        SET doc_metadata = doc_metadata || jsonb_build_object(
          'display_headline', title,
          'summary', coalesce(nullif(doc_metadata->>'excerpt', ''), raw_text),
          'why_it_matters', '',
          'key_points', '[]'::jsonb,
          'summary_generated_by', 'source-excerpt',
          'default_feed_eligible', true,
          'default_feed_exclusion_reason', NULL
        )
        WHERE doc_metadata->>'evidence_level' = 'official_feed_excerpt'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS documents_ingestion_status_idx
        ON documents ((doc_metadata->>'ingestion_status'))
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS documents_ingestion_status_idx")
    op.execute(
        """
        UPDATE documents
        SET doc_metadata = doc_metadata
          - 'ingestion_status'
          - 'ingestion_failure_codes'
          - 'ingestion_warning_codes'
          - 'quarantine_reason'
          - 'evidence_level'
          - 'rag_eligible'
          - 'last_ingestion_attempt_status'
          - 'last_ingestion_failure_codes'
          - 'last_ingestion_warning_codes'
          - 'last_ingestion_evidence_level'
          - 'last_ingestion_attempted_at'
        """
    )
