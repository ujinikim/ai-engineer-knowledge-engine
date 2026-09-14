import hashlib
import json
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.source_detail import classify_content_detail
from app.services.taxonomy import (
    EVENT_TYPES,
    LEGACY_EVENT_TYPES,
    LEGACY_PRIMARY_TOPICS,
    MATURITY_LEVELS,
    PRIMARY_TOPICS,
    TAXONOMY_POLICY_VERSION,
)


STOPWORDS = {
    "about",
    "after",
    "again",
    "also",
    "because",
    "before",
    "being",
    "between",
    "could",
    "from",
    "have",
    "into",
    "more",
    "most",
    "other",
    "over",
    "should",
    "than",
    "that",
    "their",
    "there",
    "these",
    "they",
    "this",
    "through",
    "under",
    "using",
    "were",
    "which",
    "with",
    "would",
}

MORPHOLOGY_NORMALIZATIONS = {
    "improve": "improve",
    "improved": "improve",
    "improvement": "improve",
    "improvements": "improve",
    "improves": "improve",
    "improving": "improve",
    "release": "release",
    "released": "release",
    "releases": "release",
    "releasing": "release",
}


@dataclass(frozen=True)
class SummaryThresholds:
    headline_max_characters: int = 90
    summary_max_words: int = 70
    why_it_matters_max_words: int = 35
    key_points_minimum: int = 2
    key_points_maximum: int = 4
    key_point_max_words: int = 35
    low_grounding_overlap: float = 0.30
    sparse_low_grounding_overlap: float = 0.40


@dataclass(frozen=True)
class SummaryEvaluation:
    document_id: str
    review_key: str
    source_name: str
    source_type: str
    title: str
    url: str
    generated_by: str
    display_headline: str
    summary: str
    why_it_matters: str
    key_points: list[str]
    primary_topic: str
    topic_tags: list[str]
    event_types: list[str]
    entity_tags: list[str]
    maturity: str
    source_detail: str
    headline_characters: int
    summary_word_count: int
    why_it_matters_word_count: int
    key_point_count: int
    longest_key_point_words: int
    grounding_overlap: float
    unsupported_numbers: list[str]
    quality_status: str
    warnings: list[str]
    failures: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class SummaryQualityService:
    def __init__(self, thresholds: SummaryThresholds | None = None) -> None:
        self.thresholds = thresholds or SummaryThresholds()

    def evaluate(self, document: Any) -> SummaryEvaluation:
        metadata = dict(document.doc_metadata or {})
        source_text = str(document.raw_text or "")
        display_headline = self._text(metadata.get("display_headline"))
        summary = self._text(metadata.get("summary"))
        why_it_matters = self._text(metadata.get("why_it_matters"))
        key_points = self._text_list(metadata.get("key_points"))
        primary_topic = self._text(metadata.get("primary_topic"))
        topic_tags = self._text_list(metadata.get("topic_tags"))
        event_types = self._text_list(metadata.get("event_types"))
        entity_tags = self._text_list(metadata.get("entity_tags"))
        maturity = self._text(metadata.get("maturity"))
        generated_by = self._text(metadata.get("summary_generated_by")) or "unknown"
        source_type = self._text(metadata.get("source_type")) or "unknown"
        source_detail = self._text(metadata.get("content_detail"))
        if source_detail not in {"detailed", "sparse"}:
            source_detail = classify_content_detail(str(document.title or ""), source_text)

        generated_text = " ".join(
            [display_headline, summary, why_it_matters, *key_points]
        ).strip()
        summary_word_count = self._word_count(summary)
        why_word_count = self._word_count(why_it_matters)
        key_point_words = [self._word_count(point) for point in key_points]
        unsupported_numbers = self._unsupported_numbers(generated_text, source_text)
        grounding_overlap = self._grounding_overlap(generated_text, source_text)
        warnings: list[str] = []
        failures: list[str] = []

        required_fields = {
            "display_headline": display_headline,
            "summary": summary,
            "why_it_matters": why_it_matters,
            "key_points": key_points,
            "primary_topic": primary_topic,
            "event_types": event_types,
            "entity_tags": entity_tags,
            "maturity": maturity,
        }
        for field, value in required_fields.items():
            if not value:
                failures.append(f"missing_{field}")

        if len(display_headline) > self.thresholds.headline_max_characters:
            warnings.append("headline_too_long")
        if summary_word_count > self.thresholds.summary_max_words:
            warnings.append("summary_too_long")
        if why_word_count > self.thresholds.why_it_matters_max_words:
            warnings.append("why_it_matters_too_long")
        if key_points and len(key_points) < self.thresholds.key_points_minimum:
            warnings.append("too_few_key_points")
        if len(key_points) > self.thresholds.key_points_maximum:
            warnings.append("too_many_key_points")
        if key_point_words and max(key_point_words) > self.thresholds.key_point_max_words:
            warnings.append("key_point_too_long")
        if unsupported_numbers:
            warnings.append("unsupported_number")
        grounding_threshold = (
            self.thresholds.sparse_low_grounding_overlap
            if source_detail == "sparse"
            else self.thresholds.low_grounding_overlap
        )
        if generated_text and grounding_overlap < grounding_threshold:
            warnings.append("low_lexical_grounding")
        is_v2 = metadata.get("taxonomy_policy_version") == TAXONOMY_POLICY_VERSION
        allowed_topics = PRIMARY_TOPICS if is_v2 else PRIMARY_TOPICS + LEGACY_PRIMARY_TOPICS
        allowed_events = EVENT_TYPES if is_v2 else EVENT_TYPES + LEGACY_EVENT_TYPES
        if primary_topic and primary_topic not in allowed_topics:
            failures.append("invalid_primary_topic")
        if event_types and any(event not in allowed_events for event in event_types):
            failures.append("invalid_event_type")
        if is_v2 and len(event_types) > 1:
            failures.append("multiple_event_types")
        if is_v2 and topic_tags:
            failures.append("unexpected_topic_tags")
        if maturity and maturity not in MATURITY_LEVELS:
            failures.append("invalid_maturity")
        if generated_by == "deterministic-fallback":
            warnings.append("deterministic_fallback_summary")
        if (
            metadata.get("extraction_status") in {"feed_excerpt_only", "title_only"}
            or metadata.get("hydration_status") == "failed"
        ):
            warnings.append("source_content_incomplete")

        status = "fail" if failures else "warning" if warnings else "pass"
        review_key = self._review_key(document.content_hash, required_fields, generated_by)
        return SummaryEvaluation(
            document_id=str(document.id),
            review_key=review_key,
            source_name=str(document.source_name),
            source_type=source_type,
            title=str(document.title or ""),
            url=str(document.canonical_url or document.url or ""),
            generated_by=generated_by,
            display_headline=display_headline,
            summary=summary,
            why_it_matters=why_it_matters,
            key_points=key_points,
            primary_topic=primary_topic,
            topic_tags=topic_tags,
            event_types=event_types,
            entity_tags=entity_tags,
            maturity=maturity,
            source_detail=source_detail,
            headline_characters=len(display_headline),
            summary_word_count=summary_word_count,
            why_it_matters_word_count=why_word_count,
            key_point_count=len(key_points),
            longest_key_point_words=max(key_point_words, default=0),
            grounding_overlap=round(grounding_overlap, 4),
            unsupported_numbers=unsupported_numbers,
            quality_status=status,
            warnings=list(dict.fromkeys(warnings)),
            failures=list(dict.fromkeys(failures)),
        )

    def aggregate(self, evaluations: list[SummaryEvaluation]) -> dict[str, Any]:
        statuses = Counter(item.quality_status for item in evaluations)
        warnings = Counter(warning for item in evaluations for warning in item.warnings)
        failures = Counter(failure for item in evaluations for failure in item.failures)
        by_source_type: dict[str, Counter[str]] = defaultdict(Counter)
        by_generator: dict[str, Counter[str]] = defaultdict(Counter)
        for item in evaluations:
            by_source_type[item.source_type][item.quality_status] += 1
            by_generator[item.generated_by][item.quality_status] += 1

        overlaps = [item.grounding_overlap for item in evaluations]
        return {
            "documents_evaluated": len(evaluations),
            "status_counts": self._complete_counts(statuses),
            "warning_counts": dict(warnings.most_common()),
            "failure_counts": dict(failures.most_common()),
            "average_grounding_overlap": round(sum(overlaps) / len(overlaps), 4)
            if overlaps
            else 0.0,
            "by_source_type": {
                source_type: self._complete_counts(counts)
                for source_type, counts in sorted(by_source_type.items())
            },
            "by_generator": {
                generator: self._complete_counts(counts)
                for generator, counts in sorted(by_generator.items())
            },
        }

    def select_review_sample(
        self,
        evaluations: list[SummaryEvaluation],
        sample_size: int,
    ) -> list[SummaryEvaluation]:
        if sample_size <= 0:
            return []
        complete_source_evaluations = [
            item for item in evaluations if "source_content_incomplete" not in item.warnings
        ]
        evaluations = complete_source_evaluations or evaluations
        ordered = sorted(
            evaluations,
            key=lambda item: (
                {"fail": 0, "warning": 1, "pass": 2}[item.quality_status],
                item.grounding_overlap,
                item.source_name,
                item.document_id,
            ),
        )
        selected: list[SummaryEvaluation] = []
        seen_ids: set[str] = set()

        for source_type in sorted({item.source_type for item in ordered}):
            candidate = next(item for item in ordered if item.source_type == source_type)
            self._append_unique(selected, seen_ids, candidate)
            if len(selected) >= sample_size:
                return selected

        for generator in sorted({item.generated_by for item in ordered}):
            candidate = next(item for item in ordered if item.generated_by == generator)
            self._append_unique(selected, seen_ids, candidate)
            if len(selected) >= sample_size:
                return selected

        for item in ordered:
            if item.source_name not in {selected_item.source_name for selected_item in selected}:
                self._append_unique(selected, seen_ids, item)
                if len(selected) >= sample_size:
                    return selected

        for item in ordered:
            self._append_unique(selected, seen_ids, item)
            if len(selected) >= sample_size:
                break
        return selected

    def _review_key(self, content_hash: str, fields: dict[str, Any], generated_by: str) -> str:
        payload = json.dumps(
            {"content_hash": content_hash, "generated_by": generated_by, "fields": fields},
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _unsupported_numbers(self, generated_text: str, source_text: str) -> list[str]:
        generated = set(self._numbers(generated_text))
        source = set(self._numbers(source_text))
        return sorted(generated - source)

    def _numbers(self, value: str) -> list[str]:
        pattern = re.compile(
            r"(?<![\w])(?:\$)?v?(?P<number>\d[\d,]*(?:\.\d+)?)"
            r"(?P<percent>%|\s+percent\b)?",
            re.IGNORECASE,
        )
        numbers: list[str] = []
        for match in pattern.finditer(value):
            number = match.group("number").replace(",", "")
            try:
                number = format(Decimal(number).normalize(), "f")
            except InvalidOperation:
                pass
            if match.group("percent"):
                number = f"{number}%"
            numbers.append(number.lower())
        return numbers

    def _grounding_overlap(self, generated_text: str, source_text: str) -> float:
        generated = self._content_tokens(generated_text)
        if not generated:
            return 1.0
        source = self._content_tokens(source_text)
        return len(generated & source) / len(generated)

    def _content_tokens(self, value: str) -> set[str]:
        return {
            self._normalize_content_token(token)
            for token in re.findall(r"[a-zA-Z][a-zA-Z0-9+#.-]{3,}", value.lower())
            if self._normalize_content_token(token) not in STOPWORDS
        }

    def _normalize_content_token(self, token: str) -> str:
        token = token.strip(".-")
        return MORPHOLOGY_NORMALIZATIONS.get(token, token)

    def _word_count(self, value: str) -> int:
        return len(re.findall(r"\b[\w+#.-]+\b", value))

    def _text(self, value: object) -> str:
        return " ".join(str(value or "").split())

    def _text_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [self._text(item) for item in value if self._text(item)]

    def _complete_counts(self, counts: Counter[str]) -> dict[str, int]:
        return {status: counts.get(status, 0) for status in ("pass", "warning", "fail")}

    def _append_unique(
        self,
        selected: list[SummaryEvaluation],
        seen_ids: set[str],
        item: SummaryEvaluation,
    ) -> None:
        if item.document_id not in seen_ids:
            selected.append(item)
            seen_ids.add(item.document_id)
