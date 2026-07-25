from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


TimeWindow = Literal["day", "week", "month", "all"]


class UpdateSourceItem(BaseModel):
    slug: str
    name: str
    organization: str
    tool: str
    category: str
    source_type: str
    primary_topic: str
    homepage_url: str
    last_collected_at: datetime | None = None
    last_error: str | None = None


class UpdateItem(BaseModel):
    id: str
    title: str
    url: str
    source_name: str
    organization: str
    tool: str
    category: str
    primary_topic: str
    topic_tags: list[str] = Field(default_factory=list)
    event_types: list[str] = Field(default_factory=list)
    entity_tags: list[str] = Field(default_factory=list)
    source_type: str
    maturity: str
    version: str | None = None
    excerpt: str
    display_headline: str
    summary: str
    why_it_matters: str
    key_points: list[str] = Field(default_factory=list)
    published_at: datetime
    fetched_at: datetime
    importance_score: float


class DashboardStats(BaseModel):
    total_updates: int
    source_count: int
    tool_count: int
    topic_count: int
    latest_published_at: datetime | None = None


class UpdateFacets(BaseModel):
    sources: list[str]
    tools: list[str]
    categories: list[str]
    event_types: list[str]
    source_types: list[str]
    maturities: list[str]


class UpdateListResponse(BaseModel):
    window: TimeWindow
    window_start: datetime | None
    window_end: datetime
    generated_at: datetime
    items: list[UpdateItem]
    stats: DashboardStats
    facets: UpdateFacets
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)
