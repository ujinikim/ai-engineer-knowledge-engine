from types import SimpleNamespace
from uuid import uuid4

from scripts.reviews.prepare_feed_relevance_review import recommendation


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


def test_concrete_safety_features_are_core_despite_societal_title() -> None:
    tier, reasons, _ = recommendation(
        document("Why teens deserve access to safe AI", ["product-release"])
    )

    assert tier == "core"
    assert reasons == ["technical_release_or_change"]


def test_existing_api_walkthrough_is_a_technical_tutorial() -> None:
    tier, reasons, _ = recommendation(
        document(
            "Make Long-Running NVIDIA TensorRT Engine Builds Observable and "
            "Cancelable in Python or C++",
            ["tutorial", "library-release"],
        )
    )

    assert tier == "core"
    assert reasons == ["technical_tutorial"]


def test_benchmark_led_analysis_uses_research_reason() -> None:
    tier, reasons, _ = recommendation(
        document(
            "NVIDIA Nemotron 3 Ultra Leads Open Models on Accuracy and Efficiency "
            "in Agentic RTL Coding",
            ["engineering-analysis"],
        )
    )

    assert tier == "core"
    assert reasons == ["research_or_benchmark"]


def test_platform_model_availability_uses_release_reason() -> None:
    tier, reasons, _ = recommendation(
        document(
            "Get started with OpenAI GPT-5.6 Sol, Terra, and Luna on Amazon Bedrock",
            ["engineering-analysis"],
        )
    )

    assert tier == "core"
    assert reasons == ["technical_release_or_change"]
