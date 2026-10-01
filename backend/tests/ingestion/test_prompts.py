from app.ingestion.content_detail import classify_content_detail
from app.ingestion.prompts import (
    MAIN_THEME_RESPONSE_FORMAT,
    category_prompt,
    event_prompt,
    main_theme_prompt,
    summary_user_prompt,
)


def test_taxonomy_prompt_prioritizes_main_theme_over_product_mentions() -> None:
    prompt = category_prompt()
    events_prompt = event_prompt()

    assert "main theme" in prompt
    assert "merely the setting" in prompt
    assert "A product mention does not make an article a release" in events_prompt
    assert "detecting failures" in prompt
    assert "TPU or GPU kernel authoring" in prompt
    assert "recommendation, prediction, classification" in prompt
    assert "'get started' steps" in events_prompt


def test_main_theme_prompt_does_not_repeat_relevance_classification() -> None:
    prompt = main_theme_prompt()

    assert "main_theme" in prompt
    assert "decision was made upstream" in prompt
    assert "Do not classify whether the article belongs in the feed" in prompt
    assert "Core requires" not in prompt
    schema = MAIN_THEME_RESPONSE_FORMAT["json_schema"]["schema"]
    assert list(schema["properties"]) == ["main_theme"]


def test_sparse_source_prompt_prohibits_speculative_benefits() -> None:
    raw_text = "v1.18.3\n\nFix query errors when using shard keys while resharding."

    detail_level = classify_content_detail("v1.18.3", raw_text)
    prompt = summary_user_prompt(
        title="v1.18.3",
        raw_text=raw_text,
        organization="Qdrant",
        tool="Qdrant",
        source_type="official-release",
        detail_level=detail_level,
    )

    assert detail_level == "sparse"
    assert "Use near-extractive wording" in prompt
    assert "do not claim it improves general reliability" in prompt
    assert "Do not recommend an action" in prompt
    assert "The change applies to users" in prompt
    assert "Default topic" not in prompt
    assert "Default event" not in prompt


def test_detailed_source_does_not_receive_sparse_instructions() -> None:
    body = "\n".join(
        [
            "The release adds a new cache implementation for production inference workloads.",
            "Production tests reduced median latency by 25 percent across three deployments.",
            "Operators can enable the cache through the existing runtime configuration.",
            "The source provides benchmark methodology and compatibility details for adopters.",
            "Compatibility is documented for existing deployments using the prior cache configuration.",
            "The release notes also identify rollout steps and the supported runtime versions.",
        ]
    )
    raw_text = f"Runtime cache release\n\n{body}"

    detail_level = classify_content_detail("Runtime cache release", raw_text)
    prompt = summary_user_prompt(
        title="Runtime cache release",
        raw_text=raw_text,
        organization="Example",
        tool="Runtime",
        source_type="official-engineering-blog",
        detail_level=detail_level,
    )

    assert detail_level == "detailed"
    assert "Sparse-source instructions" not in prompt
    assert "Production tests reduced median latency" in prompt
