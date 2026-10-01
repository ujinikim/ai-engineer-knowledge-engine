"""Collect configured sources: fetch entries, decide what each becomes, and store it.

For every entry, `_upsert_entry` prepares a candidate, applies the publication gate,
and routes it:

- keep the stored article when a refresh is worse than what is already stored
- publishable, awaiting relevance: store provisional labels and retry next run
- publishable, excluded or feed-excerpt evidence: store a card from the source excerpt
- unchanged content that is already classified: refresh dates and status only
- not publishable: quarantine without a card, chunks, or embeddings
- otherwise: summarize, chunk, and embed
"""

import logging
import time
import uuid
from contextlib import aclosing
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from app.core.embedding import EmbeddingService
from app.core.model_usage import ModelUsage
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event, safe_url
from app.db.models import CollectionSourceRun, Document
from app.ingestion.candidate import ArticleCandidate, prepare_candidate
from app.ingestion.chunking import ChunkingService
from app.ingestion.content_detail import classify_content_detail
from app.ingestion.fetch import failed_fetch_entry, fetch_full_article, get_with_retries
from app.ingestion.parsing import entry_datetime, matches_config, source_entries
from app.ingestion.policy import IngestionDecision, evaluate_ingestion_candidate
from app.ingestion.relevance import (
    RELEVANCE_POLICY_VERSION,
    RELEVANCE_TIERS,
    ArticleRelevanceService,
)
from app.ingestion.store import (
    add_chunks,
    apply_fields,
    current_fields,
    delete_chunks,
    find_existing_article,
    save_article,
)
from app.ingestion.summary import ArticleSummaryService
from app.ingestion.taxonomy import TAXONOMY_POLICY_VERSION, normalize_event_types


logger = get_logger("collector")

USER_AGENT = "AI-Engineer-Update-Radar/0.1 (+local RAG project)"
SOURCE_COUNT_KEYS = (
    "updates_created",
    "updates_changed",
    "updates_unchanged",
    "updates_quarantined",
    "chunks_written",
)


@dataclass(frozen=True)
class CollectionResult:
    sources_processed: int = 0
    updates_created: int = 0
    updates_changed: int = 0
    updates_unchanged: int = 0
    updates_quarantined: int = 0
    chunks_written: int = 0
    errors: int = 0
    chat_input_tokens: int = 0
    chat_output_tokens: int = 0
    embedding_tokens: int = 0
    estimated_model_cost_usd: float | None = None


class IngestionPipeline:
    run_id: str | None = None

    def __init__(self, db: Session) -> None:
        self.db = db
        self.chunker = ChunkingService()
        self.usage = ModelUsage()
        self.embedder = EmbeddingService(usage=self.usage)
        self.summarizer = ArticleSummaryService(usage=self.usage)
        self.relevance = ArticleRelevanceService(usage=self.usage)

    # Collection run ---------------------------------------------------------

    async def collect(
        self,
        source_configs: list[dict],
        max_items_per_source: int = 12,
        run_id: str | None = None,
    ) -> CollectionResult:
        self.run_id = run_id or uuid.uuid4().hex
        totals = dict.fromkeys(("sources_processed", "errors", *SOURCE_COUNT_KEYS), 0)

        async with httpx.AsyncClient(
            follow_redirects=True, timeout=30, headers={"User-Agent": USER_AGENT}
        ) as client:
            for config in source_configs:
                source_counts = await self._collect_source(client, config, max_items_per_source)
                if source_counts is None:
                    totals["errors"] += 1
                    continue
                totals["sources_processed"] += 1
                for key, value in source_counts.items():
                    totals[key] += value

        return CollectionResult(
            **totals,
            chat_input_tokens=self.usage.chat_input_tokens,
            chat_output_tokens=self.usage.chat_output_tokens,
            embedding_tokens=self.usage.embedding_tokens,
            estimated_model_cost_usd=self.usage.estimated_cost_usd(
                settings.chat_model,
                settings.embedding_model,
            ),
        )

    async def _collect_source(
        self, client: httpx.AsyncClient, config: dict, max_items: int
    ) -> dict[str, int] | None:
        """Ingest one source and record its run; None when the source failed."""
        source_slug = config["slug"]
        started_at = _utc_now()
        started = time.perf_counter()
        counts = dict.fromkeys(SOURCE_COUNT_KEYS, 0)
        matched_items = 0
        try:
            async with aclosing(self._matching_entries(client, config)) as entries:
                async for entry in entries:
                    status, chunks_written = self._upsert_entry(source_slug, config, entry)
                    counts[f"updates_{status}"] += 1
                    counts["chunks_written"] += chunks_written
                    matched_items += 1
                    if matched_items >= max_items:
                        break

            self._record_source_run(
                source_slug,
                started_at,
                status="completed",
                matched_items=matched_items,
                **counts,
            )
            log_event(
                logger,
                "source_collection_completed",
                run_id=self.run_id,
                source_slug=source_slug,
                matched_items=matched_items,
                **counts,
                duration_ms=_elapsed_ms(started),
            )
            return counts
        except Exception as error:
            self.db.rollback()
            self._record_source_run(
                source_slug, started_at, status="failed", error=str(error)[:1000]
            )
            log_event(
                logger,
                "source_collection_failed",
                level=logging.ERROR,
                run_id=self.run_id,
                source_slug=source_slug,
                exception_type=type(error).__name__,
                duration_ms=_elapsed_ms(started),
            )
            return None

    async def _matching_entries(self, client: httpx.AsyncClient, config: dict):
        """Yield the source's entries that pass its filters, with full articles fetched."""
        source_slug = config["slug"]
        is_listing = config.get("source_kind") == "html_listing"
        response = await get_with_retries(client, config["feed_url"], run_id=self.run_id)
        for entry in source_entries(config, response.text, response.content):
            if is_listing:
                entry = await fetch_full_article(client, config, entry, run_id=self.run_id)
            if config.get("require_published_date") and not entry_datetime(entry):
                log_event(
                    logger,
                    "source_entry_skipped",
                    level=logging.WARNING,
                    run_id=self.run_id,
                    source_slug=source_slug,
                    reason="missing_published_date",
                    url=safe_url(entry.get("link")),
                )
                continue
            if not matches_config(config, entry):
                continue
            if config.get("fetch_full_article") and not is_listing:
                try:
                    entry = await fetch_full_article(client, config, entry, run_id=self.run_id)
                except (httpx.HTTPError, ValueError) as error:
                    entry = failed_fetch_entry(entry, error)
                    log_event(
                        logger,
                        "full_article_fetch_failed",
                        level=logging.WARNING,
                        run_id=self.run_id,
                        source_slug=source_slug,
                        url=safe_url(entry.get("link")),
                        http_status=entry["_full_article_fetch_http_status"],
                        error_code=entry["_full_article_fetch_error_code"],
                        exception_type=type(error).__name__,
                    )
            yield entry

    def _record_source_run(self, source_slug: str, started_at: datetime, **fields) -> None:
        self.db.add(
            CollectionSourceRun(
                id=uuid.uuid4(),
                run_id=self.run_id,
                source_slug=source_slug,
                started_at=started_at,
                finished_at=_utc_now(),
                **fields,
            )
        )
        self.db.commit()

    # One entry ----------------------------------------------------------------

    def _upsert_entry(self, source_slug: str, config: dict, entry) -> tuple[str, int]:
        """Store one entry and return its status and the number of chunks written."""
        candidate = prepare_candidate(source_slug, config, entry, now=_utc_now())
        decision = evaluate_ingestion_candidate(
            content_detail=candidate.content_detail,
            hydration_status=candidate.hydration_status,
            extraction_status=candidate.extraction_status,
            event_types=candidate.provisional_events,
            publish_feed_excerpt=bool(config.get("publish_feed_excerpt", False)),
        )
        existing = find_existing_article(self.db, candidate)

        if existing and not decision.rag_eligible and _has_full_evidence(existing):
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
                return self._save_excerpt_card(existing, candidate, fields, "relevance-excluded")
            if not decision.rag_eligible:
                return self._save_excerpt_card(existing, candidate, fields, "source-excerpt")

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
                "relevance_status": existing.relevance_status,
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
            warning_codes=list(decision.warning_codes),
            evidence_level=decision.evidence_level,
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

    def _save_excerpt_card(
        self,
        existing: Document | None,
        candidate: ArticleCandidate,
        fields: dict,
        generated_by: str,
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
                "summary_generated_by": generated_by,
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
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
            "taxonomy_policy_version": existing.taxonomy_policy_version,
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
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
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
        config: dict,
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
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
