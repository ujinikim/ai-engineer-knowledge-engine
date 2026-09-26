import pytest
import json
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.model_usage import ModelUsage
from app.services.article_relevance import (
    RELEVANCE_POLICY_VERSION,
    ArticleRelevanceService,
)


def test_relevance_classification_uses_strict_agent_engineering_schema() -> None:
    usage = ModelUsage()
    service = ArticleRelevanceService.__new__(ArticleRelevanceService)
    service.model = "gpt-test"
    service.usage = usage
    service.client = Mock()
    service.client.chat.completions.create.return_value = SimpleNamespace(
        usage=SimpleNamespace(prompt_tokens=30, completion_tokens=10),
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "relevance_tier": "contextual",
                            "relevance_reason": "A foundation-model release informs agent builders.",
                            "agent_focus": "supporting",
                            "agent_evidence_quote": "",
                        }
                    )
                )
            )
        ],
    )

    decision = service.classify(
        title="Foundation model release",
        raw_text="A new general-purpose foundation model is available.",
    )

    assert decision.tier == "contextual"
    assert decision.status == "classified"
    assert decision.generated_by == "gpt-test"
    assert decision.agent_focus == "supporting"
    assert decision.metadata()["relevance_policy_version"] == RELEVANCE_POLICY_VERSION
    response_format = service.client.chat.completions.create.call_args.kwargs["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True
    assert usage.chat_input_tokens == 30


def test_relevance_failure_is_unclassified() -> None:
    service = ArticleRelevanceService.__new__(ArticleRelevanceService)
    service.model = "gpt-test"
    service.usage = None
    service.client = Mock()
    service.client.chat.completions.create.side_effect = RuntimeError("unavailable")

    decision = service.classify(title="Unknown update", raw_text="Unknown update")

    assert decision.tier is None
    assert decision.status == "failed"
    assert decision.generated_by == "classification-error"
    assert "pending retry" in decision.reason.lower()


def test_unsupported_core_claim_is_deterministically_demoted() -> None:
    service = ArticleRelevanceService.__new__(ArticleRelevanceService)
    service.model = "gpt-test"
    service.usage = None
    service.client = Mock()
    service.client.chat.completions.create.return_value = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "relevance_tier": "core",
                            "relevance_reason": "Kernel tuning supports agent computation.",
                            "agent_focus": "central",
                            "agent_evidence_quote": "AI agent computation kernels",
                        }
                    )
                )
            )
        ],
    )

    decision = service.classify(
        title="Helion on TPU",
        raw_text="Helion generates and tunes performant TPU kernels.",
    )

    assert decision.tier == "contextual"
    assert decision.status == "corrected_unsupported_core"


def test_core_claim_accepts_an_exact_agent_evidence_quote() -> None:
    service = ArticleRelevanceService.__new__(ArticleRelevanceService)
    service.model = "gpt-test"
    service.usage = None
    service.client = Mock()
    service.client.chat.completions.create.return_value = SimpleNamespace(
        usage=None,
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(
                    content=json.dumps(
                        {
                            "relevance_tier": "core",
                            "relevance_reason": "The article evaluates production AI agents.",
                            "agent_focus": "central",
                            "agent_evidence_quote": "evaluating production AI agents",
                        }
                    )
                )
            )
        ],
    )

    decision = service.classify(
        title="Agent evaluation",
        raw_text="A practical pipeline for evaluating production AI agents before deployment.",
    )

    assert decision.tier == "core"
    assert decision.status == "classified"


@pytest.mark.parametrize(
    ("raw_text", "quote"),
    [
        ("To\nbuild effective agents\n, they need unlimited tool libraries.", "To build effective agents, they need unlimited tool libraries."),
        ("We\u2019re launching the agent harness today.", "\"We're launching the agent harness today\""),
        ("Codex will keep looping until the goal is done... or the budget runs out.", "Codex will keep looping... or the budget runs out"),
        ("MCP Apps is now live as the first official MCP extension for interactive agent tools.", "MCP Apps are now live as an official MCP extension for interactive agent tools"),
    ],
)
def test_quote_check_tolerates_formatting_and_light_paraphrase(raw_text: str, quote: str) -> None:
    assert ArticleRelevanceService._quote_is_supported("Title", raw_text, quote)


@pytest.mark.parametrize(
    "quote",
    ["", "Title", "agents orchestrate tool calls with persistent memory", "Helion... agent planning loops"],
)
def test_quote_check_rejects_unsupported_or_trivial_quotes(quote: str) -> None:
    assert not ArticleRelevanceService._quote_is_supported(
        "Title", "Helion generates and tunes performant TPU kernels.", quote
    )
