"""Run a collection: fetch each configured source, filter its entries, and ingest them.

This file owns the run (sources, retries, run records, counts). What happens to each
entry is decided in `ingest.py`.
"""

import logging
import time
import uuid
from contextlib import aclosing
from dataclasses import dataclass
from datetime import datetime

import httpx
from sqlalchemy.orm import Session

from app.core.embedding import EmbeddingService
from app.core.model_usage import ModelUsage
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event, safe_url
from app.db.models import CollectionSourceRun
from app.ingestion.chunking import ChunkingService
from app.ingestion.ingest import ArticleIngestor, utc_now
from app.ingestion.fetch import failed_fetch_entry, fetch_full_article, get_with_retries
from app.ingestion.parsing import entry_datetime, matches_config, source_entries
from app.ingestion.relevance import (
    ArticleRelevanceService,
)
from app.ingestion.summary import ArticleSummaryService
from app.sources import SourceConfig


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
    def __init__(self, db: Session) -> None:
        self.db = db
        self.chunker = ChunkingService()
        self.usage = ModelUsage()
        self.embedder = EmbeddingService(usage=self.usage)
        self.summarizer = ArticleSummaryService(usage=self.usage)
        self.relevance = ArticleRelevanceService(usage=self.usage)
        self.run_id: str | None = None
        self.ingestor = self._new_ingestor()

    def _new_ingestor(self) -> ArticleIngestor:
        return ArticleIngestor(
            self.db,
            relevance=self.relevance,
            summarizer=self.summarizer,
            chunker=self.chunker,
            embedder=self.embedder,
            run_id=self.run_id,
        )

    # Collection run ---------------------------------------------------------

    async def collect(
        self,
        source_configs: list[SourceConfig],
        max_items_per_source: int = 12,
        run_id: str | None = None,
    ) -> CollectionResult:
        self.run_id = run_id or uuid.uuid4().hex
        self.ingestor = self._new_ingestor()
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
        self, client: httpx.AsyncClient, config: SourceConfig, max_items: int
    ) -> dict[str, int] | None:
        """Ingest one source and record its run; None when the source failed."""
        source_slug = config["slug"]
        started_at = utc_now()
        started = time.perf_counter()
        counts = dict.fromkeys(SOURCE_COUNT_KEYS, 0)
        matched_items = 0
        try:
            async with aclosing(self._matching_entries(client, config)) as entries:
                async for entry in entries:
                    status, chunks_written = self.ingestor.ingest(source_slug, config, entry)
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

    async def _matching_entries(self, client: httpx.AsyncClient, config: SourceConfig):
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
                finished_at=utc_now(),
                **fields,
            )
        )
        self.db.commit()


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
