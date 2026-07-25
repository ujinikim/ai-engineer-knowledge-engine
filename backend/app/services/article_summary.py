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

        try:
            response = self.client.chat.completions.create(
                model=settings.chat_model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Turn one source article into a concise AI-engineering feed card. "
                            "Use only supplied facts. Return JSON with display_headline, summary, "
                            "why_it_matters, key_points, primary_topic, topic_tags, event_types, "
                            "and entity_tags. The headline must be factual and under 90 characters. "
                            "Summary must be 1-2 sentences under 70 words. Why_it_matters must be "
                            "one sentence under 35 words. Return 2-4 short key_points. Choose "
                            f"primary_topic from {list(PRIMARY_TOPICS)} and event_types from "
                            f"{list(EVENT_TYPES)}. Never add claims absent from the source."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Organization: {organization}\nTool: {tool}\n"
                            f"Source type: {source_type}\nDefault topic: {default_topic}\n"
                            f"Title: {title}\n\nSource text:\n{raw_text[:12000]}"
                        ),
                    },
                ],
                response_format={"type": "json_object"},
                temperature=0.1,
                max_completion_tokens=450,
            )
            payload = json.loads(response.choices[0].message.content or "{}")
            return self._validated(payload, fallback, source_type)
        except Exception:
            return fallback

    def _validated(
        self,
        payload: dict,
        fallback: ArticleSummary,
        source_type: str,
    ) -> ArticleSummary:
        primary_topic = str(payload.get("primary_topic") or fallback.primary_topic).strip().lower()
        if primary_topic not in PRIMARY_TOPICS:
            primary_topic = fallback.primary_topic
        event_types = clean_labels(payload.get("event_types"), EVENT_TYPES, limit=5)
        if not event_types:
            event_types = fallback.event_types

        return ArticleSummary(
            display_headline=self._text(payload.get("display_headline"), fallback.display_headline, 120),
            summary=self._text(payload.get("summary"), fallback.summary, 600),
            why_it_matters=self._text(payload.get("why_it_matters"), fallback.why_it_matters, 320),
            key_points=self._text_list(payload.get("key_points"), fallback.key_points, 4, 180),
            primary_topic=primary_topic,
            topic_tags=clean_tags(payload.get("topic_tags")) or fallback.topic_tags,
            event_types=event_types,
            entity_tags=clean_tags(payload.get("entity_tags")) or fallback.entity_tags,
            maturity=fallback.maturity,
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
            display_headline=title[:120],
            summary=self._truncate(summary, 500),
            why_it_matters="Review the source for implementation details and compatibility impact.",
            key_points=[self._truncate(sentence, 160) for sentence in sentences[:3] if sentence][:3],
            primary_topic=primary_topic,
            topic_tags=secondary_topics,
            event_types=events or ["library-release"],
            entity_tags=clean_tags([organization, tool]),
            maturity=infer_maturity(title, raw_text),
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
        if len(value) <= limit:
            return value
        return value[: limit - 1].rstrip() + "..."
