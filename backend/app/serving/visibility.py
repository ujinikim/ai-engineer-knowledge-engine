"""Which stored articles users may see. Feed and search both start from this rule."""

from sqlalchemy import and_

from app.db.models import Document
from app.domain import PUBLISHED, visible_relevance_tiers
from app.sources import configured_active_source_slugs


def visible_article_clause(*, include_contextual: bool = False):
    """Published articles from enabled sources whose relevance tier is shown."""
    return and_(
        Document.source_name.in_(configured_active_source_slugs()),
        Document.ingestion_status == PUBLISHED,
        Document.relevance_tier.in_(visible_relevance_tiers(include_contextual=include_contextual)),
    )
