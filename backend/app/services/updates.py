import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CollectionSourceRun, Document
from app.schemas.updates import (
    DashboardStats,
    TimeWindow,
    UpdateFacets,
    UpdateItem,
    UpdateListResponse,
    UpdateSourceItem,
)
from app.services.ingestion_policy import PUBLISHED, evidence_level
from app.services.article_relevance import visible_relevance_tiers
from app.services.source_extraction import article_excerpt
from app.services.update_visibility import (
    configured_active_source_slugs,
    configured_sources,
    source_attribute,
    source_slugs_with,
)


class UpdateService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_sources(self) -> list[UpdateSourceItem]:
        def latest_runs_for(status: str | None = None) -> dict[str, CollectionSourceRun]:
            stmt = select(CollectionSourceRun).where(
                CollectionSourceRun.source_slug.in_(configured_active_source_slugs())
            )
            if status is not None:
                stmt = stmt.where(CollectionSourceRun.status == status)
            runs = self.db.scalars(
                stmt.distinct(CollectionSourceRun.source_slug).order_by(
                    CollectionSourceRun.source_slug,
                    CollectionSourceRun.finished_at.desc(),
                    CollectionSourceRun.id.desc(),
                )
            ).all()
            return {run.source_slug: run for run in runs}

        latest_by_slug = latest_runs_for()
        latest_success_by_slug = latest_runs_for("completed")
        return [
            UpdateSourceItem(
                slug=source["slug"],
                name=source["name"],
                organization=source["organization"],
                tool=source["tool"],
                category=source.get("default_primary_topic", source["category"]),
                source_type=source.get("source_type", "official-release"),
                primary_topic=source.get("default_primary_topic", source["category"]),
                homepage_url=source["homepage_url"],
                last_collected_at=self._utc(latest_success_by_slug[source["slug"]].finished_at)
                if source["slug"] in latest_success_by_slug else None,
                last_error=latest_by_slug[source["slug"]].error
                if source["slug"] in latest_by_slug else None,
            )
            for source in sorted(configured_sources(), key=lambda source: source["name"])
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
        include_sparse: bool = False,
        include_contextual: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> UpdateListResponse:
        now = datetime.now(timezone.utc)
        window_end = self._aware(end) if end else now
        window_start = self._aware(start) if start else self.window_start(window, window_end)

        enabled_sources = configured_active_source_slugs()
        stmt = select(Document).where(
            Document.source_name.in_(enabled_sources),
        )
        if window_start:
            stmt = stmt.where(Document.published_at >= self._naive(window_start))
        stmt = stmt.where(Document.published_at <= self._naive(window_end))
        if source_names:
            stmt = stmt.where(Document.source_name.in_(source_names))
        if tools:
            stmt = stmt.where(Document.source_name.in_(source_slugs_with("tool", tools)))
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
                )
            )
        ]
        enabled_sources = configured_sources()
        all_updates = list(
            self.db.scalars(
                select(Document).where(
                    Document.source_name.in_(configured_active_source_slugs()),
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
                tool_count=len({self._source(document, "tool") for document in documents}),
                topic_count=len({self._topic(document) for document in documents}),
                latest_published_at=self._utc(max(published_dates)) if published_dates else None,
            ),
            facets=UpdateFacets(
                sources=sorted(source["slug"] for source in enabled_sources),
                tools=sorted({source["tool"] for source in enabled_sources}),
                categories=sorted({self._topic(document) for document in all_updates}),
                event_types=sorted(
                    {
                        event_type
                        for document in all_updates
                        for event_type in document.event_types or []
                    }
                ),
                source_types=sorted({self._source_type(document) for document in all_updates}),
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
        credibility = float(source_attribute(document.source_name, "credibility_weight", 1.0))
        detail = min(len(document.raw_text) / 4000, 1.0)
        return round(
            (0.45 * credibility)
            + (0.45 * freshness)
            + (0.10 * detail),
            4,
        )

    def _to_item(self, document: Document, now: datetime) -> UpdateItem:
        excerpt = article_excerpt(document.title, document.raw_text)
        return UpdateItem(
            id=str(document.id),
            title=document.title,
            url=document.url,
            source_name=document.source_name,
            organization=self._source(document, "organization"),
            tool=self._source(document, "tool"),
            category=self._topic(document),
            primary_topic=self._topic(document),
            event_types=list(document.event_types or []),
            source_type=self._source_type(document),
            evidence_level=evidence_level(
                extraction_status=document.extraction_status,
                ingestion_status=self._ingestion_status(document),
            ),
            relevance_tier=self._relevance_tier(document),
            relevance_reason=str(
                getattr(document, "relevance_reason", None)
                or ""
            ),
            excerpt=excerpt,
            display_headline=document.display_headline or document.title,
            summary=document.summary or excerpt,
            why_it_matters=document.why_it_matters or "",
            key_points=list(document.key_points or []),
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
        return tier in visible_relevance_tiers(include_contextual=include_contextual)

    def _relevance_tier(self, document: Document) -> str | None:
        canonical = getattr(document, "relevance_tier", None)
        return str(canonical) if canonical in {"core", "contextual", "excluded"} else None

    def _ingestion_status(self, document: Document) -> str:
        canonical = getattr(document, "ingestion_status", None)
        return str(canonical) if canonical else PUBLISHED

    def _matches_taxonomy(
        self,
        document: Document,
        *,
        categories: list[str] | None,
        event_types: list[str] | None,
        source_types: list[str] | None,
    ) -> bool:
        if categories and self._topic(document) not in categories:
            return False
        if event_types and not set(event_types).intersection(document.event_types or []):
            return False
        if source_types and self._source_type(document) not in source_types:
            return False
        return True

    def _topic(self, document: Document) -> str:
        return str(
            getattr(document, "primary_topic", None)
            or "developer-tools"
        )

    def _source(self, document: Document, key: str) -> str:
        return str(source_attribute(document.source_name, key) or "unknown")

    def _source_type(self, document: Document) -> str:
        return str(source_attribute(document.source_name, "source_type", "official-release"))

    def _utc(self, value: datetime | None) -> datetime | None:
        return self._aware(value) if value else None

    def _aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _naive(self, value: datetime) -> datetime:
        return self._aware(value).replace(tzinfo=None)
