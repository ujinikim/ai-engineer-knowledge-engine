from types import SimpleNamespace

from app.services.source_detail import classify_content_detail
from app.services.updates import UpdateService


def make_document(
    *,
    title: str = "v1.2.3",
    body: str = "Fix query errors when using shard keys while resharding.",
    event_types: list[str] | None = None,
) -> SimpleNamespace:
    metadata: dict = {"event_types": event_types or ["library-release"]}
    return SimpleNamespace(
        title=title,
        raw_text=f"{title}\n\n{body}",
        doc_metadata=metadata,
        ingestion_status="published",
        evidence_level="source_entry",
        relevance_tier="core",
    )


def test_content_detail_classifies_sparse_and_detailed_sources() -> None:
    sparse = make_document()
    detailed_body = " ".join(
        [
            "The release introduces a cache for production inference workloads.",
            "Production testing reduced median latency across three representative deployments.",
            "Operators can enable the cache through the existing runtime configuration.",
            "Compatibility details cover existing deployments and supported runtime versions.",
            "The release notes provide benchmark methodology and staged rollout guidance.",
            "Additional examples explain monitoring behavior during the migration process.",
        ]
    )
    detailed = make_document(title="Cache release", body=detailed_body)

    assert classify_content_detail(sparse.title, sparse.raw_text) == "sparse"
    assert classify_content_detail(detailed.title, detailed.raw_text) == "detailed"


def test_sparse_detail_alone_does_not_hide_published_core_document() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document()

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_explicit_inclusion_and_source_or_tool_context_show_sparse_document() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document()

    assert service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=False,
    )
    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=True,
    )


def test_quarantined_document_stays_hidden_even_when_sparse_is_requested() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(event_types=["security-issue"])
    document.ingestion_status = "quarantined"

    assert not service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=True,
    )
    assert not service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=True,
    )


def test_approved_official_sparse_excerpt_can_appear_in_feed() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document()
    document.evidence_level = "official_feed_excerpt"

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_low_lexical_grounding_does_not_control_visibility() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document()
    document.doc_metadata["summary_quality_warnings"] = ["low_lexical_grounding"]

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_contextual_feed_entries_require_explicit_inclusion() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document()
    document.relevance_tier = "contextual"

    assert not service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )
    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
        include_contextual=True,
    )


def test_excluded_feed_entries_stay_hidden_when_contextual_is_included() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document()
    document.relevance_tier = "excluded"

    assert not service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=True,
        include_contextual=True,
    )
