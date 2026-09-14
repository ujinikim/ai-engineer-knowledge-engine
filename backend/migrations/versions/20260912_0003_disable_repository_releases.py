"""Disable raw repository release sources.

Revision ID: 20260912_0003
Revises: 20260912_0002
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260912_0003"
down_revision: str | None = "20260912_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


REPOSITORY_RELEASE_SOURCES = (
    "vllm",
    "langgraph",
    "transformers",
    "litellm",
    "qdrant",
    "ollama",
)


def upgrade() -> None:
    op.execute(
        """
        UPDATE update_sources
        SET enabled = false
        WHERE slug IN ('vllm', 'langgraph', 'transformers', 'litellm', 'qdrant', 'ollama')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE update_sources
        SET enabled = true
        WHERE slug IN ('vllm', 'langgraph', 'transformers', 'litellm', 'qdrant', 'ollama')
        """
    )
