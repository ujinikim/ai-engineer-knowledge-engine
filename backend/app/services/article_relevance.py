import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from app.core.model_usage import ModelUsage
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event


logger = get_logger("relevance")

RELEVANCE_POLICY_VERSION = "2026-09-13-agent-engineering-v2"
RELEVANCE_TIERS = ("core", "contextual", "excluded")

RELEVANCE_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_relevance",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "relevance_tier": {"type": "string", "enum": list(RELEVANCE_TIERS)},
                "relevance_reason": {"type": "string"},
                "agent_focus": {
                    "type": "string",
                    "enum": ["central", "supporting", "absent"],
                },
                "agent_evidence_quote": {"type": "string"},
            },
            "required": [
                "relevance_tier",
                "relevance_reason",
                "agent_focus",
                "agent_evidence_quote",
            ],
            "additionalProperties": False,
        },
    },
}


@dataclass(frozen=True)
class RelevanceDecision:
    tier: str | None
    reason: str
    generated_by: str
    status: str = "classified"
    agent_focus: str = "absent"
    agent_evidence_quote: str = ""

    def metadata(self) -> dict[str, str | None]:
        return {
            "relevance_tier": self.tier,
            "relevance_reason": self.reason,
            "relevance_generated_by": self.generated_by,
            "relevance_policy_version": RELEVANCE_POLICY_VERSION,
            "relevance_classification_status": self.status,
            "relevance_agent_focus": self.agent_focus,
            "relevance_agent_evidence_quote": self.agent_evidence_quote,
        }


class ArticleRelevanceService:
    def __init__(self, usage: ModelUsage | None = None, model: str | None = None) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.usage = usage
        self.model = model or settings.chat_model

    def classify(self, *, title: str, raw_text: str) -> RelevanceDecision:
        if not self.client:
            return self._unclassified("Model relevance classification is unavailable.")

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._prompt()},
                    {
                        "role": "user",
                        "content": f"Title: {title}\n\nSource text:\n{raw_text[:12000]}",
                    },
                ],
                response_format=RELEVANCE_RESPONSE_FORMAT,
                temperature=0.1,
                max_completion_tokens=260,
            )
            if self.usage and response.usage:
                self.usage.record_chat(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )
            payload = json.loads(response.choices[0].message.content or "{}")
            tier = str(payload.get("relevance_tier") or "").strip().lower()
            reason = self._shorten(
                " ".join(str(payload.get("relevance_reason") or "").split()),
                480,
            )
            agent_focus = str(payload.get("agent_focus") or "").strip().lower()
            evidence_quote = " ".join(
                str(payload.get("agent_evidence_quote") or "").split()
            )[:240]
            if (
                tier not in RELEVANCE_TIERS
                or not reason
                or agent_focus not in {"central", "supporting", "absent"}
            ):
                return self._unclassified("Model returned an invalid relevance decision.")
            if tier == "core" and (
                agent_focus != "central"
                or not self._quote_is_supported(title, raw_text, evidence_quote)
            ):
                return RelevanceDecision(
                    tier="contextual",
                    reason=(
                        "The model proposed core relevance without source-grounded evidence that "
                        "agent engineering is the central subject; demoted to contextual."
                    ),
                    generated_by=self.model,
                    status="corrected_unsupported_core",
                    agent_focus=agent_focus,
                    agent_evidence_quote=evidence_quote,
                )
            return RelevanceDecision(
                tier=tier,
                reason=reason,
                generated_by=self.model,
                agent_focus=agent_focus,
                agent_evidence_quote=evidence_quote,
            )
        except Exception as error:
            log_event(
                logger,
                "relevance_generation_failed",
                level=logging.WARNING,
                model=self.model,
                exception_type=type(error).__name__,
            )
            return self._unclassified("Model relevance classification failed.")

    def _unclassified(self, reason: str) -> RelevanceDecision:
        return RelevanceDecision(
            tier=None,
            reason=f"{reason} Classification pending retry.",
            generated_by="classification-error",
            status="failed",
        )

    @staticmethod
    def _quote_is_supported(title: str, raw_text: str, quote: str) -> bool:
        if not quote:
            return False
        normalized_source = " ".join(f"{title}\n{raw_text}".casefold().split())
        normalized_quote = " ".join(quote.casefold().split())
        return len(normalized_quote) >= 8 and normalized_quote in normalized_source

    @staticmethod
    def _shorten(value: str, limit: int) -> str:
        if len(value) <= limit:
            return value
        shortened = value[: limit - 3].rsplit(" ", 1)[0].rstrip()
        return f"{shortened}..."

    @staticmethod
    def _prompt() -> str:
        return (
            "Route an article for a product narrowly focused on practical agent engineering. "
            "Choose core only when the article's central subject explicitly concerns engineers "
            "building, evaluating, "
            "secure, deploy, observe, or operate AI agents: agent frameworks and orchestration, "
            "tool use and MCP, planning and memory, agent-focused RAG, agent evaluations and "
            "guardrails, coding agents, or infrastructure specifically supporting agent systems. "
            "Choose contextual when the article is meaningfully useful background for agent "
            "engineers but is not principally about building or operating agents, such as a "
            "foundation-model release, general inference or training technique, AI accelerators "
            "or kernels, broad AI research, or policy "
            "with concrete technical implications. Choose excluded when the central subject has "
            "no meaningful agent-engineering connection, or is generic marketing, hiring, event "
            "promotion, business news, or unrelated software/cloud content. Judge the article, "
            "not the publisher. Never choose core merely because a model, kernel, accelerator, "
            "database, or general infrastructure technique could be used by agents. Do not invent "
            "an agent use case or call generic AI workloads agent workloads. For example, TPU "
            "kernel authoring is contextual unless the article itself centrally discusses agent "
            "systems; ray tracing is excluded; an agent evaluation pipeline is core. Set "
            "agent_focus to central only when agent engineering is the principal subject, "
            "supporting when it is explicit but secondary, and absent when it is not stated. For "
            "a core decision, copy a short exact quote from the title or source that proves the "
            "central agent focus into agent_evidence_quote. Otherwise return an empty quote. When "
            "genuinely uncertain between contextual and excluded, choose contextual. Give one "
            "concise reason grounded only in the article. For contextual content, describe its "
            "actual AI/ML engineering subject and explicitly note that it is not agent-specific; "
            "do not justify it with a hypothetical way agents or agent engineers might use it."
        )


def visible_relevance_tiers(*, include_contextual: bool = False) -> tuple[str, ...]:
    return ("core", "contextual") if include_contextual else ("core",)
