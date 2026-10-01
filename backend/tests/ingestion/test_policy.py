from app.domain import PUBLISHED, QUARANTINED
from app.ingestion.policy import evaluate_ingestion_candidate


def test_detailed_source_is_publishable() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="detailed",
        extraction_status="full_article",
        event_types=["engineering-analysis"],
    )

    assert decision.status == PUBLISHED
    assert decision.failure_codes == ()


def test_failed_hydration_and_sparse_excerpt_are_quarantined() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="sparse",
        extraction_status="feed_excerpt_only",
        event_types=["product-release"],
    )

    assert decision.status == QUARANTINED
    assert decision.failure_codes == (
        "article_hydration_failed",
        "insufficient_source_detail",
    )


def test_important_sparse_event_can_publish_when_fetch_did_not_fail() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="sparse",
        extraction_status="source_entry",
        event_types=["security-issue"],
    )

    assert decision.status == PUBLISHED


def test_approved_official_feed_excerpt_is_dashboard_only_evidence() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="sparse",
        extraction_status="feed_excerpt_only",
        event_types=["product-release"],
        publish_feed_excerpt=True,
    )

    assert decision.status == PUBLISHED
    assert decision.failure_codes == ()
    assert decision.warning_codes == (
        "article_hydration_failed",
        "insufficient_source_detail",
    )
    assert decision.evidence_level == "official_feed_excerpt"
    assert decision.default_feed_eligible is True
    assert decision.rag_eligible is False
