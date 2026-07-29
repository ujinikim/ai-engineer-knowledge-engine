from types import SimpleNamespace

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
