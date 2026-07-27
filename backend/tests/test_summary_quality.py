from types import SimpleNamespace
from uuid import uuid4

from app.services.summary_quality import SummaryQualityService, SummaryThresholds


def make_document(
    *,
    raw_text: str | None = None,
    metadata: dict | None = None,
    source_name: str = "example-source",
):
    raw_text = raw_text or (
        "Inference runtime update\n\n"
        "The release improves inference latency by 20 percent and adds safer cache handling. "
        "Developers can deploy the update without changing the existing API."
    )
    metadata = metadata or {
        "source_type": "official-engineering-blog",
        "display_headline": "Inference runtime improves latency",
        "summary": "The release improves inference latency and cache handling.",
        "why_it_matters": "Developers can deploy faster inference without changing the API.",
        "key_points": [
            "Inference latency is improved.",
            "Cache handling is safer.",
        ],
        "primary_topic": "inference-serving",
        "topic_tags": ["models-apis"],
        "event_types": ["product-release"],
        "entity_tags": ["example-runtime"],
        "maturity": "stable",
        "summary_generated_by": "gpt-test:official-engineering-blog",
        "hydration_status": "full_article",
    }
    return SimpleNamespace(
        id=uuid4(),
        source_name=source_name,
        source_type="release",
        title="Inference runtime update",
        url="https://example.com/update",
        canonical_url="https://example.com/update",
        raw_text=raw_text,
        content_hash="content-hash",
        doc_metadata=metadata,
    )


def test_valid_summary_passes() -> None:
    result = SummaryQualityService().evaluate(make_document())

    assert result.quality_status == "pass"
    assert not result.failures
    assert result.grounding_overlap >= 0.35


def test_unsupported_number_is_reported() -> None:
    document = make_document()
    document.doc_metadata = {
        **document.doc_metadata,
        "summary": "The release improves inference latency by 75%.",
    }

    result = SummaryQualityService().evaluate(document)

    assert result.unsupported_numbers == ["75%"]
    assert "unsupported_number" in result.warnings


def test_percent_wording_and_symbol_are_equivalent() -> None:
    document = make_document(
        raw_text=(
            "Benchmark result\n\n"
            "The system completed 90 percent of benchmark tasks successfully."
        )
    )
    document.doc_metadata = {
        **document.doc_metadata,
        "summary": "The system completed 90% of benchmark tasks successfully.",
    }

    result = SummaryQualityService().evaluate(document)

    assert not result.unsupported_numbers
    assert "unsupported_number" not in result.warnings


def test_numeric_trailing_zeroes_are_equivalent() -> None:
    document = make_document(
        raw_text="Generation result\n\nThe model emits 62.0 tokens per second."
    )
    document.doc_metadata = {
        **document.doc_metadata,
        "summary": "The model emits 62 tokens per second.",
    }

    result = SummaryQualityService().evaluate(document)

    assert not result.unsupported_numbers


def test_derived_half_to_percentage_remains_a_review_candidate() -> None:
    document = make_document(
        raw_text="Adoption result\n\nMore than half of developers use the tool each month."
    )
    document.doc_metadata = {
        **document.doc_metadata,
        "summary": "More than 50% of developers use the tool each month.",
    }

    result = SummaryQualityService().evaluate(document)

    assert result.unsupported_numbers == ["50%"]
    assert "unsupported_number" in result.warnings


def test_version_number_with_leading_v_is_supported() -> None:
    document = make_document(
        raw_text="Runtime v1.18.3\n\nRuntime v1.18.3 fixes resharding query errors."
    )
    document.doc_metadata = {
        **document.doc_metadata,
        "display_headline": "Runtime 1.18.3 fixes resharding errors",
        "summary": "Runtime version 1.18.3 fixes resharding query errors.",
    }

    result = SummaryQualityService().evaluate(document)

    assert not result.unsupported_numbers
    assert "unsupported_number" not in result.warnings


def test_grounding_normalizes_basic_word_forms() -> None:
    service = SummaryQualityService()

    overlap = service._grounding_overlap(
        "The runtime released improvements.",
        "The runtime release will improve serving.",
    )

    assert overlap == 1.0


def test_sparse_sources_use_a_stricter_grounding_threshold() -> None:
    thresholds = SummaryThresholds(
        low_grounding_overlap=0.0,
        sparse_low_grounding_overlap=1.0,
    )
    document = make_document()
    document.doc_metadata = {**document.doc_metadata, "content_detail": "sparse"}

    result = SummaryQualityService(thresholds).evaluate(document)

    assert result.source_detail == "sparse"
    assert "low_lexical_grounding" in result.warnings


def test_missing_fields_and_invalid_taxonomy_fail() -> None:
    document = make_document()
    document.doc_metadata = {
        **document.doc_metadata,
        "summary": "",
        "primary_topic": "unknown-topic",
        "event_types": ["unknown-event"],
        "maturity": "unknown",
    }

    result = SummaryQualityService().evaluate(document)

    assert result.quality_status == "fail"
    assert "missing_summary" in result.failures
    assert "invalid_primary_topic" in result.failures
    assert "invalid_event_type" in result.failures
    assert "invalid_maturity" in result.failures


def test_fallback_and_incomplete_source_are_visible() -> None:
    document = make_document()
    document.doc_metadata = {
        **document.doc_metadata,
        "summary_generated_by": "deterministic-fallback",
        "hydration_status": "failed",
    }

    result = SummaryQualityService().evaluate(document)

    assert "deterministic_fallback_summary" in result.warnings
    assert "source_content_incomplete" in result.warnings


def test_successful_model_summary_can_still_use_incomplete_source_content() -> None:
    document = make_document()
    document.doc_metadata = {
        **document.doc_metadata,
        "summary_generated_by": "gpt-test:official-product-news",
        "hydration_status": "failed",
        "extraction_status": "feed_excerpt_only",
        "summary_input_source": "feed_excerpt",
    }

    result = SummaryQualityService().evaluate(document)

    assert "source_content_incomplete" in result.warnings
    assert "deterministic_fallback_summary" not in result.warnings


def test_review_key_changes_with_summary_content() -> None:
    service = SummaryQualityService()
    document = make_document()
    first = service.evaluate(document)
    document.doc_metadata = {
        **document.doc_metadata,
        "summary": "The release improves cache handling.",
    }
    second = service.evaluate(document)

    assert first.review_key != second.review_key


def test_review_sample_covers_source_types() -> None:
    service = SummaryQualityService()
    evaluations = []
    for index, source_type in enumerate(
        ("official-release", "official-engineering-blog", "editorial-analysis")
    ):
        document = make_document(source_name=f"source-{index}")
        document.doc_metadata = {**document.doc_metadata, "source_type": source_type}
        evaluations.append(service.evaluate(document))

    sample = service.select_review_sample(evaluations, sample_size=3)

    assert {item.source_type for item in sample} == {
        "official-release",
        "official-engineering-blog",
        "editorial-analysis",
    }


def test_review_sample_skips_incomplete_source_content() -> None:
    service = SummaryQualityService()
    incomplete = make_document(source_name="preview-only")
    incomplete.doc_metadata = {**incomplete.doc_metadata, "hydration_status": "failed"}
    complete = make_document(source_name="complete-source")

    sample = service.select_review_sample(
        [service.evaluate(incomplete), service.evaluate(complete)],
        sample_size=1,
    )

    assert sample[0].source_name == "complete-source"
