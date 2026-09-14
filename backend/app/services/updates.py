import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, UpdateSource
from app.schemas.updates import (
    DashboardStats,
    TimeWindow,
    UpdateFacets,
    UpdateItem,
    UpdateListResponse,
    UpdateSourceItem,
)
from app.services.source_detail import classify_content_detail
from app.services.ingestion_policy import PUBLISHED, stored_ingestion_status
from app.services.article_relevance import stored_relevance_tier


class UpdateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sources(self) -> list[UpdateSourceItem]:
        sources = self.db.scalars(
            select(UpdateSource).where(UpdateSource.enabled.is_(True)).order_by(UpdateSource.name)
        ).all()
        return [
            UpdateSourceItem(
                slug=source.slug,
                name=source.name,
                organization=source.organization,
                tool=source.tool,
                category=source.category,
                source_type=str(source.source_metadata.get("source_type") or "official-release"),
                primary_topic=source.category,
                homepage_url=source.homepage_url,
                last_collected_at=self._utc(source.last_collected_at),
                last_error=source.last_error,
            )
            for source in sources
        ]

    def list_updates(
        self,
        window: TimeWindow,
        limit: int,
        offset: int,
        source_names: list[str] | None = None,
        tools: list[str] | None = None,
        categories: list[str] | None = None,
        event_types: list[str] | None = None,
        source_types: list[str] | None = None,
        maturities: list[str] | None = None,
        include_sparse: bool = False,
        include_contextual: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> UpdateListResponse:
        now = datetime.now(timezone.utc)
        window_end = self._aware(end) if end else now
        window_start = self._aware(start) if start else self.window_start(window, window_end)

        enabled_source_slugs = select(UpdateSource.slug).where(UpdateSource.enabled.is_(True))
        stmt = select(Document).where(
            Document.source_type == "release",
            Document.source_name.in_(enabled_source_slugs),
        )
        if window_start:
            stmt = stmt.where(Document.published_at >= self._naive(window_start))
        stmt = stmt.where(Document.published_at <= self._naive(window_end))
        if source_names:
            stmt = stmt.where(Document.source_name.in_(source_names))
        if tools:
            stmt = stmt.where(Document.doc_metadata["tool"].astext.in_(tools))
        documents = list(self.db.scalars(stmt).all())
        explicit_sparse_context = bool(source_names or tools)
        documents = [
            document
            for document in documents
            if (
                self._is_feed_visible(
                    document,
                    include_sparse=include_sparse,
                    explicit_sparse_context=explicit_sparse_context,
                    include_contextual=include_contextual,
                )
                and self._matches_taxonomy(
                    document,
                    categories=categories,
                    event_types=event_types,
                    source_types=source_types,
                    maturities=maturities,
                )
            )
        ]
        enabled_sources = list(
            self.db.scalars(select(UpdateSource).where(UpdateSource.enabled.is_(True))).all()
        )
        all_updates = list(
            self.db.scalars(
                select(Document).where(
                    Document.source_type == "release",
                    Document.source_name.in_(enabled_source_slugs),
                )
            ).all()
        )
        all_updates = [
            document
            for document in all_updates
            if self._ingestion_status(document) == PUBLISHED
            and self._relevance_is_visible(
                document,
                include_contextual=include_contextual,
            )
        ]
        ranked = sorted(documents, key=lambda document: self.importance_score(document, now), reverse=True)
        page = ranked[offset : offset + limit]
        published_dates = [document.published_at for document in documents if document.published_at]

        return UpdateListResponse(
            window=window,
            window_start=window_start,
            window_end=window_end,
            generated_at=now,
            items=[self._to_item(document, now) for document in page],
            stats=DashboardStats(
                total_updates=len(documents),
                source_count=len({document.source_name for document in documents}),
                tool_count=len({self._metadata(document, "tool") for document in documents}),
                topic_count=len({self._topic(document) for document in documents}),
                latest_published_at=self._utc(max(published_dates)) if published_dates else None,
            ),
            facets=UpdateFacets(
                sources=sorted(source.slug for source in enabled_sources),
                tools=sorted({source.tool for source in enabled_sources}),
                categories=sorted({self._topic(document) for document in all_updates}),
                event_types=sorted(
                    {
                        event_type
                        for document in all_updates
                        for event_type in document.doc_metadata.get("event_types", [])
                    }
                ),
                source_types=sorted(
                    {
                        str(document.doc_metadata.get("source_type") or "official-release")
                        for document in all_updates
                    }
                ),
                maturities=sorted(
                    {
                        str(document.doc_metadata.get("maturity") or "stable")
                        for document in all_updates
                    }
                ),
            ),
            limit=limit,
            offset=offset,
        )

    @staticmethod
    def window_start(window: TimeWindow, end: datetime) -> datetime | None:
        durations = {
            "day": timedelta(days=1),
            "week": timedelta(days=7),
            "month": timedelta(days=30),
        }
        duration = durations.get(window)
        return end - duration if duration else None

    def importance_score(self, document: Document, now: datetime) -> float:
        published_at = self._aware(document.published_at) if document.published_at else now
        age_days = max(0.0, (now - published_at).total_seconds() / 86400)
        freshness = math.exp(-age_days / 21)
        credibility = float(document.doc_metadata.get("credibility_weight", 1.0))
        detail = min(len(document.raw_text) / 4000, 1.0)
        maturity_weights = {
            "stable": 1.0,
            "general-availability": 1.0,
            "beta": 0.75,
            "preview": 0.7,
            "release-candidate": 0.6,
            "development": 0.45,
            "research": 0.75,
            "deprecated": 0.8,
        }
        maturity = str(document.doc_metadata.get("maturity") or "stable")
        maturity_score = maturity_weights.get(maturity, 0.7)
        return round(
            (0.40 * credibility)
            + (0.40 * freshness)
            + (0.10 * detail)
            + (0.10 * maturity_score),
            4,
        )

    def _to_item(self, document: Document, now: datetime) -> UpdateItem:
        metadata = document.doc_metadata
        visibility = self._visibility(document)
        excerpt = metadata.get("excerpt") or document.raw_text[:420]
        return UpdateItem(
            id=str(document.id),
            title=document.title,
            url=document.url,
            source_name=document.source_name,
            organization=self._metadata(document, "organization"),
            tool=self._metadata(document, "tool"),
            category=self._topic(document),
            primary_topic=self._topic(document),
            topic_tags=list(metadata.get("topic_tags") or []),
            event_types=list(metadata.get("event_types") or []),
            entity_tags=list(metadata.get("entity_tags") or []),
            source_type=str(metadata.get("source_type") or "official-release"),
            maturity=str(metadata.get("maturity") or "stable"),
            content_detail=str(visibility["content_detail"]),
            evidence_level=self._evidence_level(document),
            rag_eligible=self._rag_eligible(document),
            relevance_tier=self._relevance_tier(document),
            relevance_reason=str(
                getattr(document, "relevance_reason", None)
                or metadata.get("relevance_reason")
                or "Legacy record retained as core."
            ),
            default_feed_eligible=self._default_feed_eligible(document),
            default_feed_exclusion_reason=visibility["default_feed_exclusion_reason"],
            version=metadata.get("version"),
            excerpt=excerpt,
            display_headline=str(metadata.get("display_headline") or document.title),
            summary=str(metadata.get("summary") or excerpt),
            why_it_matters=str(metadata.get("why_it_matters") or ""),
            key_points=list(metadata.get("key_points") or []),
            published_at=self._utc(document.published_at) or now,
            fetched_at=self._utc(document.fetched_at) or now,
            importance_score=self.importance_score(document, now),
        )

    def _is_feed_visible(
        self,
        document: Document,
        *,
        include_sparse: bool,
        explicit_sparse_context: bool,
        include_contextual: bool = False,
    ) -> bool:
        if self._ingestion_status(document) != PUBLISHED:
            return False
        if not self._relevance_is_visible(
            document,
            include_contextual=include_contextual,
        ):
            return False
        del include_sparse, explicit_sparse_context
        return True

    def _relevance_is_visible(
        self,
        document: Document,
        *,
        include_contextual: bool,
    ) -> bool:
        tier = self._relevance_tier(document)
        return tier == "core" or (include_contextual and tier == "contextual")

    def _relevance_tier(self, document: Document) -> str:
        canonical = getattr(document, "relevance_tier", None)
        return str(canonical) if canonical else stored_relevance_tier(document.doc_metadata)

    def _ingestion_status(self, document: Document) -> str:
        canonical = getattr(document, "ingestion_status", None)
        return str(canonical) if canonical else stored_ingestion_status(document.doc_metadata)

    def _evidence_level(self, document: Document) -> str:
        canonical = getattr(document, "evidence_level", None)
        return str(canonical) if canonical else str(
            document.doc_metadata.get("evidence_level") or "source_entry"
        )

    def _rag_eligible(self, document: Document) -> bool:
        return (
            self._ingestion_status(document) == PUBLISHED
            and self._evidence_level(document) != "official_feed_excerpt"
            and self._relevance_tier(document) != "excluded"
        )

    def _default_feed_eligible(self, document: Document) -> bool:
        return (
            self._ingestion_status(document) == PUBLISHED
            and self._relevance_tier(document) == "core"
        )

    def _visibility(self, document: Document) -> dict[str, str | bool | None]:
        metadata = document.doc_metadata
        content_detail = str(
            metadata.get("content_detail")
            or classify_content_detail(str(document.title or ""), str(document.raw_text or ""))
        )
        default_eligible = self._default_feed_eligible(document)
        reason = None
        if self._ingestion_status(document) != PUBLISHED:
            reason = "ingestion_quarantined"
        elif self._relevance_tier(document) != "core":
            reason = f"relevance_{self._relevance_tier(document)}"
        return {
            "content_detail": content_detail,
            "default_feed_eligible": default_eligible,
            "default_feed_exclusion_reason": reason,
        }

    def _matches_taxonomy(
        self,
        document: Document,
        *,
        categories: list[str] | None,
        event_types: list[str] | None,
        source_types: list[str] | None,
        maturities: list[str] | None,
    ) -> bool:
        metadata = document.doc_metadata
        if categories and self._topic(document) not in categories:
            return False
        if event_types and not set(event_types).intersection(metadata.get("event_types", [])):
            return False
        if source_types and str(metadata.get("source_type") or "official-release") not in source_types:
            return False
        return not maturities or str(metadata.get("maturity") or "stable") in maturities

    def _topic(self, document: Document) -> str:
        return str(
            document.doc_metadata.get("primary_topic")
            or document.doc_metadata.get("category")
            or "developer-tools"
        )

    def _metadata(self, document: Document, key: str) -> str:
        return str(document.doc_metadata.get(key) or "unknown")

    def _utc(self, value: datetime | None) -> datetime | None:
        return self._aware(value) if value else None

    def _aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _naive(self, value: datetime) -> datetime:
        return self._aware(value).replace(tzinfo=None)
