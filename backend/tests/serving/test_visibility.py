"""The one rule for which articles users may see, as the SQL feed and search send."""

from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.serving.feed import FeedService
from app.serving.search import SearchService
from app.serving.visibility import visible_article_clause
from app.sources import configured_active_source_slugs


def sql(statement) -> str:
    return str(
        statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )


def test_default_shows_only_published_core_articles_from_enabled_sources() -> None:
    text = sql(visible_article_clause())

    assert "documents.ingestion_status = 'published'" in text
    assert "documents.relevance_tier IN ('core')" in text
    assert all(f"'{slug}'" in text for slug in configured_active_source_slugs())


def test_including_contextual_adds_that_tier_and_never_excluded() -> None:
    text = sql(visible_article_clause(include_contextual=True))

    assert "documents.relevance_tier IN ('core', 'contextual')" in text
    assert "excluded" not in text


def test_quarantined_and_unclassified_articles_never_match() -> None:
    text = sql(visible_article_clause(include_contextual=True))

    assert "quarantined" not in text  # only 'published' is accepted
    assert "IS NULL" not in text and "NULL" not in text  # a missing tier never matches IN (...)


def test_visibility_ignores_extraction_and_length_so_sparse_and_excerpt_articles_show() -> None:
    text = sql(visible_article_clause(include_contextual=True))

    assert "extraction_status" not in text
    assert "raw_text" not in text


def test_search_adds_only_the_feed_excerpt_exclusion() -> None:
    text = sql(SearchService.__new__(SearchService)._retrievable_document_clause())

    assert sql(visible_article_clause()) in text
    assert "documents.extraction_status != 'feed_excerpt_only'" in text


def test_feed_query_starts_from_the_shared_rule_and_adds_each_filter() -> None:
    db = MagicMock()
    db.scalars.return_value.all.return_value = []

    FeedService(db).list_updates(
        window="all",
        limit=10,
        offset=0,
        tools=["LangChain"],
        categories=["agentic-generative-ai"],
        event_types=["guide"],
        source_types=["editorial-analysis"],
        include_contextual=True,
    )

    text = sql(db.scalars.call_args_list[0].args[0])
    assert sql(visible_article_clause(include_contextual=True)) in text
    assert "coalesce(documents.primary_topic, 'developer-tools') IN ('agentic-generative-ai')" in text
    assert "documents.event_types && ARRAY['guide']" in text
    assert "documents.source_name IN ('langchain-blog')" in text  # tool filter
    assert "documents.source_name IN ('simon-agentic-engineering')" in text  # source-type filter
