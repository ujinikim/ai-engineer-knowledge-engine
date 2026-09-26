import json
import logging
import re
from dataclasses import dataclass

from openai import OpenAI

from app.core.settings import settings
from app.core.model_usage import ModelUsage
from app.core.structured_logging import get_logger, log_event
from app.services.taxonomy import (
    EVENT_TYPES,
    PRIMARY_TOPICS,
    TAXONOMY_POLICY_VERSION,
    clean_labels,
    classify_topic_with_method,
    infer_event_types,
)
from app.services.source_detail import classify_content_detail


logger = get_logger("summarization")

CATEGORY_DESCRIPTIONS = {
    "agentic-generative-ai": "LLMs, foundation models, agents, orchestration, tool use, and generative applications",
    "machine-learning-classical-ai": "machine learning, deep learning, reinforcement learning, training, optimization, and symbolic AI",
    "vision-speech-robotics": "computer vision, image or video, audio, speech, multimodal systems, and robotics",
    "data-search-retrieval": "RAG, embeddings, vector databases, knowledge graphs, datasets, indexing, and search",
    "ai-products-engineering-infrastructure": "AI products, APIs, SDKs, developer tools, inference, deployment, hardware, and production systems",
    "safety-evaluation-governance": "benchmarks, evaluations, security, alignment, interpretability, reliability, and governance",
}

EVENT_DESCRIPTIONS = {
    "release-update": "a launch, release, product update, API change, integration, or pricing change",
    "research": "a paper, experiment, benchmark result, or other new research finding",
    "guide": "a tutorial, walkthrough, or practical how-to",
    "analysis": "an explanation, opinion, survey, or engineering analysis",
    "alert": "a vulnerability, security issue, incident, outage, deprecation, or breaking change",
}

CATEGORY_SELECTION_GUIDANCE = (
    "Classify the article's main theme: the activity, problem, or contribution it "
    "primarily explains. Do not classify from an organization, product, model, agent, "
    "or platform name that is merely the setting. Prefer safety-evaluation-governance "
    "when the main theme is measuring quality, benchmarking, guardrails, detecting "
    "failures, reliability, security, content safeguards, or governance, even when the "
    "evaluated system is an agent or LLM. Prefer data-search-retrieval when the main "
    "theme is designing or measuring an information-retrieval, RAG, indexing, embedding, "
    "or search component, even when an LLM uses that component. Prefer "
    "ai-products-engineering-infrastructure for deployment, serving, accelerators, TPU or "
    "GPU kernel authoring, runtimes, SDKs, and production architecture; using an AWS or "
    "other cloud product does not by itself make the article infrastructure. Prefer "
    "machine-learning-classical-ai when the main contribution is a recommendation, "
    "prediction, classification, training, or optimization method. Use "
    "agentic-generative-ai when generating content, foundation models, or agent behavior "
    "is itself the main theme."
)

EVENT_SELECTION_GUIDANCE = (
    "Choose the event describing why the article exists. Use release-update only when "
    "the central claim announces a newly available product, version, capability, API "
    "change, integration, or pricing change. A product mention does not make an article "
    "a release. Prefer guide when the article is organized around instructions, setup, "
    "best practices, or 'get started' steps, even if it discusses a recently released "
    "product. Prefer research for a study or reported experiment. Prefer analysis for an "
    "explanation, editorial report, architecture discussion, or customer case study. Use "
    "alert for an incident, vulnerability, breaking change, or deprecation."
)

TAXONOMY_BOUNDARY_EXAMPLES = (
    "Boundary examples: Applying Bedrock Guardrails to generated code has main theme "
    "'applying safety controls to generated code', category safety-evaluation-governance, "
    "and event guide. Deploying and scaling a guardrail service has main theme 'operating "
    "a production guardrail service', category ai-products-engineering-infrastructure, "
    "and event guide. Measuring whether agents complete tasks correctly has category "
    "safety-evaluation-governance; announcing a new agent model has category "
    "agentic-generative-ai and event release-update."
)

ARTICLE_SUMMARY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_summary",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "display_headline": {"type": "string"},
                "summary": {"type": "string"},
                "why_it_matters": {"type": "string"},
                "key_points": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "main_theme": {"type": "string"},
                "primary_topic": {"type": "string", "enum": list(PRIMARY_TOPICS)},
                "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
            },
            "required": [
                "display_headline",
                "summary",
                "why_it_matters",
                "key_points",
                "main_theme",
                "primary_topic",
                "event_type",
            ],
            "additionalProperties": False,
        },
    },
}

MAIN_THEME_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_main_theme",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "main_theme": {"type": "string"},
            },
            "required": ["main_theme"],
            "additionalProperties": False,
        },
    },
}

CATEGORY_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_category",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "primary_topic": {"type": "string", "enum": list(PRIMARY_TOPICS)},
                "classification_reason": {"type": "string"},
            },
            "required": [
                "primary_topic",
                "classification_reason",
            ],
            "additionalProperties": False,
        },
    },
}

EVENT_RESPONSE_FORMAT = {
    "type": "json_schema",
    "json_schema": {
        "name": "article_event",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "event_type": {"type": "string", "enum": list(EVENT_TYPES)},
                "event_reason": {"type": "string"},
            },
            "required": ["event_type", "event_reason"],
            "additionalProperties": False,
        },
    },
}


def shorten_at_word_boundary(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    available = limit - 3
    candidate = value[:available].rstrip()
    if " " in candidate:
        word_boundary = candidate.rfind(" ")
        if word_boundary >= max(available // 2, 1):
            candidate = candidate[:word_boundary].rstrip()
    return candidate + "..."


@dataclass(frozen=True)
class ArticleSummary:
    display_headline: str
    summary: str
    why_it_matters: str
    key_points: list[str]
    primary_topic: str
    event_types: list[str]
    generated_by: str

    def fields(self) -> dict:
        return {
            "display_headline": self.display_headline,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "key_points": self.key_points,
            "primary_topic": self.primary_topic,
            "event_types": self.event_types,
            "summary_generated_by": self.generated_by,
            "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
        }


class ArticleSummaryService:
    def __init__(self, usage: ModelUsage | None = None, model: str | None = None) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.usage = usage
        self.model = model or settings.chat_model

    def summarize(
        self,
        *,
        title: str,
        raw_text: str,
        organization: str,
        tool: str,
        source_type: str,
        default_topic: str,
        default_event_types: list[str],
    ) -> ArticleSummary:
        fallback = self._fallback(
            title=title,
            raw_text=raw_text,
            organization=organization,
            tool=tool,
            default_topic=default_topic,
            default_event_types=default_event_types,
        )
        if not self.client:
            return fallback

        detail_level = self._source_detail_level(title, raw_text)
        model = getattr(self, "model", settings.chat_model)
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": self._system_prompt(),
                    },
                    {
                        "role": "user",
                        "content": self._user_prompt(
                            title=title,
                            raw_text=raw_text,
                            organization=organization,
                            tool=tool,
                            source_type=source_type,
                            detail_level=detail_level,
                        ),
                    },
                ],
                response_format=ARTICLE_SUMMARY_RESPONSE_FORMAT,
                temperature=0.1,
                max_completion_tokens=450,
            )
            if self.usage and response.usage:
                self.usage.record_chat(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )
            payload = json.loads(response.choices[0].message.content or "{}")
            return self._validated(
                payload,
                fallback,
                source_type,
                title=title,
                raw_text=raw_text,
            )
        except Exception as error:
            log_event(
                logger,
                "summary_generation_fallback",
                level=logging.WARNING,
                model=model,
                source_type=source_type,
                tool=tool,
                exception_type=type(error).__name__,
            )
            return fallback

    def _system_prompt(self) -> str:
        return (
            "Turn one source article into a concise AI-engineering feed card. "
            "Return the required structured fields for a concise AI-engineering feed card. "
            "Use only facts stated in the supplied source. Do not infer benefits, outcomes, "
            "motivations, severity, or broader effects. In particular, do not claim improved "
            "reliability, stability, performance, security, usability, efficiency, scalability, "
            "or productivity unless the source explicitly states that improvement. Do not add "
            "recommendations such as \"users should update\" or guarantees such as \"users will "
            "no longer experience errors\" unless the source states them. Preserve qualifications "
            "and uncertainty. A plausible conclusion is still unsupported when the source does "
            "not state it. "
            "The headline must state the concrete update, avoid promotional language, and stay "
            "under 90 characters. The summary must be 1-2 sentences under 70 words and describe "
            "what changed, who or what is affected, and any stated conditions. Why_it_matters "
            "must be one sentence under 35 words. Prefer the affected user, component, workflow, "
            "compatibility condition, or required action over a general benefit. When no broader "
            "impact is stated, describe only the affected scope. When even the affected scope is "
            "unclear, use: \"The source does not provide enough detail to assess broader impact.\" "
            "Return 2-4 short, distinct key_points supported by the source; do not pad the list "
            "with inferred benefits. Select exactly one broad primary_topic for the article's "
            "central subject, not every technology it mentions. The configured defaults are weak "
            "fallbacks only; classify from the article whenever it contains enough evidence. "
            f"{CATEGORY_SELECTION_GUIDANCE} "
            "Before selecting a category, write main_theme as one short sentence describing "
            "what the article primarily teaches, investigates, measures, announces, or warns about. "
            f"{TAXONOMY_BOUNDARY_EXAMPLES} "
            "Select exactly one event type for the article's central event. "
            f"{EVENT_SELECTION_GUIDANCE} A security-related "
            "feature is not an alert unless the "
            "source describes a vulnerability, security defect, or disclosed threat. Availability "
            "on several product surfaces is not itself an alert. "
            f"Category definitions: {CATEGORY_DESCRIPTIONS}. "
            f"Event definitions: {EVENT_DESCRIPTIONS}."
        )

    def _user_prompt(
        self,
        *,
        title: str,
        raw_text: str,
        organization: str,
        tool: str,
        source_type: str,
        detail_level: str,
    ) -> str:
        sparse_instructions = ""
        if detail_level == "sparse":
            sparse_instructions = (
                "\nSparse-source instructions:\n"
                "- Use near-extractive wording.\n"
                "- Do not infer the purpose or effect of a fix from its component name.\n"
                "- Do not expand abbreviations unless the source defines them.\n"
                "- Do not add generic product benefits.\n"
                "- Do not recommend an action or promise that a problem is fully resolved.\n"
                "- For why_it_matters, prefer the neutral form: \"The change applies to users "
                "of [the explicitly named component or workflow].\"\n"
                "- It is acceptable for every field to be brief.\n"
                "Example: for \"Fix query errors when using shard keys while resharding,\" "
                "say the fix is relevant to users combining shard keys with resharding; do not "
                "claim it improves general reliability or distributed consistency.\n"
            )
        return (
            f"Organization: {organization}\n"
            f"Tool: {tool}\n"
            f"Source type: {source_type}\n"
            f"Source detail level: {detail_level}\n"
            f"Title: {title}\n"
            f"{sparse_instructions}\n"
            f"Source text:\n{raw_text[:12000]}"
        )

    def _source_detail_level(self, title: str, raw_text: str) -> str:
        return classify_content_detail(title, raw_text)

    def _validated(
        self,
        payload: dict,
        fallback: ArticleSummary,
        source_type: str,
        *,
        title: str,
        raw_text: str,
    ) -> ArticleSummary:
        primary_topic = str(payload.get("primary_topic") or fallback.primary_topic).strip().lower()
        if primary_topic not in PRIMARY_TOPICS:
            primary_topic = fallback.primary_topic
        model_event = payload.get("event_type")
        event_types = clean_labels(
            [model_event] if model_event else payload.get("event_types"),
            EVENT_TYPES,
            limit=1,
        )
        if not event_types:
            event_types = fallback.event_types

        return ArticleSummary(
            display_headline=self._text(payload.get("display_headline"), fallback.display_headline, 90),
            summary=self._text(payload.get("summary"), fallback.summary, 600),
            why_it_matters=self._text(payload.get("why_it_matters"), fallback.why_it_matters, 320),
            key_points=self._text_list(payload.get("key_points"), fallback.key_points, 4, 180),
            primary_topic=primary_topic,
            event_types=event_types,
            generated_by=f"{getattr(self, 'model', settings.chat_model)}:{source_type}",
        )

    def _fallback(
        self,
        *,
        title: str,
        raw_text: str,
        organization: str,
        tool: str,
        default_topic: str,
        default_event_types: list[str],
    ) -> ArticleSummary:
        body = raw_text.removeprefix(title).strip()
        compact = " ".join(body.split())
        sentences = re.split(r"(?<=[.!?])\s+", compact)
        summary = " ".join(sentences[:2]).strip() or title
        primary_topic, _ = classify_topic_with_method(
            f"{title}\n{title}\n{raw_text}",
            default_topic,
        )
        events = infer_event_types(raw_text, default_event_types)
        return ArticleSummary(
            display_headline=self._truncate(title, 90),
            summary=self._truncate(summary, 500),
            why_it_matters="Review the source for implementation details and compatibility impact.",
            key_points=[self._truncate(sentence, 160) for sentence in sentences[:3] if sentence][:3],
            primary_topic=primary_topic,
            event_types=events or ["analysis"],
            generated_by="deterministic-fallback",
        )

    def classify_taxonomy(
        self,
        *,
        title: str,
        raw_text: str,
        default_topic: str,
        default_event_types: list[str],
    ) -> tuple[
        str,
        list[str],
        str,
        str | None,
        str | None,
        None,
        None,
        str | None,
    ]:
        """Classify theme, category, and event; relevance is handled upstream."""
        fallback_topic, fallback_method = classify_topic_with_method(
            f"{title}\n{title}\n{raw_text}",
            default_topic,
        )
        fallback_events = infer_event_types(raw_text, default_event_types) or ["analysis"]
        if not self.client:
            return (
                fallback_topic,
                fallback_events[:1],
                fallback_method,
                None,
                "Model classification unavailable; deterministic fallback used.",
                None,
                None,
                None,
            )

        try:
            theme_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._main_theme_prompt()},
                    {
                        "role": "user",
                        "content": (
                            f"Title: {title}\n\nSource text:\n{raw_text[:12000]}"
                        ),
                    },
                ],
                response_format=MAIN_THEME_RESPONSE_FORMAT,
                temperature=0.1,
                max_completion_tokens=220,
            )
            if self.usage and theme_response.usage:
                self.usage.record_chat(
                    theme_response.usage.prompt_tokens,
                    theme_response.usage.completion_tokens,
                )
            theme_payload = json.loads(theme_response.choices[0].message.content or "{}")
            main_theme = self._text(theme_payload.get("main_theme"), "", 180)
            if not main_theme:
                return (
                    fallback_topic,
                    fallback_events[:1],
                    fallback_method,
                    None,
                    "Main-theme gate returned no usable decision.",
                    None,
                    None,
                    None,
                )

            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._taxonomy_prompt()},
                    {
                        "role": "user",
                        "content": f"Title: {title}\nMain theme: {main_theme}",
                    },
                ],
                response_format=CATEGORY_RESPONSE_FORMAT,
                temperature=0.1,
                max_completion_tokens=140,
            )
            if self.usage and response.usage:
                self.usage.record_chat(
                    response.usage.prompt_tokens,
                    response.usage.completion_tokens,
                )
            payload = json.loads(response.choices[0].message.content or "{}")
            topic = str(payload.get("primary_topic") or "").strip().lower()
            reason = self._text(payload.get("classification_reason"), "", 240)
            if topic not in PRIMARY_TOPICS or not reason:
                return (
                    fallback_topic,
                    fallback_events[:1],
                    fallback_method,
                    main_theme,
                    "Category gate returned an invalid structured result.",
                    None,
                    None,
                    None,
                )

            event_response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self._event_prompt()},
                    {
                        "role": "user",
                        "content": f"Title: {title}\nMain theme: {main_theme}",
                    },
                ],
                response_format=EVENT_RESPONSE_FORMAT,
                temperature=0.1,
                max_completion_tokens=100,
            )
            if self.usage and event_response.usage:
                self.usage.record_chat(
                    event_response.usage.prompt_tokens,
                    event_response.usage.completion_tokens,
                )
            event_payload = json.loads(
                event_response.choices[0].message.content or "{}"
            )
            events = clean_labels(
                [event_payload.get("event_type")],
                EVENT_TYPES,
                limit=1,
            )
            event_reason = self._text(event_payload.get("event_reason"), "", 240)
            if not events or not event_reason:
                events = fallback_events[:1]
                event_reason = "Event gate failed; deterministic fallback used."
            return (
                topic,
                events,
                self.model,
                main_theme,
                reason,
                None,
                None,
                event_reason,
            )
        except Exception as error:
            log_event(
                logger,
                "taxonomy_generation_fallback",
                level=logging.WARNING,
                model=self.model,
                exception_type=type(error).__name__,
            )
            return (
                fallback_topic,
                fallback_events[:1],
                fallback_method,
                None,
                "Model classification failed; deterministic fallback used.",
                None,
                None,
                None,
            )

    def _main_theme_prompt(self) -> str:
        return (
            "Identify what the article primarily "
            "teaches, investigates, measures, announces, or warns about as one concrete "
            "main_theme sentence based only on the source. Describe the subject and activity, "
            "not the publisher, product setting, or relevance tier. Do not classify whether the "
            "article belongs in the feed; that decision was made upstream. Do not select or "
            "mention a taxonomy category. Do not add benefits, improvements, "
            "severity, or outcomes unless the source explicitly states them."
        )

    def _taxonomy_prompt(self) -> str:
        return (
            "Classify the supplied title and main theme into exactly one broad category. You do "
            "not have the full article, publisher, source default, or product "
            "metadata. State a short classification_reason grounded in the supplied theme. "
            f"{CATEGORY_SELECTION_GUIDANCE} "
            f"{TAXONOMY_BOUNDARY_EXAMPLES} "
            f"Category definitions: {CATEGORY_DESCRIPTIONS}."
        )

    def _event_prompt(self) -> str:
        return (
            "Classify the supplied title and main theme into exactly one event type. State a "
            "short event_reason grounded in the supplied text. "
            f"{EVENT_SELECTION_GUIDANCE} Event definitions: {EVENT_DESCRIPTIONS}."
        )

    def _text(self, value: object, fallback: str, limit: int) -> str:
        text = " ".join(str(value or "").split())
        return self._truncate(text, limit) if text else fallback

    def _text_list(self, value: object, fallback: list[str], count: int, limit: int) -> list[str]:
        if not isinstance(value, list):
            return fallback
        items = [self._truncate(" ".join(str(item).split()), limit) for item in value if str(item).strip()]
        return items[:count] or fallback

    def _truncate(self, value: str, limit: int) -> str:
        return shorten_at_word_boundary(value, limit)
