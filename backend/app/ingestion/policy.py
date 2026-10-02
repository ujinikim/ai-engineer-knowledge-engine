from dataclasses import dataclass

from app.domain import PUBLISHED, QUARANTINED
from app.ingestion.content_detail import IMPORTANT_SPARSE_EVENT_TYPES


FETCH_FAILED_STATUSES = ("feed_excerpt_only", "title_only")


@dataclass(frozen=True)
class IngestionDecision:
    status: str
    failure_codes: tuple[str, ...]

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
) -> IngestionDecision:
    """Apply the deterministic boundary between stored candidates and published evidence."""
    failures: list[str] = []
    if extraction_status in FETCH_FAILED_STATUSES:
        failures.append("article_hydration_failed")
    if extraction_status == "title_only":
        failures.append("title_only_source")
    important_sparse_event = bool(IMPORTANT_SPARSE_EVENT_TYPES.intersection(event_types or []))
    if content_detail == "sparse" and not important_sparse_event:
        failures.append("insufficient_source_detail")

    unique_failures = tuple(dict.fromkeys(failures))
    return IngestionDecision(
        status=QUARANTINED if unique_failures else PUBLISHED,
        failure_codes=unique_failures,
    )
