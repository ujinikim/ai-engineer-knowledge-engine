from app.ingestion.summary import ArticleSummaryService


def test_deterministic_summary_keeps_source_facts() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    service.model = "gpt-test"
    article = service._fallback(
        title="vLLM adds prefill controls",
        raw_text=(
            "vLLM adds prefill controls\n\n"
            "The release adds throttled prefill scheduling. It also improves KV cache handling."
        ),
        default_topic="ai-products-engineering-infrastructure",
        default_event_types=["release-update"],
    )

    assert article.primary_topic == "ai-products-engineering-infrastructure"
    assert article.display_headline == "vLLM adds prefill controls"
    assert "throttled prefill" in article.summary
    assert article.event_types == ["release-update"]


def test_generated_and_fallback_headlines_are_capped_at_90_characters() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    service.model = "gpt-test"
    long_title = (
        "PyTorch 2.13 adds FlexAttention on Apple Silicon and introduces a new "
        "distributed communications backend"
    )
    fallback = service._fallback(
        title=long_title,
        raw_text=f"{long_title}\n\nThe release adds two documented runtime capabilities.",
        default_topic="training-fine-tuning",
        default_event_types=["library-release"],
    )
    validated = service._validated(
        {"display_headline": long_title},
        fallback,
        "official-release",
    )

    assert len(fallback.display_headline) <= 90
    assert len(validated.display_headline) <= 90
    assert fallback.display_headline.endswith("...")
    assert validated.display_headline.endswith("...")


def test_validated_taxonomy_has_one_category_and_one_event() -> None:
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    service.model = "gpt-test"
    fallback = service._fallback(
        title="Agent tool-use research",
        raw_text="Agent tool-use research\n\nA research paper studies tool use by agents.",
        default_topic="agentic-generative-ai",
        default_event_types=["research"],
    )

    validated = service._validated(
        {
            "primary_topic": "agentic-generative-ai",
            "event_types": ["research", "analysis"],
        },
        fallback,
        "research-paper",
    )

    assert validated.primary_topic == "agentic-generative-ai"
    assert validated.event_types == ["research"]
    assert "topic_tags" not in validated.fields()
