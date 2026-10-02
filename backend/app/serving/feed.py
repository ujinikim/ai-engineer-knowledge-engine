import math
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CollectionSourceRun, Document
from app.domain import article_excerpt
from app.schemas.updates import (
    DashboardStats,
    TimeWindow,
    UpdateFacets,
    UpdateItem,
    UpdateListResponse,
    UpdateSourceItem,
)
from app.serving.visibility import visible_article_clause
from app.sources import (
    configured_active_source_slugs,
    configured_sources,
    source_attribute,
    source_slugs_with,
)


DEFAULT_TOPIC = "developer-tools"  # shown for an article stored without a topic
DEFAULT_SOURCE_TYPE = "official-release"


class FeedService:
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
        include_contextual: bool = False,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> UpdateListResponse:
        now = datetime.now(timezone.utc)
        window_end = self._aware(end) if end else now
        window_start = self._aware(start) if start else self.window_start(window, window_end)

        visible = visible_article_clause(include_contextual=include_contextual)
        stmt = select(Document).where(visible)
        if window_start:
            stmt = stmt.where(Document.published_at >= self._naive(window_start))
        stmt = stmt.where(Document.published_at <= self._naive(window_end))
        if source_names:
            stmt = stmt.where(Document.source_name.in_(source_names))
        if tools:
            stmt = stmt.where(Document.source_name.in_(source_slugs_with("tool", tools)))
        if categories:
            stmt = stmt.where(func.coalesce(Document.primary_topic, DEFAULT_TOPIC).in_(categories))
        if event_types:
            stmt = stmt.where(Document.event_types.overlap(event_types))
        if source_types:
            stmt = stmt.where(
                Document.source_name.in_(source_slugs_with("source_type", source_types, DEFAULT_SOURCE_TYPE))
            )
        documents = list(self.db.scalars(stmt).all())
        enabled_sources = configured_sources()
        # Facets describe everything visible, not just the current page of filters.
        all_updates = list(self.db.scalars(select(Document).where(visible)).all())
        # Equal scores are common (date-only publish dates), so break ties explicitly:
        # newest first, then by id, so the order never depends on the database's row order.
        ranked = sorted(
            documents,
            key=lambda document: (
                self.importance_score(document, now),
                document.published_at or datetime.min,
                str(document.id),
            ),
            reverse=True,
        )
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
            relevance_tier=document.relevance_tier,
            relevance_reason=document.relevance_reason or "",
            excerpt=excerpt,
            display_headline=document.display_headline or document.title,
            summary=document.summary or excerpt,
            why_it_matters=document.why_it_matters or "",
            key_points=list(document.key_points or []),
            published_at=self._utc(document.published_at) or now,
            fetched_at=self._utc(document.fetched_at) or now,
            importance_score=self.importance_score(document, now),
        )

    def _topic(self, document: Document) -> str:
        return document.primary_topic or DEFAULT_TOPIC

    def _source(self, document: Document, key: str) -> str:
        return str(source_attribute(document.source_name, key) or "unknown")

    def _source_type(self, document: Document) -> str:
        return str(source_attribute(document.source_name, "source_type", DEFAULT_SOURCE_TYPE))

    def _utc(self, value: datetime | None) -> datetime | None:
        return self._aware(value) if value else None

    def _aware(self, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _naive(self, value: datetime) -> datetime:
        return self._aware(value).replace(tzinfo=None)
