from app.ingestion.taxonomy import (
    classify_topic_with_method,
    infer_event_types,
    normalize_event_types,
)


def test_topic_classification_exposes_when_source_default_was_used() -> None:
    topic, method = classify_topic_with_method(
        "A short announcement without any category evidence.",
        "agentic-generative-ai",
    )

    assert topic == "agentic-generative-ai"
    assert method == "source-default"


def test_topic_classification_uses_evidence_before_source_default() -> None:
    topic, method = classify_topic_with_method(
        "A safety evaluation benchmark for model security.",
        "agentic-generative-ai",
    )

    assert topic == "safety-evaluation-governance"
    assert method == "deterministic-keyword"


def test_generic_search_does_not_imply_retrieval_infrastructure() -> None:
    topic, method = classify_topic_with_method(
        "A researcher uses an AI assistant to search genomes for antimicrobial molecules.",
        "agentic-generative-ai",
    )

    assert topic == "agentic-generative-ai"
    assert method == "source-default"


def test_specific_information_retrieval_language_is_still_detected() -> None:
    topic, method = classify_topic_with_method(
        "The study measures web retrieval quality for an LLM search engine.",
        "agentic-generative-ai",
    )

    assert topic == "data-search-retrieval"
    assert method == "deterministic-keyword"


def test_event_inference() -> None:
    assert infer_event_types("This API endpoint is deprecated and will sunset.") == ["alert"]


def test_event_normalization_keeps_at_most_one_v2_event() -> None:
    assert normalize_event_types(
        "transformers",
        ["release-update", "alert"],
    ) == ["release-update"]
    assert normalize_event_types("ollama", ["product-release"]) == []


def test_event_default_is_only_used_when_content_has_no_event_signal() -> None:
    assert infer_event_types("This paper presents a new study.", ["release-update"]) == ["research"]
    assert infer_event_types("A concise source with no event language.", ["analysis"]) == ["analysis"]
