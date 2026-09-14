import json
from types import SimpleNamespace
from unittest.mock import Mock

from app.core.model_usage import ModelUsage
from app.services.article_relevance import (
    RELEVANCE_POLICY_VERSION,
    ArticleRelevanceService,
    relevance_is_visible,
    stored_relevance_tier,
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


def test_relevance_failure_is_explicit_and_fails_open_to_core() -> None:
    service = ArticleRelevanceService.__new__(ArticleRelevanceService)
    service.model = "gpt-test"
    service.usage = None
    service.client = Mock()
    service.client.chat.completions.create.side_effect = RuntimeError("unavailable")

    decision = service.classify(title="Unknown update", raw_text="Unknown update")

    assert decision.tier == "core"
    assert decision.status == "fail_open"
    assert decision.generated_by == "fail-open"
    assert "retained in core for review" in decision.reason.lower()


def test_legacy_relevance_is_core_and_excluded_is_never_visible() -> None:
    assert stored_relevance_tier({}) == "core"
    assert relevance_is_visible({}) is True
    assert relevance_is_visible({"relevance_tier": "contextual"}) is False
    assert relevance_is_visible(
        {"relevance_tier": "contextual"},
        include_contextual=True,
    )
    assert not relevance_is_visible(
        {"relevance_tier": "excluded"},
        include_contextual=True,
    )


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
