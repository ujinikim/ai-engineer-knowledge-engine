from types import SimpleNamespace

from app.services.retriever import Candidate, RetrieverService


def candidate(document_id: str) -> Candidate:
    return Candidate(
        chunk=SimpleNamespace(),
        document=SimpleNamespace(id=document_id),
    )


def test_retrieval_limits_chunks_per_document():
    service = RetrieverService.__new__(RetrieverService)
    candidates = [candidate("a"), candidate("a"), candidate("a"), candidate("b"), candidate("c")]

    selected = service._diversify_documents(candidates, limit=4, max_per_document=2)

    assert [item.document.id for item in selected] == ["a", "a", "b", "c"]


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

    assert terms == ["openai", "announce", "gpt-live"]
