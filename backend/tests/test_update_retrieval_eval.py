from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.schemas.search import SearchRequest
from scripts.evaluation.evaluate_update_retrieval import (
    filter_violations,
    required_text_coverage,
    retrieval_metrics,
    validate_question_set,
)


def result(**overrides):
    values = {
        "document_id": "doc-1",
        "document_title": "Runtime release",
        "content": "The runtime adds a new cache control.",
        "source_name": "runtime-source",
        "tool": "Runtime",
        "category": "inference-serving",
        "event_types": ["library-release"],
        "source_category": "official-release",
        "maturity": "stable",
        "published_at": datetime(2026, 7, 27, tzinfo=timezone.utc),
    }
    return SimpleNamespace(**{**values, **overrides})


def test_retrieval_metrics_use_unique_documents_but_rank_first_chunk() -> None:
    metrics = retrieval_metrics(
        ["irrelevant", "doc-1", "doc-1", "doc-2"],
        ["doc-1", "doc-2"],
    )

    assert metrics["recall_at_k"] == 1.0
    assert metrics["precision_at_k"] == pytest.approx(2 / 3, abs=0.0001)
    assert metrics["first_relevant_rank"] == 2
    assert metrics["reciprocal_rank"] == 0.5
    assert metrics["all_relevant_documents_hit"] is True


def test_insufficient_evidence_case_has_nullable_relevance_metrics() -> None:
    metrics = retrieval_metrics(["doc-1"], [])

    assert metrics["recall_at_k"] is None
    assert metrics["reciprocal_rank"] is None
    assert metrics["all_relevant_documents_hit"] is None


def test_filter_validation_reports_only_failed_fields() -> None:
    request = SearchRequest(
        query="What changed?",
        collection="updates",
        source_names=["other-source"],
        categories=["inference-serving"],
        event_types=["library-release"],
    )

    violations = filter_violations([result()], request)

    assert violations == [{"document_id": "doc-1", "field": "source_names"}]


def test_required_text_coverage_is_case_and_whitespace_insensitive() -> None:
    hits, coverage = required_text_coverage(
        [result(content="The runtime adds a NEW   cache control.")],
        ["new cache control", "missing fact"],
    )

    assert hits == ["new cache control"]
    assert coverage == 0.5


def test_question_set_requires_matching_snapshot_and_known_documents() -> None:
    snapshot = {
        "corpus_hash": "snapshot-hash",
        "documents": [{"document_id": "doc-1"}],
    }
    payload = {
        "snapshot_corpus_hash": "snapshot-hash",
        "questions": [
            {
                "id": "lookup",
                "question": "What changed?",
                "intent": "lookup",
                "split": "calibration",
                "expected_outcome": "answerable",
                "request": {"collection": "updates"},
                "relevant_document_ids": ["doc-1"],
            }
        ],
    }

    validate_question_set(payload, snapshot)

    payload["questions"][0]["relevant_document_ids"] = ["missing"]
    with pytest.raises(ValueError, match="missing from snapshot"):
        validate_question_set(payload, snapshot)
