from scripts.evaluate_retrieval import search_request


def test_legacy_retrieval_questions_default_to_docs_collection() -> None:
    request = search_request({"question": "How does memory work?"})

    assert request.collection == "docs"


def test_legacy_retrieval_question_can_override_collection() -> None:
    request = search_request(
        {
            "question": "What changed?",
            "collection": "updates",
            "top_k": 8,
        }
    )

    assert request.collection == "updates"
    assert request.top_k == 8
