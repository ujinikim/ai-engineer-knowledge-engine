"""Decide what one feed entry becomes and store it.

`ArticleIngestor.ingest` prepares a candidate, applies the publication gate, and routes it:

- keep the stored article when a refresh is worse than what is already stored
- publishable, awaiting relevance: store provisional labels and retry next run
- publishable but judged irrelevant: store a card from the source excerpt
- unchanged content that is already classified: refresh dates and status only
- not publishable: quarantine without a card, chunks, or embeddings
- otherwise: summarize, chunk, and embed
"""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.structured_logging import get_logger, log_event, safe_url
from app.db.models import Document
from app.domain import RELEVANCE_TIERS
from app.ingestion.candidate import ArticleCandidate, prepare_candidate
from app.ingestion.content_detail import classify_content_detail
from app.ingestion.policy import IngestionDecision, evaluate_ingestion_candidate
from app.ingestion.relevance import RELEVANCE_POLICY_VERSION
from app.ingestion.store import (
    add_chunks,
    apply_fields,
    current_fields,
    delete_chunks,
    find_existing_article,
    save_article,
)
from app.ingestion.taxonomy import normalize_event_types
from app.sources import SourceConfig


logger = get_logger("collector")


class ArticleIngestor:
    def __init__(self, db: Session, *, relevance, summarizer, chunker, embedder, run_id: str | None = None) -> None:
        self.db = db
        self.relevance = relevance
        self.summarizer = summarizer
        self.chunker = chunker
        self.embedder = embedder
        self.run_id = run_id

    def ingest(self, source_slug: str, config: SourceConfig, entry) -> tuple[str, int]:
        """Store one entry and return its status and the number of chunks written."""
        candidate = prepare_candidate(source_slug, config, entry, now=utc_now())
        decision = evaluate_ingestion_candidate(
            content_detail=candidate.content_detail,
            extraction_status=candidate.extraction_status,
            event_types=candidate.provisional_events,
        )
        existing = find_existing_article(self.db, candidate)

        if existing and not decision.publishable and _has_full_evidence(existing):
            return self._keep_stored_article(existing, candidate, decision)

        fields = {
            "primary_topic": candidate.default_topic,
            "extraction_status": candidate.extraction_status,
            **decision.fields(),
        }
        if decision.publishable:
            fields.update(self._relevance_fields(existing, candidate))
            tier = fields.get("relevance_tier")
            if tier is None:
                return self._save_awaiting_relevance(existing, candidate, fields)
            if tier == "excluded":
                return self._save_excluded_card(existing, candidate, fields)

        if (
            existing
            and existing.content_hash == candidate.content_hash
            and existing.relevance_tier in RELEVANCE_TIERS
        ):
            return self._refresh_unchanged(existing, candidate, fields, decision)
        if not decision.publishable:
            return self._save_quarantined(existing, candidate, fields, decision)
        return self._save_summarized(existing, candidate, fields, config)

    def _relevance_fields(self, existing: Document | None, candidate: ArticleCandidate) -> dict:
        """Reuse a current decision for unchanged content; otherwise classify."""
        if (
            existing
            and existing.content_hash == candidate.content_hash
            and existing.relevance_policy_version == RELEVANCE_POLICY_VERSION
            and existing.relevance_tier in RELEVANCE_TIERS
        ):
            return {
                "relevance_tier": existing.relevance_tier,
                "relevance_reason": existing.relevance_reason,
                "relevance_policy_version": existing.relevance_policy_version,
            }
        return self.relevance.classify(title=candidate.title, raw_text=candidate.raw_text).fields()

    # Routes -------------------------------------------------------------------

    def _keep_stored_article(
        self, existing: Document, candidate: ArticleCandidate, decision: IngestionDecision
    ) -> tuple[str, int]:
        """A refresh with weaker evidence never replaces a stored full article."""
        existing.fetched_at = candidate.fetched_at
        log_event(
            logger,
            "stored_article_retained",
            run_id=self.run_id,
            source_slug=candidate.source_slug,
            url=safe_url(candidate.url),
            attempt_status=decision.status,
            failure_codes=list(decision.failure_codes),
        )
        return "unchanged", 0

    def _save_awaiting_relevance(
        self, existing: Document | None, candidate: ArticleCandidate, fields: dict
    ) -> tuple[str, int]:
        """Classification failed: keep a prior decision, or store provisional labels."""
        if existing and existing.relevance_tier in RELEVANCE_TIERS:
            existing.fetched_at = candidate.fetched_at
            log_event(
                logger,
                "relevance_classification_retained",
                level=logging.WARNING,
                run_id=self.run_id,
                source_slug=candidate.source_slug,
                url=safe_url(candidate.url),
                relevance_tier=existing.relevance_tier,
            )
            return "unchanged", 0

        status = _write_status(existing, candidate)
        save_article(
            self.db,
            existing,
            candidate,
            {
                **fields,
                "primary_topic": candidate.provisional_topic,
                "event_types": candidate.provisional_events,
            },
        )
        return status, 0

    def _save_excluded_card(
        self, existing: Document | None, candidate: ArticleCandidate, fields: dict
    ) -> tuple[str, int]:
        """Build the card from the source excerpt; nothing is summarized or embedded."""
        status = _write_status(existing, candidate)
        save_article(
            self.db,
            existing,
            candidate,
            {
                **fields,
                "primary_topic": candidate.provisional_topic,
                "display_headline": candidate.title[:90],
                "summary": candidate.excerpt,
                "why_it_matters": "",
                "key_points": [],
                "event_types": candidate.provisional_events,
                "summary_generated_by": "relevance-excluded",
            },
        )
        return status, 0

    def _refresh_unchanged(
        self,
        existing: Document,
        candidate: ArticleCandidate,
        fields: dict,
        decision: IngestionDecision,
    ) -> tuple[str, int]:
        """Same content: keep the card and taxonomy, refresh dates and gate status."""
        existing.fetched_at = candidate.fetched_at
        existing.published_at = candidate.published_at
        if not decision.publishable:
            delete_chunks(self.db, existing)
        save_fields = {
            **current_fields(existing),
            **fields,
            "primary_topic": existing.primary_topic,
            "event_types": existing.event_types,
        }
        apply_fields(existing, save_fields)
        if not decision.publishable:
            self._log_quarantine(candidate, decision)
            return "quarantined", 0
        return "unchanged", 0

    def _save_quarantined(
        self,
        existing: Document | None,
        candidate: ArticleCandidate,
        fields: dict,
        decision: IngestionDecision,
    ) -> tuple[str, int]:
        save_article(
            self.db,
            existing,
            candidate,
            {
                **fields,
                "event_types": candidate.provisional_events,
            },
            update_url=True,
        )
        self._log_quarantine(candidate, decision)
        return "quarantined", 0

    def _save_summarized(
        self,
        existing: Document | None,
        candidate: ArticleCandidate,
        fields: dict,
        config: SourceConfig,
    ) -> tuple[str, int]:
        article = self.summarizer.summarize(
            title=candidate.title,
            raw_text=candidate.raw_text,
            organization=config["organization"],
            tool=config["tool"],
            source_type=config.get("source_type", "official-release"),
            default_topic=candidate.default_topic,
            default_event_types=candidate.default_event_types,
        )
        article_fields = article.fields()
        status = "changed" if existing else "created"
        document = save_article(
            self.db,
            existing,
            candidate,
            {
                **fields,
                **article_fields,
                "event_types": normalize_event_types(
                    candidate.source_slug,
                    list(article_fields.get("event_types") or candidate.default_event_types),
                ),
            },
        )
        chunks = self.chunker.chunk_text(candidate.raw_text, max_tokens=650, overlap_tokens=80)
        embeddings = self.embedder.embed_texts([chunk.content for chunk in chunks])
        return status, add_chunks(self.db, document, chunks, embeddings)

    def _log_quarantine(self, candidate: ArticleCandidate, decision: IngestionDecision) -> None:
        log_event(
            logger,
            "article_quarantined",
            run_id=self.run_id,
            source_slug=candidate.source_slug,
            url=safe_url(candidate.url),
            failure_codes=list(decision.failure_codes),
            extraction_status=candidate.extraction_status,
        )


def _has_full_evidence(document: Document) -> bool:
    return (
        document.extraction_status == "full_article"
        or classify_content_detail(document.title or "", document.raw_text) == "detailed"
    )


def _write_status(existing: Document | None, candidate: ArticleCandidate) -> str:
    """Status of a write, judged before the stored content is overwritten."""
    if existing is None:
        return "created"
    return "changed" if existing.content_hash != candidate.content_hash else "unchanged"


def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
