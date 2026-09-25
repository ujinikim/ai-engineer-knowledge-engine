from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.search import RetrievedChunk, normalize_list


class AskRequest(BaseModel):
    question: str
    top_k: int = Field(default=6, ge=1, le=20)
    source_names: list[str] | None = None
    tools: list[str] | None = None
    categories: list[str] | None = None
    event_types: list[str] | None = None
    source_types: list[str] | None = None
    maturities: list[str] | None = None
    include_contextual: bool = False
    collection: Literal["updates"] = "updates"
    published_after: datetime | None = None
    published_before: datetime | None = None
    min_similarity: float = Field(default=0.35, ge=0, le=1)
    search_mode: Literal["vector", "keyword", "hybrid"] = "hybrid"
    retrieval_strategy: Literal["standard", "source_balanced"] = "standard"
    max_completion_tokens: int = Field(default=300, ge=50, le=1200)
    max_context_tokens: int = Field(default=3500, ge=500, le=12000)

    @field_validator(
        "source_names",
        "categories",
        "event_types",
        "source_types",
        "maturities",
        mode="before",
    )
    @classmethod
    def validate_source_names(cls, value: object) -> object:
        return normalize_list(value, lowercase=True)

    @field_validator("tools", mode="before")
    @classmethod
    def validate_tools(cls, value: object) -> object:
        return normalize_list(value)


class Citation(BaseModel):
    id: int
    title: str
    url: str
    chunk_id: str


class AnswerMetrics(BaseModel):
    embedding_ms: int = 0
    retrieval_ms: int = 0
    llm_ms: int = 0
    total_ms: int = 0
    context_tokens: int = 0
    completion_tokens: int = 0
    estimated_cost_usd: float = 0


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    retrieved_chunks: list[RetrievedChunk]
    context_chunks: list[RetrievedChunk] = Field(default_factory=list)
    metrics: AnswerMetrics
    retrieval_warning: str | None = None
    citation_warnings: list[str] = Field(default_factory=list)
    generation_warnings: list[str] = Field(default_factory=list)
