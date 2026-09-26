"""Generate an article's feed card with the model, or deterministically as a fallback."""

import json
import logging
import re
from dataclasses import dataclass

from openai import OpenAI

from app.core.model_usage import ModelUsage
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event
from app.ingestion.content_detail import classify_content_detail
from app.ingestion.prompts import (
    ARTICLE_SUMMARY_RESPONSE_FORMAT,
    summary_system_prompt,
    summary_user_prompt,
)
from app.ingestion.taxonomy import (
    EVENT_TYPES,
    PRIMARY_TOPICS,
    TAXONOMY_POLICY_VERSION,
    clean_labels,
    classify_topic_with_method,
    infer_event_types,
)
from app.ingestion.text import clean_text, clean_text_list, shorten_at_word_boundary


logger = get_logger("summarization")


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
            default_topic=default_topic,
            default_event_types=default_event_types,
        )
        if not self.client:
            return fallback

        model = getattr(self, "model", settings.chat_model)
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": summary_system_prompt()},
                    {
                        "role": "user",
                        "content": summary_user_prompt(
                            title=title,
                            raw_text=raw_text,
                            organization=organization,
                            tool=tool,
                            source_type=source_type,
                            detail_level=classify_content_detail(title, raw_text),
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
            return self._validated(payload, fallback, source_type)
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

    def _validated(self, payload: dict, fallback: ArticleSummary, source_type: str) -> ArticleSummary:
        """Keep valid model fields; replace invalid or missing ones from the fallback."""
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
            display_headline=clean_text(payload.get("display_headline"), fallback.display_headline, 90),
            summary=clean_text(payload.get("summary"), fallback.summary, 600),
            why_it_matters=clean_text(payload.get("why_it_matters"), fallback.why_it_matters, 320),
            key_points=clean_text_list(payload.get("key_points"), fallback.key_points, 4, 180),
            primary_topic=primary_topic,
            event_types=event_types,
            generated_by=f"{getattr(self, 'model', settings.chat_model)}:{source_type}",
        )

    @staticmethod
    def _fallback(
        *,
        title: str,
        raw_text: str,
        default_topic: str,
        default_event_types: list[str],
    ) -> ArticleSummary:
        """A card built from the article's first sentences and keyword taxonomy."""
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
            display_headline=shorten_at_word_boundary(title, 90),
            summary=shorten_at_word_boundary(summary, 500),
            why_it_matters="Review the source for implementation details and compatibility impact.",
            key_points=[
                shorten_at_word_boundary(sentence, 160) for sentence in sentences[:3] if sentence
            ][:3],
            primary_topic=primary_topic,
            event_types=events or ["analysis"],
            generated_by="deterministic-fallback",
        )
