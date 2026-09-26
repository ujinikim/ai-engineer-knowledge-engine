import hashlib
import logging
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urlparse

import httpx
from sqlalchemy import and_, delete, or_, select
from sqlalchemy.orm import Session

from app.core.model_usage import ModelUsage
from app.core.settings import settings
from app.core.structured_logging import get_logger, log_event
from app.db.models import Chunk, CollectionSourceRun, Document
from app.services.article_relevance import (
    RELEVANCE_POLICY_VERSION,
    RELEVANCE_TIERS,
    ArticleRelevanceService,
)
from app.services.article_summary import ArticleSummaryService
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.ingestion_policy import (
    evaluate_ingestion_candidate,
)
from app.services.source_extraction import SourceExtractionMixin
from app.services.source_detail import classify_content_detail
from app.services.taxonomy import (
    TAXONOMY_POLICY_VERSION,
    classify_topic_with_method,
    infer_event_types,
    normalize_event_types,
)


logger = get_logger("collector")


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


class UpdateCollectorService(SourceExtractionMixin):
    def __init__(self, db: Session) -> None:
        self.db = db
        self.chunker = ChunkingService()
        self.usage = ModelUsage()
        self.embedder = EmbeddingService(usage=self.usage)
        self.summarizer = ArticleSummaryService(usage=self.usage)
        self.relevance = ArticleRelevanceService(usage=self.usage)

    async def collect(
        self,
        source_configs: list[dict],
        max_items_per_source: int = 12,
        run_id: str | None = None,
    ) -> CollectionResult:
        run_id = run_id or uuid.uuid4().hex
        self.run_id = run_id
        counts = {
            "sources_processed": 0,
            "updates_created": 0,
            "updates_changed": 0,
            "updates_unchanged": 0,
            "updates_quarantined": 0,
            "chunks_written": 0,
            "errors": 0,
        }
        headers = {"User-Agent": "AI-Engineer-Update-Radar/0.1 (+local RAG project)"}

        async with httpx.AsyncClient(follow_redirects=True, timeout=30, headers=headers) as client:
            for config in source_configs:
                source_slug = config["slug"]
                source_started_at = datetime.now(timezone.utc).replace(tzinfo=None)
                source_started = time.perf_counter()
                source_counts_before = counts.copy()
                matched_items = 0
                try:
                    response = await self._get_with_retries(client, config["feed_url"])
                    entries = self._source_entries(config, response)
                    for entry in entries:
                        if config.get("source_kind") == "html_listing":
                            entry = await self._hydrate_html_entry(client, config, entry)
                        if config.get("require_published_date") and not self._entry_datetime(entry):
                            log_event(
                                logger,
                                "source_entry_skipped",
                                level=logging.WARNING,
                                run_id=run_id,
                                source_slug=source_slug,
                                reason="missing_published_date",
                                url=self._log_safe_url(entry.get("link")),
                            )
                            continue
                        if not self._matches_config(config, entry):
                            continue
                        if config.get("fetch_full_article") and config.get("source_kind") != "html_listing":
                            try:
                                entry = await self._hydrate_html_entry(client, config, entry)
                            except (httpx.HTTPError, ValueError) as error:
                                entry = self._full_article_fallback_entry(entry, error)
                                log_event(
                                    logger,
                                    "full_article_fetch_failed",
                                    level=logging.WARNING,
                                    run_id=run_id,
                                    source_slug=source_slug,
                                    url=self._log_safe_url(entry.get("link")),
                                    http_status=entry["_full_article_fetch_http_status"],
                                    error_code=entry["_full_article_fetch_error_code"],
                                    exception_type=type(error).__name__,
                                )
                        status, chunks_written = self._upsert_entry(source_slug, config, entry)
                        counts[f"updates_{status}"] += 1
                        counts["chunks_written"] += chunks_written
                        matched_items += 1
                        if matched_items >= max_items_per_source:
                            break

                    source_counts = {
                        key: counts[key] - source_counts_before[key]
                        for key in (
                            "updates_created", "updates_changed", "updates_unchanged",
                            "updates_quarantined", "chunks_written",
                        )
                    }
                    self.db.add(
                        CollectionSourceRun(
                            id=uuid.uuid4(),
                            run_id=run_id,
                            source_slug=source_slug,
                            started_at=source_started_at,
                            finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
                            status="completed",
                            matched_items=matched_items,
                            **source_counts,
                        )
                    )
                    counts["sources_processed"] += 1
                    self.db.commit()
                    log_event(
                        logger,
                        "source_collection_completed",
                        run_id=run_id,
                        source_slug=config["slug"],
                        matched_items=matched_items,
                        **source_counts,
                        duration_ms=int((time.perf_counter() - source_started) * 1000),
                    )
                except Exception as error:
                    self.db.rollback()
                    counts = source_counts_before.copy()
                    counts["errors"] += 1
                    self.db.add(
                        CollectionSourceRun(
                            id=uuid.uuid4(),
                            run_id=run_id,
                            source_slug=source_slug,
                            started_at=source_started_at,
                            finished_at=datetime.now(timezone.utc).replace(tzinfo=None),
                            status="failed",
                            error=str(error)[:1000],
                        )
                    )
                    self.db.commit()
                    log_event(
                        logger,
                        "source_collection_failed",
                        level=logging.ERROR,
                        run_id=run_id,
                        source_slug=config["slug"],
                        exception_type=type(error).__name__,
                        duration_ms=int((time.perf_counter() - source_started) * 1000),
                    )

        return CollectionResult(
            **counts,
            chat_input_tokens=self.usage.chat_input_tokens,
            chat_output_tokens=self.usage.chat_output_tokens,
            embedding_tokens=self.usage.embedding_tokens,
            estimated_model_cost_usd=self.usage.estimated_cost_usd(
                settings.chat_model,
                settings.embedding_model,
            ),
        )

    def _upsert_entry(self, source_slug: str, config: dict, entry) -> tuple[str, int]:
        raw_url = str(entry.get("link") or entry.get("id") or "").strip()
        url = self._normalize_document_url(raw_url)
        title = str(entry.get("title") or "Untitled update").strip()
        if not url:
            raise ValueError(f"Feed entry from {source_slug} has no URL")

        body_html = self._entry_html(entry)
        body_text = self._clean_html(body_html)
        raw_text = f"{title}\n\n{body_text}".strip()
        content_detail = classify_content_detail(title, raw_text)
        content_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()
        published_at = self._entry_datetime(entry)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        default_topic = config.get("default_primary_topic", config["category"])
        source_type = config.get("source_type", "official-release")
        default_event_types = config.get("default_event_types", ["analysis"])
        hydration_status = str(entry.get("_hydration_status") or "not_requested")
        extraction_status = str(
            entry.get("_extraction_status")
            or {
                "full_article": "full_article",
                "failed": "feed_excerpt_only" if body_text else "title_only",
            }.get(hydration_status, "source_entry")
        )
        base_metadata = {
            "organization": config["organization"],
            "tool": config["tool"],
            "primary_topic": default_topic,
            "excerpt": self._excerpt(body_text or title),
            "source_type": source_type,
            "credibility_weight": float(config.get("credibility_weight", 1.0)),
            # Legacy hydration status remains during the metadata migration.
            "hydration_status": hydration_status,
            "extraction_status": extraction_status,
        }
        provisional_events = normalize_event_types(
            source_slug,
            infer_event_types(raw_text, default_event_types),
        )
        provisional_topic, provisional_topic_method = classify_topic_with_method(
            f"{title}\n{title}\n{raw_text}",
            default_topic,
        )
        ingestion = evaluate_ingestion_candidate(
            content_detail=content_detail,
            hydration_status=hydration_status,
            extraction_status=extraction_status,
            event_types=provisional_events,
            publish_feed_excerpt=bool(config.get("publish_feed_excerpt", False)),
        )
        base_metadata = {
            **base_metadata,
            **ingestion.metadata(),
        }

        document = self._find_existing_document(
            source_slug=source_slug,
            raw_url=raw_url,
            title=title,
            content_hash=content_hash,
        )
        existing_has_full_evidence = bool(
            document
            and (
                getattr(document, "evidence_level", None) == "full_article"
                or document.doc_metadata.get("extraction_status") == "full_article"
                or classify_content_detail(getattr(document, "title", ""), document.raw_text) == "detailed"
            )
        )
        if document and not ingestion.rag_eligible and existing_has_full_evidence:
            document.fetched_at = now
            log_event(
                logger,
                "stored_article_retained",
                run_id=getattr(self, "run_id", None),
                source_slug=source_slug,
                url=self._log_safe_url(url),
                attempt_status=ingestion.status,
                failure_codes=list(ingestion.failure_codes),
                warning_codes=list(ingestion.warning_codes),
                evidence_level=ingestion.evidence_level,
            )
            return "unchanged", 0

        if ingestion.publishable:
            existing_relevance = dict(document.doc_metadata) if document else {}
            if (
                document
                and document.content_hash == content_hash
                and existing_relevance.get("relevance_policy_version")
                == RELEVANCE_POLICY_VERSION
                and document.relevance_tier in RELEVANCE_TIERS
                and existing_relevance.get("relevance_classification_status") != "fail_open"
            ):
                relevance_metadata = {
                    "relevance_tier": document.relevance_tier,
                    "relevance_reason": document.relevance_reason,
                    **{
                        key: existing_relevance[key]
                        for key in (
                            "relevance_generated_by",
                            "relevance_policy_version",
                            "relevance_classification_status",
                        )
                        if key in existing_relevance
                    },
                }
            else:
                relevance_metadata = self.relevance.classify(
                    title=title,
                    raw_text=raw_text,
                ).metadata()
            base_metadata = {**base_metadata, **relevance_metadata}

        if ingestion.publishable and base_metadata.get("relevance_tier") is None:
            if (
                document
                and document.relevance_tier in RELEVANCE_TIERS
                and document.doc_metadata.get("relevance_classification_status") != "fail_open"
            ):
                document.fetched_at = now
                log_event(
                    logger,
                    "relevance_classification_retained",
                    level=logging.WARNING,
                    run_id=getattr(self, "run_id", None),
                    source_slug=source_slug,
                    url=self._log_safe_url(url),
                    relevance_tier=document.relevance_tier,
                )
                return "unchanged", 0

            pending_metadata = {
                **base_metadata,
                "primary_topic": provisional_topic,
                "event_types": provisional_events,
            }
            status = "changed" if document and document.content_hash != content_hash else "unchanged"
            if document:
                document.source_name = source_slug
                document.title = title[:500]
                document.raw_text = raw_text
                document.content_hash = content_hash
                document.fetched_at = now
                document.published_at = published_at
                document.doc_metadata = pending_metadata
                self._sync_canonical_fields(document, pending_metadata)
                self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            else:
                status = "created"
                document = Document(
                    id=uuid.uuid4(),
                    source_name=source_slug,
                    title=title[:500],
                    url=url,
                    raw_text=raw_text,
                    content_hash=content_hash,
                    fetched_at=now,
                    published_at=published_at,
                    doc_metadata=pending_metadata,
                )
                self._sync_canonical_fields(document, pending_metadata)
                self.db.add(document)
                self.db.flush()
            return status, 0

        if ingestion.publishable and base_metadata.get("relevance_tier") == "excluded":
            excluded_metadata = {
                **base_metadata,
                "primary_topic": provisional_topic,
                "display_headline": title[:90],
                "summary": str(base_metadata["excerpt"]),
                "why_it_matters": "",
                "key_points": [],
                "event_types": provisional_events,
                "summary_generated_by": "relevance-excluded",
                "taxonomy_generated_by": provisional_topic_method,
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
            }
            status = "changed" if document and document.content_hash != content_hash else "unchanged"
            if document:
                document.source_name = source_slug
                document.title = title[:500]
                document.raw_text = raw_text
                document.content_hash = content_hash
                document.fetched_at = now
                document.published_at = published_at
                document.doc_metadata = excluded_metadata
                self._sync_canonical_fields(document, excluded_metadata)
                self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            else:
                status = "created"
                document = Document(
                    id=uuid.uuid4(),
                    source_name=source_slug,
                    title=title[:500],
                    url=url,
                    raw_text=raw_text,
                    content_hash=content_hash,
                    fetched_at=now,
                    published_at=published_at,
                    doc_metadata=excluded_metadata,
                )
                self._sync_canonical_fields(document, excluded_metadata)
                self.db.add(document)
                self.db.flush()
            return status, 0

        if ingestion.publishable and not ingestion.rag_eligible:
            excerpt_metadata = {
                **base_metadata,
                "primary_topic": provisional_topic,
                "display_headline": title[:90],
                "summary": str(base_metadata["excerpt"]),
                "why_it_matters": "",
                "key_points": [],
                "event_types": provisional_events,
                "summary_generated_by": "source-excerpt",
                "taxonomy_generated_by": provisional_topic_method,
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
            }
            status = "changed" if document and document.content_hash != content_hash else "unchanged"
            if document:
                document.source_name = source_slug
                document.title = title[:500]
                document.raw_text = raw_text
                document.content_hash = content_hash
                document.fetched_at = now
                document.published_at = published_at
                document.doc_metadata = excerpt_metadata
                self._sync_canonical_fields(document, excerpt_metadata)
                self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            else:
                status = "created"
                document = Document(
                    id=uuid.uuid4(),
                    source_name=source_slug,
                    title=title[:500],
                    url=url,
                    raw_text=raw_text,
                    content_hash=content_hash,
                    fetched_at=now,
                    published_at=published_at,
                    doc_metadata=excerpt_metadata,
                )
                self._sync_canonical_fields(document, excerpt_metadata)
                self.db.add(document)
                self.db.flush()
            return status, 0

        if (
            document
            and document.content_hash == content_hash
            and document.relevance_tier in RELEVANCE_TIERS
            and document.doc_metadata.get("relevance_classification_status") != "fail_open"
        ):
            document.fetched_at = now
            document.published_at = published_at
            existing_taxonomy = {
                "primary_topic": document.primary_topic,
                **{
                    key: document.doc_metadata.get(key)
                    for key in (
                        "event_types",
                        "taxonomy_policy_version",
                    )
                    if key in document.doc_metadata
                },
            }
            merged_metadata = {**document.doc_metadata, **base_metadata}
            merged_metadata = {**merged_metadata, **existing_taxonomy}
            merged_metadata = {
                **merged_metadata,
                **ingestion.metadata(),
            }
            if not ingestion.publishable:
                self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            document.doc_metadata = merged_metadata
            self._sync_canonical_fields(document, merged_metadata)
            if not ingestion.publishable:
                return "quarantined", 0
            return "unchanged", 0

        if not ingestion.publishable:
            quarantine_metadata = {
                **base_metadata,
                "event_types": provisional_events,
                "taxonomy_generated_by": provisional_topic_method,
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
            }
            if document:
                document.source_name = source_slug
                document.title = title[:500]
                document.url = self._normalize_document_url(raw_url)
                document.raw_text = raw_text
                document.content_hash = content_hash
                document.fetched_at = now
                document.published_at = published_at
                document.doc_metadata = quarantine_metadata
                self._sync_canonical_fields(document, quarantine_metadata)
                self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
            else:
                document = Document(
                    id=uuid.uuid4(),
                    source_name=source_slug,
                    title=title[:500],
                    url=self._normalize_document_url(raw_url),
                    raw_text=raw_text,
                    content_hash=content_hash,
                    fetched_at=now,
                    published_at=published_at,
                    doc_metadata=quarantine_metadata,
                )
                self._sync_canonical_fields(document, quarantine_metadata)
                self.db.add(document)
                self.db.flush()
            return "quarantined", 0

        article = self.summarizer.summarize(
            title=title,
            raw_text=raw_text,
            organization=config["organization"],
            tool=config["tool"],
            source_type=source_type,
            default_topic=default_topic,
            default_event_types=default_event_types,
        )
        metadata = {**base_metadata, **article.metadata()}
        normalized_events = normalize_event_types(
            source_slug,
            list(metadata.get("event_types") or default_event_types),
        )
        metadata = {
            **metadata,
            "event_types": normalized_events,
            "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
        }
        metadata = {
            **metadata,
            **ingestion.metadata(),
        }

        status = "changed" if document else "created"
        if document:
            document.source_name = source_slug
            document.title = title[:500]
            document.raw_text = raw_text
            document.content_hash = content_hash
            document.fetched_at = now
            document.published_at = published_at
            document.doc_metadata = metadata
            self._sync_canonical_fields(document, metadata)
            self.db.execute(delete(Chunk).where(Chunk.document_id == document.id))
        else:
            document = Document(
                id=uuid.uuid4(),
                source_name=source_slug,
                title=title[:500],
                url=url,
                raw_text=raw_text,
                content_hash=content_hash,
                fetched_at=now,
                published_at=published_at,
                doc_metadata=metadata,
            )
            self._sync_canonical_fields(document, metadata)
            self.db.add(document)
            self.db.flush()

        chunks = self.chunker.chunk_text(raw_text, max_tokens=650, overlap_tokens=80)
        embeddings = self.embedder.embed_texts([chunk.content for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            self.db.add(
                Chunk(
                    id=uuid.uuid4(),
                    document_id=document.id,
                    chunk_index=chunk.index,
                    content=chunk.content,
                    embedding=embedding,
                    token_count=chunk.token_count,
                    content_hash=hashlib.sha256(chunk.content.encode("utf-8")).hexdigest(),
                )
            )
        return status, len(chunks)

    @staticmethod
    def _sync_canonical_fields(document: Document, metadata: dict) -> None:
        """Keep decisions in typed columns and presentation details in JSON."""
        document.ingestion_status = str(metadata.get("ingestion_status") or "published")
        document.evidence_level = str(metadata.get("evidence_level") or "source_entry")
        document.relevance_tier = metadata.get("relevance_tier")
        document.relevance_reason = metadata.get("relevance_reason")
        document.primary_topic = metadata.get("primary_topic")
        document.doc_metadata = {
            key: value
            for key, value in metadata.items()
            if key not in {
                "ingestion_status", "evidence_level", "relevance_tier",
                "relevance_reason", "primary_topic", "ingestion_warning_codes",
                "taxonomy_main_theme", "extraction_metadata_version",
                "quality_tier", "source_kind", "content_detail",
                "summary_input_source", "maturity",
            }
        }

    def _find_existing_document(
        self,
        *,
        source_slug: str,
        raw_url: str,
        title: str,
        content_hash: str,
    ) -> Document | None:
        raw_candidates = self._document_url_candidates(raw_url)
        conditions = [Document.url.in_(raw_candidates)]
        conditions.append(
            and_(
                Document.source_name == source_slug,
                Document.title == title[:500],
                Document.content_hash == content_hash,
            )
        )
        return self.db.scalar(select(Document).where(or_(*conditions)).limit(1))

    def _normalize_document_url(self, value: str) -> str:
        parsed = urlparse(value.strip())
        scheme = parsed.scheme.lower()
        hostname = (parsed.hostname or "").lower()
        port = parsed.port
        if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
            hostname = f"{hostname}:{port}"
        path = parsed.path
        if path and path != "/":
            path = path.rstrip("/")
        tracking_parameters = {"fbclid", "gclid", "mc_cid", "mc_eid"}
        query = urlencode(
            sorted(
                (key, item)
                for key, item in parse_qsl(parsed.query, keep_blank_values=True)
                if not key.lower().startswith("utm_") and key.lower() not in tracking_parameters
            ),
            doseq=True,
        )
        return parsed._replace(
            scheme=scheme,
            netloc=hostname,
            path=path,
            query=query,
        ).geturl()

    def _document_url_candidates(self, value: str) -> list[str]:
        normalized = self._normalize_document_url(value)
        parsed = urlparse(normalized)
        candidates = [normalized]
        if parsed.path and parsed.path != "/":
            candidates.append(parsed._replace(path=f"{parsed.path}/").geturl())
        return list(dict.fromkeys(candidates))
