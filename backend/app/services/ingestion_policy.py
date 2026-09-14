from dataclasses import dataclass

from app.services.source_detail import IMPORTANT_SPARSE_EVENT_TYPES


PUBLISHED = "published"
QUARANTINED = "quarantined"


@dataclass(frozen=True)
class IngestionDecision:
    status: str
    failure_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]
    evidence_level: str
    rag_eligible: bool
    default_feed_eligible: bool

    @property
    def publishable(self) -> bool:
        return self.status == PUBLISHED

    def metadata(self) -> dict[str, str | bool | list[str] | None]:
        return {
            "ingestion_status": self.status,
            "ingestion_failure_codes": list(self.failure_codes),
            "ingestion_warning_codes": list(self.warning_codes),
            "quarantine_reason": self.failure_codes[0] if self.failure_codes else None,
            "evidence_level": self.evidence_level,
            "rag_eligible": self.rag_eligible,
        }


def evaluate_ingestion_candidate(
    *,
    content_detail: str,
    hydration_status: str,
    extraction_status: str,
    event_types: list[str] | None,
    publish_feed_excerpt: bool = False,
) -> IngestionDecision:
    """Apply the deterministic boundary between stored candidates and published evidence."""
    failures: list[str] = []
    warnings: list[str] = []
    approved_feed_excerpt = bool(
        publish_feed_excerpt
        and hydration_status == "failed"
        and extraction_status == "feed_excerpt_only"
    )
    if hydration_status == "failed" and not approved_feed_excerpt:
        failures.append("article_hydration_failed")
    elif hydration_status == "failed":
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
        default_feed_eligible=approved_feed_excerpt or not unique_failures,
    )


def stored_ingestion_status(metadata: dict) -> str:
    """Interpret pre-migration metadata safely during rolling deployments."""
    explicit = str(metadata.get("ingestion_status") or "").strip().lower()
    if explicit in {PUBLISHED, QUARANTINED}:
        return explicit

    decision = evaluate_ingestion_candidate(
        content_detail=str(metadata.get("content_detail") or "detailed"),
        hydration_status=str(metadata.get("hydration_status") or "not_requested"),
        extraction_status=str(metadata.get("extraction_status") or "source_entry"),
        event_types=list(metadata.get("event_types") or []),
    )
    return decision.status
