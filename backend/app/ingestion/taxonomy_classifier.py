"""Classify an article's category and event with three model steps.

The model first writes the article's main theme, then picks a category and an event
from that theme alone, so the publisher or product name cannot drive the label. Any
failed step falls back to deterministic keyword rules.
"""

import json
import logging
from dataclasses import dataclass

from openai import OpenAI

from app.core.model_usage import ModelUsage
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event
from app.ingestion.prompts import (
    CATEGORY_RESPONSE_FORMAT,
    EVENT_RESPONSE_FORMAT,
    MAIN_THEME_RESPONSE_FORMAT,
    category_prompt,
    event_prompt,
    main_theme_prompt,
)
from app.ingestion.taxonomy import (
    EVENT_TYPES,
    PRIMARY_TOPICS,
    clean_labels,
    classify_topic_with_method,
    infer_event_types,
)
from app.ingestion.text import clean_text


logger = get_logger("summarization")


@dataclass(frozen=True)
class TaxonomyClassification:
    primary_topic: str
    event_types: list[str]
    method: str
    main_theme: str | None
    category_reason: str | None
    event_reason: str | None


class TaxonomyClassifier:
    def __init__(self, usage: ModelUsage | None = None, model: str | None = None) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        self.usage = usage
        self.model = model or settings.chat_model

    def classify(
        self,
        *,
        title: str,
        raw_text: str,
        default_topic: str,
        default_event_types: list[str],
    ) -> TaxonomyClassification:
        fallback_topic, fallback_method = classify_topic_with_method(
            f"{title}\n{title}\n{raw_text}",
            default_topic,
        )
        fallback_events = infer_event_types(raw_text, default_event_types) or ["analysis"]

        def fallback(reason: str, main_theme: str | None = None) -> TaxonomyClassification:
            return TaxonomyClassification(
                primary_topic=fallback_topic,
                event_types=fallback_events[:1],
                method=fallback_method,
                main_theme=main_theme,
                category_reason=reason,
                event_reason=None,
            )

        if not self.client:
            return fallback("Model classification unavailable; deterministic fallback used.")

        try:
            theme_payload = self._ask(
                main_theme_prompt(),
                f"Title: {title}\n\nSource text:\n{raw_text[:12000]}",
                MAIN_THEME_RESPONSE_FORMAT,
                max_tokens=220,
            )
            main_theme = clean_text(theme_payload.get("main_theme"), "", 180)
            if not main_theme:
                return fallback("Main-theme gate returned no usable decision.")

            theme_input = f"Title: {title}\nMain theme: {main_theme}"
            category_payload = self._ask(
                category_prompt(), theme_input, CATEGORY_RESPONSE_FORMAT, max_tokens=140
            )
            topic = str(category_payload.get("primary_topic") or "").strip().lower()
            reason = clean_text(category_payload.get("classification_reason"), "", 240)
            if topic not in PRIMARY_TOPICS or not reason:
                return fallback("Category gate returned an invalid structured result.", main_theme)

            event_payload = self._ask(
                event_prompt(), theme_input, EVENT_RESPONSE_FORMAT, max_tokens=100
            )
            events = clean_labels([event_payload.get("event_type")], EVENT_TYPES, limit=1)
            event_reason = clean_text(event_payload.get("event_reason"), "", 240)
            if not events or not event_reason:
                events = fallback_events[:1]
                event_reason = "Event gate failed; deterministic fallback used."
            return TaxonomyClassification(
                primary_topic=topic,
                event_types=events,
                method=self.model,
                main_theme=main_theme,
                category_reason=reason,
                event_reason=event_reason,
            )
        except Exception as error:
            log_event(
                logger,
                "taxonomy_generation_fallback",
                level=logging.WARNING,
                model=self.model,
                exception_type=type(error).__name__,
            )
            return fallback("Model classification failed; deterministic fallback used.")

    def _ask(self, system: str, user: str, response_format: dict, *, max_tokens: int) -> dict:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_format,
            temperature=0.1,
            max_completion_tokens=max_tokens,
        )
        if self.usage and response.usage:
            self.usage.record_chat(response.usage.prompt_tokens, response.usage.completion_tokens)
        return json.loads(response.choices[0].message.content or "{}")
