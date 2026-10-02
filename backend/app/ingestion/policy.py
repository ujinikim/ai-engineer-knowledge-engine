from dataclasses import dataclass

from app.domain import PUBLISHED, QUARANTINED
from app.ingestion.content_detail import IMPORTANT_SPARSE_EVENT_TYPES


FETCH_FAILED_STATUSES = ("feed_excerpt_only", "title_only")


@dataclass(frozen=True)
class IngestionDecision:
    status: str
    failure_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]
    evidence_level: str
    rag_eligible: bool

    @property
    def publishable(self) -> bool:
        return self.status == PUBLISHED

    def fields(self) -> dict[str, str]:
        return {"ingestion_status": self.status}


def evaluate_ingestion_candidate(
    *,
    content_detail: str,
    extraction_status: str,
    event_types: list[str] | None,
    publish_feed_excerpt: bool = False,
) -> IngestionDecision:
    """Apply the deterministic boundary between stored candidates and published evidence."""
    failures: list[str] = []
    warnings: list[str] = []
    # The article page could not be used when only the feed's own text (or just the
    # title) is left; a source may approve publishing that feed excerpt anyway.
    fetch_failed = extraction_status in FETCH_FAILED_STATUSES
    approved_feed_excerpt = bool(publish_feed_excerpt and extraction_status == "feed_excerpt_only")
    if fetch_failed and not approved_feed_excerpt:
        failures.append("article_hydration_failed")
    elif fetch_failed:
        warnings.append("article_hydration_failed")
    if extraction_status == "title_only":
        failures.append("title_only_source")

    important_sparse_event = bool(
        IMPORTANT_SPARSE_EVENT_TYPES.intersection(event_types or [])
    )
    if content_detail == "sparse" and not important_sparse_event and not approved_feed_excerpt:
        failures.append("insufficient_source_detail")
    elif content_detail == "sparse" and approved_feed_excerpt:
        warnings.append("insufficient_source_detail")

    unique_failures = tuple(dict.fromkeys(failures))
    unique_warnings = tuple(dict.fromkeys(warnings))
    return IngestionDecision(
        status=QUARANTINED if unique_failures else PUBLISHED,
        failure_codes=unique_failures,
        warning_codes=unique_warnings,
        evidence_level=(
            "official_feed_excerpt"
            if approved_feed_excerpt
            else "full_article"
            if extraction_status == "full_article"
            else "source_entry"
        ),
        rag_eligible=not approved_feed_excerpt and not unique_failures,
    )
