import json
import re
from dataclasses import dataclass

from openai import OpenAI

from app.core.settings import settings
from app.services.taxonomy import (
    EVENT_TYPES,
    PRIMARY_TOPICS,
    clean_labels,
    clean_tags,
    classify_topic,
    infer_event_types,
    infer_maturity,
)
from app.services.source_detail import classify_content_detail


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
    topic_tags: list[str]
    event_types: list[str]
    entity_tags: list[str]
    maturity: str
    generated_by: str

    def metadata(self) -> dict:
        return {
            "display_headline": self.display_headline,
            "summary": self.summary,
            "why_it_matters": self.why_it_matters,
            "key_points": self.key_points,
            "primary_topic": self.primary_topic,
            "topic_tags": self.topic_tags,
            "event_types": self.event_types,
            "entity_tags": self.entity_tags,
            "maturity": self.maturity,
            "summary_generated_by": self.generated_by,
        }


class ArticleSummaryService:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

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
        try:
            response = self.client.chat.completions.create(
                model=settings.chat_model,
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
                            default_topic=default_topic,
                            default_event_types=default_event_types,
                            detail_level=detail_level,
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_completion_tokens=450,
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            return self._validated(
                payload,
                fallback,
                source_type,
                title=title,
                raw_text=raw_text,
            )
        except Exception:
            return fallback

    def _system_prompt(self) -> str:
        return (
            "Turn one source article into a concise AI-engineering feed card. "
            "Return JSON with display_headline, summary, why_it_matters, key_points, "
            "primary_topic, topic_tags, event_types, and entity_tags. "
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
            "with inferred benefits. Treat the configured default topic and event types as strong "
            "priors and override them only when the source clearly supports another value. Choose "
            "only event types that are materially represented by the article; do not add a second "
            "event merely because it is loosely related. Support for a model inside a library is "
            "not a model launch. A security-related feature is not a security issue unless the "
            "source describes a vulnerability, security defect, or disclosed threat. Availability "
            "on several product surfaces is not an integration unless separate systems are "
            "explicitly connected. "
            f"primary_topic from {list(PRIMARY_TOPICS)} and event_types from {list(EVENT_TYPES)}."
        )

    def _user_prompt(
        self,
        *,
        title: str,
        raw_text: str,
        organization: str,
        tool: str,
        source_type: str,
        default_topic: str,
        default_event_types: list[str],
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
            f"Default topic: {default_topic}\n"
            f"Default event types: {default_event_types}\n"
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
        event_types = clean_labels(payload.get("event_types"), EVENT_TYPES, limit=5)
        if not event_types:
            event_types = fallback.event_types

        return ArticleSummary(
            display_headline=self._text(payload.get("display_headline"), fallback.display_headline, 90),
            summary=self._text(payload.get("summary"), fallback.summary, 600),
            why_it_matters=self._text(payload.get("why_it_matters"), fallback.why_it_matters, 320),
            key_points=self._text_list(payload.get("key_points"), fallback.key_points, 4, 180),
            primary_topic=primary_topic,
            topic_tags=clean_tags(payload.get("topic_tags")) or fallback.topic_tags,
            event_types=event_types,
            entity_tags=clean_tags(payload.get("entity_tags")) or fallback.entity_tags,
            maturity=infer_maturity(title, raw_text, event_types),
            generated_by=f"{settings.chat_model}:{source_type}",
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
        primary_topic, secondary_topics = classify_topic(raw_text, default_topic)
        events = infer_event_types(raw_text, default_event_types)
        return ArticleSummary(
            display_headline=self._truncate(title, 90),
            summary=self._truncate(summary, 500),
            why_it_matters="Review the source for implementation details and compatibility impact.",
            key_points=[self._truncate(sentence, 160) for sentence in sentences[:3] if sentence][:3],
            primary_topic=primary_topic,
            topic_tags=secondary_topics,
            event_types=events or ["library-release"],
            entity_tags=clean_tags([organization, tool]),
            maturity=infer_maturity(title, raw_text, events),
            generated_by="deterministic-fallback",
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
