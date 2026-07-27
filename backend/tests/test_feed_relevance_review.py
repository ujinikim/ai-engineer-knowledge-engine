from types import SimpleNamespace
from uuid import uuid4

from scripts.prepare_feed_relevance_review import recommendation


def document(title: str, event_types: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        doc_metadata={"event_types": event_types or []},
    )


def test_promotional_title_can_still_represent_core_product_release() -> None:
    tier, reasons, _ = recommendation(
        document(
            "ChatGPT is now a partner for your most ambitious work",
            ["product-release"],
        )
    )

    assert tier == "core"
    assert reasons == ["technical_release_or_change"]


def test_customer_deployment_with_metrics_is_contextual() -> None:
    tier, reasons, _ = recommendation(
        document(
            "NTT DATA Group cuts incident analysis to 30 minutes with Codex",
            ["product-release"],
        )
    )

    assert tier == "contextual"
    assert reasons == ["measured_customer_deployment"]


def test_generic_customer_use_case_is_excluded() -> None:
    tier, reasons, _ = recommendation(
        document("How sales teams use ChatGPT Work", ["product-release"])
    )

    assert tier == "excluded"
    assert reasons == ["customer_story_or_case_study"]


def test_technical_conference_announcement_is_contextual() -> None:
    tier, reasons, _ = recommendation(
        document(
            "PyTorch Conference North America Schedule Is Live",
            ["product-release", "tutorial"],
        )
    )

    assert tier == "contextual"
    assert reasons == ["event_or_community_update"]
