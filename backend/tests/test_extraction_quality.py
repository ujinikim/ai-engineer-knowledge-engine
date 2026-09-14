import hashlib
from datetime import datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

from app.services.extraction_quality import ExtractionQualityService


def make_chunk(content: str, index: int = 0):
    return SimpleNamespace(
        chunk_index=index,
        content=content,
        embedding=[0.1, 0.2],
        token_count=max(1, len(content.split())),
        content_hash=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def make_document(
    raw_text: str,
    *,
    source_name: str = "example-source",
    title: str = "Example engineering update",
    published_at: datetime | None = None,
    fetched_at: datetime | None = None,
    content_hash: str | None = None,
    metadata: dict | None = None,
    url: str = "https://example.com/update",
):
    fetched_at = fetched_at or datetime(2026, 7, 22, 12, 0, 0)
    published_at = published_at or fetched_at - timedelta(days=1)
    return SimpleNamespace(
        id=uuid4(),
        source_name=source_name,
        source_type="release",
        title=title,
        url=url,
        canonical_url=url,
        raw_text=raw_text,
        content_hash=content_hash or hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        published_at=published_at,
        fetched_at=fetched_at,
        doc_metadata=metadata
        or {
            "source_type": "official-engineering-blog",
            "source_kind": "rss",
            "quality_tier": "primary",
        },
    )


def test_complete_article_passes_extraction_evaluation() -> None:
    body = " ".join(["The release improves inference latency and reliability."] * 24)
    raw_text = f"Example engineering update\n\n{body}"
    document = make_document(raw_text)

    result = ExtractionQualityService().evaluate(
        document,
        [make_chunk(raw_text)],
        now=datetime(2026, 7, 23),
    )

    assert result.quality_status == "pass"
    assert result.content_hash_valid
    assert result.embeddings_complete
    assert result.publication_date_confidence == "high"
    assert not result.suspected_excerpt
    assert not result.suspected_collection_page


def test_html_listing_collection_url_warns() -> None:
    body = " ".join(["A complete-looking article preview with technical detail."] * 30)
    raw_text = f"June updates\n\n{body}"
    document = make_document(
        raw_text,
        title="June updates",
        url="https://example.com/news/tag/jun-05-2026",
        metadata={
            "source_type": "editorial-analysis",
            "source_kind": "html_listing",
            "quality_tier": "curated",
        },
    )

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert result.suspected_collection_page
    assert "suspected_collection_page" in result.warnings


def test_short_article_with_collection_timestamp_warns() -> None:
    fetched_at = datetime(2026, 7, 22, 12, 0, 0)
    raw_text = "Example engineering update\n\nShort announcement."
    document = make_document(raw_text, published_at=fetched_at, fetched_at=fetched_at)

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert result.quality_status == "warning"
    assert "suspected_excerpt" in result.warnings
    assert "published_at_matches_collection_time" in result.warnings
    assert result.publication_date_confidence == "low"


def test_article_feed_preview_over_old_threshold_warns() -> None:
    body = "Preview sentence with technical context. " * 18
    raw_text = f"Example engineering update\n\n{body}"
    document = make_document(raw_text)

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert 300 < len(raw_text) < 1000
    assert "suspected_excerpt" in result.warnings


def test_short_github_release_is_not_treated_as_excerpt() -> None:
    raw_text = "v1.2.3\n\nFix a scheduler counter."
    document = make_document(
        raw_text,
        title="v1.2.3",
        metadata={
            "source_type": "official-release",
            "source_kind": "github_releases",
            "quality_tier": "primary",
        },
    )

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert not result.suspected_excerpt
    assert "suspected_excerpt" not in result.warnings


def test_short_official_changelog_is_not_treated_as_excerpt() -> None:
    raw_text = "Example product update\n\n" + ("A concise changelog detail. " * 20)
    document = make_document(
        raw_text,
        title="Example product update",
        metadata={
            "source_type": "official-changelog",
            "source_kind": "rss",
            "quality_tier": "primary",
        },
    )

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert len(raw_text) < 1000
    assert "suspected_excerpt" not in result.warnings


def test_hydration_failure_is_reported() -> None:
    raw_text = "Example engineering update\n\n" + ("Feed preview. " * 80)
    document = make_document(
        raw_text,
        metadata={
            "source_type": "official-engineering-blog",
            "source_kind": "rss",
            "quality_tier": "primary",
            "hydration_status": "failed",
        },
    )

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert "article_hydration_failed" in result.warnings


def test_feed_excerpt_only_extraction_is_reported() -> None:
    raw_text = "Example engineering update\n\n" + ("Feed preview. " * 80)
    document = make_document(
        raw_text,
        metadata={
            "source_type": "official-engineering-blog",
            "source_kind": "rss",
            "quality_tier": "primary",
            "hydration_status": "failed",
            "extraction_status": "feed_excerpt_only",
            "summary_input_source": "feed_excerpt",
        },
    )

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert "article_hydration_failed" in result.warnings


def test_single_repeated_footer_does_not_trigger_duplicate_warning() -> None:
    repeated = "The post Example appeared first on The GitHub Blog. " * 6
    unique_a = "Detailed implementation information about billing controls. " * 6
    unique_b = "Additional rollout information for administrators and teams. " * 6
    raw_text = f"Example engineering update\n{repeated}\n{repeated}\n{unique_a}\n{unique_b}"
    document = make_document(raw_text)

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert result.duplicate_line_ratio > 0.15
    assert result.duplicate_line_count == 1
    assert "high_duplicate_line_ratio" not in result.warnings


def test_multiple_repeated_lines_trigger_duplicate_warning() -> None:
    repeated = "Repeated changelog section with enough meaningful text. " * 6
    unique_a = "Detailed implementation information about billing controls. " * 6
    unique_b = "Additional rollout information for administrators and teams. " * 6
    raw_text = (
        "Example engineering update\n"
        f"{repeated}\n{repeated}\n{repeated}\n{repeated}\n{unique_a}\n{unique_b}"
    )
    document = make_document(raw_text)

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert result.duplicate_line_count == 3
    assert "high_duplicate_line_ratio" in result.warnings


def test_github_release_repetition_does_not_trigger_duplicate_warning() -> None:
    repeated = "Repeated release-note prose with enough words to resemble a full paragraph. " * 4
    raw_text = f"v1.2.3\n{repeated}\n{repeated}\n{repeated}\n{repeated}"
    document = make_document(
        raw_text,
        title="v1.2.3",
        metadata={
            "source_type": "official-release",
            "source_kind": "github_releases",
            "quality_tier": "primary",
        },
    )

    result = ExtractionQualityService().evaluate(document, [make_chunk(raw_text)])

    assert result.duplicate_line_count == 3
    assert "high_duplicate_line_ratio" not in result.warnings


def test_integrity_failures_are_reported() -> None:
    raw_text = "Example engineering update\n\n" + ("Useful body. " * 40)
    document = make_document(raw_text, content_hash="incorrect")

    result = ExtractionQualityService().evaluate(document, [])

    assert result.quality_status == "fail"
    assert "content_hash_mismatch" in result.failures
    assert "missing_chunks" in result.failures


def test_excluded_document_does_not_require_chunks() -> None:
    raw_text = "AI Agent Conference\n\n" + ("Event announcement details. " * 80)
    document = make_document(
        raw_text,
        title="AI Agent Conference",
        metadata={
            "ingestion_status": "published",
            "evidence_level": "full_article",
            "relevance_tier": "excluded",
        },
    )

    result = ExtractionQualityService().evaluate(document, [])

    assert result.chunks_expected is False
    assert result.quality_status == "pass"
    assert "missing_chunks" not in result.failures


def test_aggregation_and_sample_cover_sources() -> None:
    service = ExtractionQualityService()
    evaluations = []
    for source in ("alpha", "beta", "gamma"):
        raw_text = f"Example engineering update\n\n{source} " + ("technical detail " * 80)
        document = make_document(raw_text, source_name=source)
        evaluations.append(service.evaluate(document, [make_chunk(raw_text)]))

    summary = service.aggregate(evaluations)
    sample = service.select_review_sample(evaluations, sample_size=3)

    assert summary["documents_evaluated"] == 3
    assert summary["status_counts"] == {"pass": 3, "warning": 0, "fail": 0}
    assert {item.source_name for item in sample} == {"alpha", "beta", "gamma"}
