from types import SimpleNamespace

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.db.models import Chunk, Document
from app.schemas.ask import AskRequest
from app.schemas.search import SearchRequest
from app.services.retriever import Candidate, RetrieverService


def candidate(
    document_id: str,
    *,
    title: str = "",
    content: str = "",
) -> Candidate:
    return Candidate(
        chunk=SimpleNamespace(content=content),
        document=SimpleNamespace(id=document_id, title=title),
    )


def test_retrieval_limits_chunks_per_document():
    service = RetrieverService.__new__(RetrieverService)
    candidates = [candidate("a"), candidate("a"), candidate("a"), candidate("b"), candidate("c")]

    selected = service._diversify_documents(candidates, limit=4, max_per_document=2)

    assert [item.document.id for item in selected] == ["a", "a", "b", "c"]


def test_retrieval_skips_title_only_chunks_when_document_has_substantive_candidates():
    service = RetrieverService.__new__(RetrieverService)
    candidates = [
        candidate("a", title="Release A", content="Release A"),
        candidate("a", title="Release A", content="Release A\n\nDetailed change."),
        candidate("b", title="Release B", content="Release B"),
    ]

    selected = service._diversify_documents(candidates, limit=3, max_per_document=2)

    assert [item.document.id for item in selected] == ["a", "b"]
    assert selected[0].chunk.content.endswith("Detailed change.")


def test_keyword_scoring_rewards_distinctive_title_matches() -> None:
    service = RetrieverService.__new__(RetrieverService)
    query = "Which vLLM release candidate fixed P/D with the DP Supervisor?"
    terms = service._keyword_terms(query)

    exact_score = service._keyword_match_score(
        query,
        terms,
        "v0.24.0rc2: Fix P/D with DP Supervisor",
        "Fix P/D with DP Supervisor.",
    )
    long_changelog_score = service._keyword_match_score(
        query,
        terms,
        "v0.24.0",
        "The vLLM release contains many fixes, including DP Supervisor changes.",
    )

    assert exact_score > long_changelog_score


def test_keyword_terms_drop_generic_update_language() -> None:
    service = RetrieverService.__new__(RetrieverService)

    terms = service._keyword_terms("What did OpenAI announce in the GPT-Live update?")

    assert terms == ["openai", "announce", "gpt", "live"]


def test_keyword_normalization_treats_common_separators_as_spaces() -> None:
    service = RetrieverService.__new__(RetrieverService)

    terms = service._keyword_terms(
        "Compare agent-security, agent_security, and agent/security."
    )

    assert terms == ["agent", "security"]


def test_keyword_scoring_matches_hyphenated_query_to_spaced_title() -> None:
    service = RetrieverService.__new__(RetrieverService)
    query = "DeepMind agent-security"
    terms = service._keyword_terms(query)

    hyphenated_score = service._keyword_match_score(
        query,
        terms,
        "DeepMind Agent-Security",
        "",
    )
    spaced_score = service._keyword_match_score(
        query,
        terms,
        "DeepMind Agent Security",
        "",
    )

    assert spaced_score == hyphenated_score
    assert spaced_score > 0


def test_update_retrieval_only_queries_published_documents() -> None:
    service = RetrieverService.__new__(RetrieverService)
    statement = service._apply_filters(
        select(Chunk, Document).join(Document, Chunk.document_id == Document.id),
        SearchRequest(query="agents", collection="updates", search_mode="keyword"),
    )

    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "documents.source_type" not in sql
    assert "ingestion_status" in sql
    assert "published" in sql
    assert "evidence_level" in sql
    assert "official_feed_excerpt" in sql
    assert "anthropic-engineering" in sql
    assert "relevance_tier" in sql
    assert "core" in sql
    assert "documents.relevance_tier IS NULL" not in sql


def test_search_and_answers_accept_only_article_collection() -> None:
    assert SearchRequest(query="agents").collection == "updates"
    assert AskRequest(question="What changed?").collection == "updates"
    with pytest.raises(ValidationError):
        SearchRequest(query="agents", collection="docs")
    with pytest.raises(ValidationError):
        AskRequest(question="What changed?", collection="all")


def test_contextual_retrieval_requires_explicit_inclusion() -> None:
    service = RetrieverService.__new__(RetrieverService)
    base = select(Chunk, Document).join(Document, Chunk.document_id == Document.id)
    default_statement = service._apply_filters(
        base,
        SearchRequest(query="agents", collection="updates", search_mode="keyword"),
    )
    contextual_statement = service._apply_filters(
        base,
        SearchRequest(
            query="agents",
            collection="updates",
            search_mode="keyword",
            include_contextual=True,
        ),
    )
    default_sql = str(
        default_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    contextual_sql = str(
        contextual_statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )

    assert "contextual" not in default_sql
    assert "contextual" in contextual_sql
    assert "excluded" not in contextual_sql
