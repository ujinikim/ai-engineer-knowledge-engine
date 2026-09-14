from types import SimpleNamespace

from app.services.source_detail import (
    classify_content_detail,
    sparse_visibility_metadata,
)
from app.services.updates import UpdateService


def make_document(
    *,
    title: str = "v1.2.3",
    body: str = "Fix query errors when using shard keys while resharding.",
    event_types: list[str] | None = None,
    content_detail: str | None = None,
) -> SimpleNamespace:
    metadata: dict = {"event_types": event_types or ["library-release"]}
    if content_detail:
        metadata["content_detail"] = content_detail
    return SimpleNamespace(
        title=title,
        raw_text=f"{title}\n\n{body}",
        doc_metadata=metadata,
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


def test_sparse_visibility_metadata_excludes_ordinary_patch_notes() -> None:
    visibility = sparse_visibility_metadata("sparse", ["library-release"])

    assert visibility == {
        "content_detail": "sparse",
        "default_feed_eligible": False,
        "default_feed_exclusion_reason": "low_source_detail",
    }


def test_important_events_override_sparse_suppression() -> None:
    for event_type in (
        "security-issue",
        "breaking-change",
        "deprecation",
        "incident",
    ):
        visibility = sparse_visibility_metadata("sparse", [event_type])
        assert visibility["default_feed_eligible"] is True
        assert visibility["default_feed_exclusion_reason"] is None


def test_default_feed_hides_sparse_document() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="sparse")

    assert not service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_explicit_inclusion_and_source_or_tool_context_show_sparse_document() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="sparse")
    document.doc_metadata["ingestion_status"] = "published"

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
    document = make_document(content_detail="sparse", event_types=["security-issue"])
    document.doc_metadata["ingestion_status"] = "quarantined"

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


def test_persisted_feed_eligibility_can_show_an_official_sparse_excerpt() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="sparse")
    document.doc_metadata.update(
        {
            "ingestion_status": "published",
            "evidence_level": "official_feed_excerpt",
            "default_feed_eligible": True,
            "default_feed_exclusion_reason": None,
        }
    )

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_low_lexical_grounding_does_not_control_visibility() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="detailed")
    document.doc_metadata["summary_quality_warnings"] = ["low_lexical_grounding"]

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )


def test_contextual_feed_entries_require_explicit_inclusion() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="detailed")
    document.doc_metadata.update(
        {"ingestion_status": "published", "relevance_tier": "contextual"}
    )

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
    document = make_document(content_detail="detailed")
    document.doc_metadata.update(
        {"ingestion_status": "published", "relevance_tier": "excluded"}
    )

    assert not service._is_feed_visible(
        document,
        include_sparse=True,
        explicit_sparse_context=True,
        include_contextual=True,
    )


def test_rag_eligibility_is_derived_from_canonical_fields() -> None:
    service = UpdateService.__new__(UpdateService)
    contextual = make_document(content_detail="detailed")
    contextual.ingestion_status = "published"
    contextual.evidence_level = "source_entry"
    contextual.relevance_tier = "contextual"
    contextual.doc_metadata["rag_eligible"] = False
    excluded = make_document(content_detail="detailed")
    excluded.ingestion_status = "published"
    excluded.evidence_level = "full_article"
    excluded.relevance_tier = "excluded"
    excluded.doc_metadata["rag_eligible"] = True

    assert service._rag_eligible(contextual) is True
    assert service._rag_eligible(excluded) is False


def test_default_feed_eligibility_ignores_stale_compatibility_boolean() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="detailed")
    document.ingestion_status = "published"
    document.evidence_level = "full_article"
    document.relevance_tier = "core"
    document.doc_metadata["default_feed_eligible"] = False

    assert service._default_feed_eligible(document) is True
    assert service._visibility(document)["default_feed_eligible"] is True
