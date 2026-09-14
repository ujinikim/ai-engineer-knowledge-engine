import json
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.model_usage import (
    ModelUsage,
    estimate_chat_cost_usd,
    estimate_embedding_cost_usd,
)
from app.services.article_summary import ArticleSummaryService
from app.services.embedding import EmbeddingService


def test_known_model_costs_and_snapshots_are_estimated() -> None:
    assert estimate_chat_cost_usd("gpt-4.1-mini", 1_000_000, 1_000_000) == 2.0
    assert estimate_chat_cost_usd("gpt-4.1-mini-2025-04-14", 500_000, 250_000) == 0.6
    assert estimate_embedding_cost_usd("text-embedding-3-small", 1_000_000) == 0.02


def test_unknown_model_does_not_receive_a_misleading_cost() -> None:
    usage = ModelUsage(chat_input_tokens=100, chat_output_tokens=20, embedding_tokens=50)

    assert usage.estimated_cost_usd("unknown-chat", "text-embedding-3-small") is None
    assert usage.estimated_cost_usd("gpt-4.1-mini", "unknown-embedding") is None


def test_summary_service_records_api_usage_without_recording_prompt_text() -> None:
    usage = ModelUsage()
    service = ArticleSummaryService.__new__(ArticleSummaryService)
    service.usage = usage
    service.client = Mock()
    service.client.chat.completions.create.return_value = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=120, completion_tokens=30),
        choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps({})))],
    )

    service.summarize(
        title="Release 1.0",
        raw_text="Release 1.0 adds a documented option.",
        organization="Example",
        tool="Example SDK",
        source_type="official-release",
        default_topic="ai-products-engineering-infrastructure",
        default_event_types=["release-update"],
    )

    assert usage.chat_input_tokens == 120
    assert usage.chat_output_tokens == 30
    response_format = service.client.chat.completions.create.call_args.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    event_schema = response_format["json_schema"]["schema"]["properties"]["event_type"]
    assert event_schema["enum"] == ["release-update", "research", "guide", "analysis", "alert"]


def test_embedding_service_records_api_usage() -> None:
    usage = ModelUsage()
    service = EmbeddingService.__new__(EmbeddingService)
    service.usage = usage
    service.client = Mock()
    service.client.embeddings.create.return_value = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=18, total_tokens=18),
        data=[SimpleNamespace(embedding=[0.1, 0.2])],
    )

    assert service.embed_texts(["safe input"]) == [[0.1, 0.2]]
    assert usage.embedding_tokens == 18
