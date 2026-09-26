from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def normalize_list(value: object, *, lowercase: bool = False) -> object:
    if value is None or not isinstance(value, list):
        return value

    normalized = []
    for item in value:
        if isinstance(item, str):
            item = item.strip()
            if lowercase:
                item = item.lower()
        normalized.append(item)
    return list(dict.fromkeys(normalized)) or None


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=6, ge=1, le=20)
    source_names: list[str] | None = None
    tools: list[str] | None = None
    categories: list[str] | None = None
    event_types: list[str] | None = None
    source_types: list[str] | None = None
    include_contextual: bool = False
    collection: Literal["updates"] = "updates"
    published_after: datetime | None = None
    published_before: datetime | None = None
    search_mode: Literal["vector", "keyword", "hybrid"] = "hybrid"
    retrieval_strategy: Literal["standard", "source_balanced"] = "standard"

    @field_validator(
        "source_names",
        "categories",
        "event_types",
        "source_types",
        mode="before",
    )
    @classmethod
    def validate_source_names(cls, value: object) -> object:
        return normalize_list(value, lowercase=True)

    @field_validator("tools", mode="before")
    @classmethod
    def validate_tools(cls, value: object) -> object:
        return normalize_list(value)


class RetrievedChunk(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_name: str
    url: str
    content: str
    similarity: float
    chunk_index: int
    vector_similarity: float | None = None
    keyword_score: float | None = None
    combined_score: float | None = None
    recency_score: float | None = None
    published_at: datetime | None = None
    tool: str | None = None
    category: str | None = None
    event_types: list[str] = Field(default_factory=list)
    source_category: str | None = None
    relevance_tier: Literal["core", "contextual", "excluded"] | None = None


class RetrievalMetrics(BaseModel):
    embedding_ms: int = 0
    retrieval_ms: int = 0
    total_ms: int = 0


class SearchResponse(BaseModel):
    query: str
    results: list[RetrievedChunk]
    metrics: RetrievalMetrics
