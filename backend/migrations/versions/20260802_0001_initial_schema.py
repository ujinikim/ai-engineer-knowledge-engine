"""Establish the PostgreSQL and pgvector baseline schema.

Revision ID: 20260802_0001
Revises:
Create Date: 2026-08-02
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260802_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # IF NOT EXISTS lets a database created by the retired init.sql adopt this
    # baseline without recreating tables or deleting its reviewed corpus.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS documents (
          id uuid PRIMARY KEY,
          source_name varchar(120) NOT NULL,
          source_type varchar(80) NOT NULL DEFAULT 'docs',
          title varchar(500) NOT NULL,
          url text NOT NULL UNIQUE,
          canonical_url text,
          raw_text text NOT NULL,
          content_hash varchar(128) NOT NULL,
          fetched_at timestamp NOT NULL DEFAULT now(),
          published_at timestamp,
          doc_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
          id uuid PRIMARY KEY,
          document_id uuid NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
          chunk_index integer NOT NULL,
          content text NOT NULL,
          embedding vector(1536) NOT NULL,
          token_count integer NOT NULL,
          content_hash varchar(128) NOT NULL,
          chunk_metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
          created_at timestamp NOT NULL DEFAULT now(),
          UNIQUE (document_id, chunk_index)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS update_sources (
          id uuid PRIMARY KEY,
          slug varchar(120) NOT NULL UNIQUE,
          name varchar(200) NOT NULL,
          organization varchar(200) NOT NULL,
          tool varchar(200) NOT NULL,
          category varchar(120) NOT NULL,
          source_kind varchar(80) NOT NULL DEFAULT 'atom',
          feed_url text NOT NULL UNIQUE,
          homepage_url text NOT NULL,
          credibility_weight double precision NOT NULL DEFAULT 1.0,
          enabled boolean NOT NULL DEFAULT true,
          last_collected_at timestamp,
          last_error text,
          source_metadata jsonb NOT NULL DEFAULT '{}'::jsonb
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS documents_source_name_idx ON documents (source_name)")
    op.execute("CREATE INDEX IF NOT EXISTS documents_content_hash_idx ON documents (content_hash)")
    op.execute("CREATE INDEX IF NOT EXISTS documents_source_type_idx ON documents (source_type)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS documents_published_at_idx "
        "ON documents (published_at DESC)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS update_sources_slug_idx ON update_sources (slug)")
    op.execute("CREATE INDEX IF NOT EXISTS update_sources_tool_idx ON update_sources (tool)")
    op.execute("CREATE INDEX IF NOT EXISTS update_sources_category_idx ON update_sources (category)")
    op.execute("CREATE INDEX IF NOT EXISTS chunks_document_id_idx ON chunks (document_id)")
    op.execute("CREATE INDEX IF NOT EXISTS chunks_content_hash_idx ON chunks (content_hash)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_embedding_hnsw_idx ON chunks "
        "USING hnsw (embedding vector_cosine_ops)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS chunks_content_fts_idx ON chunks "
        "USING gin (to_tsvector('english', content))"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS chunks")
    op.execute("DROP TABLE IF EXISTS update_sources")
    op.execute("DROP TABLE IF EXISTS documents")
    # The vector extension may be shared by other schemas, so this migration does
    # not remove it automatically.
