from types import SimpleNamespace
from uuid import uuid4

from scripts.reviews.prepare_feed_relevance_review import recommendation


def document(title: str, event_types: list[str] | None = None) -> SimpleNamespace:
    return SimpleNamespace(
        id=uuid4(),
        title=title,
        event_types=event_types or [],
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



def test_generic_customer_use_case_is_excluded() -> None:
    tier, reasons, _ = recommendation(
        document("How sales teams use ChatGPT Work", ["product-release"])
    )

    assert tier == "excluded"
    assert reasons == ["customer_story_or_case_study"]



def test_concrete_safety_features_are_core_despite_societal_title() -> None:
    tier, reasons, _ = recommendation(
        document("Why teens deserve access to safe AI", ["product-release"])
    )

    assert tier == "core"
    assert reasons == ["technical_release_or_change"]
