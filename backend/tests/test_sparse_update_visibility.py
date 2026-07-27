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


def test_low_lexical_grounding_does_not_control_visibility() -> None:
    service = UpdateService.__new__(UpdateService)
    document = make_document(content_detail="detailed")
    document.doc_metadata["summary_quality_warnings"] = ["low_lexical_grounding"]

    assert service._is_feed_visible(
        document,
        include_sparse=False,
        explicit_sparse_context=False,
    )
