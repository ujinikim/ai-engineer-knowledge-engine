"""Replace the source registry table with per-source collection run history.

Revision ID: 20260925_0006
Revises: 20260925_0005
Create Date: 2026-09-25
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260925_0006"
down_revision: str | None = "20260925_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE collection_source_runs (
          id uuid PRIMARY KEY,
          run_id varchar(64) NOT NULL,
          source_slug varchar(120) NOT NULL,
          started_at timestamp NOT NULL,
          finished_at timestamp NOT NULL,
          status varchar(32) NOT NULL,
          matched_items integer NOT NULL DEFAULT 0,
          updates_created integer NOT NULL DEFAULT 0,
          updates_changed integer NOT NULL DEFAULT 0,
          updates_unchanged integer NOT NULL DEFAULT 0,
          updates_quarantined integer NOT NULL DEFAULT 0,
          chunks_written integer NOT NULL DEFAULT 0,
          error text,
          CONSTRAINT uq_collection_source_runs_run_source UNIQUE (run_id, source_slug)
        )
        """
    )
    op.execute(
        "CREATE INDEX collection_source_runs_source_finished_idx "
        "ON collection_source_runs (source_slug, finished_at)"
    )
    op.execute("DROP TABLE update_sources")


def downgrade() -> None:
    op.execute(
        """
        CREATE TABLE update_sources (
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
    op.execute("CREATE INDEX update_sources_slug_idx ON update_sources (slug)")
    op.execute("CREATE INDEX update_sources_tool_idx ON update_sources (tool)")
    op.execute("CREATE INDEX update_sources_category_idx ON update_sources (category)")
    op.execute("DROP TABLE collection_source_runs")
