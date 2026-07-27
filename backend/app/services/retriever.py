import math
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import Chunk, Document
from app.schemas.search import RetrievedChunk, RetrievalMetrics, SearchRequest, SearchResponse
from app.services.embedding import EmbeddingService


@dataclass
class Candidate:
    chunk: Chunk
    document: Document
    vector_similarity: float | None = None
    keyword_score: float | None = None
    keyword_normalized: float | None = None
    recency_score: float = 0
    combined_score: float = 0


class RetrieverService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.embedding_service = EmbeddingService()

    def search(self, request: SearchRequest) -> SearchResponse:
        started = time.perf_counter()
        embedding_started = time.perf_counter()
        query_embedding = None
        if request.search_mode in {"vector", "hybrid"}:
            query_embedding = self.embedding_service.embed_texts([request.query])[0]
        embedding_ms = self._elapsed_ms(embedding_started)

        retrieval_started = time.perf_counter()
        if request.retrieval_strategy == "source_balanced":
            candidates = self._source_balanced_candidates(request, query_embedding)
        else:
            candidates = self._standard_candidates(request, query_embedding)
        retrieval_ms = self._elapsed_ms(retrieval_started)

        ranked_candidates = self._rank_candidates(candidates, request.search_mode)
        selected_candidates = self._diversify_documents(ranked_candidates, request.top_k)
        results = [
            self._to_retrieved_chunk(candidate)
            for candidate in selected_candidates
        ]

        return SearchResponse(
            query=request.query,
            results=results,
            metrics=RetrievalMetrics(
                embedding_ms=embedding_ms,
                retrieval_ms=retrieval_ms,
                total_ms=self._elapsed_ms(started),
            ),
        )

    def _standard_candidates(
        self,
        request: SearchRequest,
        query_embedding: list[float] | None,
    ) -> list[Candidate]:
        candidates: dict[str, Candidate] = {}
        candidate_limit = max(request.top_k * 5, 30)

        if request.search_mode in {"vector", "hybrid"} and query_embedding is not None:
            for candidate in self._vector_candidates(request, query_embedding, candidate_limit):
                candidates[str(candidate.chunk.id)] = candidate

        if request.search_mode in {"keyword", "hybrid"}:
            for candidate in self._keyword_candidates(request, candidate_limit):
                existing = candidates.get(str(candidate.chunk.id))
                if existing:
                    existing.keyword_score = candidate.keyword_score
                else:
                    candidates[str(candidate.chunk.id)] = candidate

        return list(candidates.values())

    def _source_balanced_candidates(
        self,
        request: SearchRequest,
        query_embedding: list[float] | None,
    ) -> list[Candidate]:
        sources = request.source_names or self._available_sources()
        if not sources:
            return self._standard_candidates(request, query_embedding)

        merged: dict[str, Candidate] = {}
        per_source_k = max(2, min(6, request.top_k))
        for source in sources:
            source_request = request.model_copy(
                update={
                    "source_names": [source],
                    "top_k": per_source_k,
                    "retrieval_strategy": "standard",
                }
            )
            for candidate in self._standard_candidates(source_request, query_embedding):
                existing = merged.get(str(candidate.chunk.id))
                if existing:
                    existing.vector_similarity = max_optional(
                        existing.vector_similarity,
                        candidate.vector_similarity,
                    )
                    existing.keyword_score = max_optional(existing.keyword_score, candidate.keyword_score)
                else:
                    merged[str(candidate.chunk.id)] = candidate

        return list(merged.values())

    def _vector_candidates(
        self,
        request: SearchRequest,
        query_embedding: list[float],
        limit: int,
    ) -> list[Candidate]:
        distance = Chunk.embedding.cosine_distance(query_embedding)
        stmt = self._apply_filters(
            (
            select(Chunk, Document, distance.label("distance"))
            .join(Document, Chunk.document_id == Document.id)
            .order_by(distance)
            .limit(limit)
            ),
            request,
        )

        rows = self.db.execute(stmt).all()
        return [
            Candidate(
                chunk=chunk,
                document=document,
                vector_similarity=round(1 - float(row_distance), 4),
                recency_score=self._recency_score(document),
            )
            for chunk, document, row_distance in rows
        ]

    def _keyword_candidates(self, request: SearchRequest, limit: int) -> list[Candidate]:
        terms = self._keyword_terms(request.query)
        if not terms:
            return []

        stmt = self._apply_filters(
            select(Chunk, Document).join(Document, Chunk.document_id == Document.id),
            request,
        )

        candidates: list[Candidate] = []
        for chunk, document in self.db.execute(stmt).all():
            score = self._keyword_match_score(
                request.query,
                terms,
                str(document.title or ""),
                str(chunk.content or ""),
            )
            if score == 0:
                continue

            candidates.append(
                Candidate(
                    chunk=chunk,
                    document=document,
                    keyword_score=round(score, 4),
                    recency_score=self._recency_score(document),
                )
            )

        return sorted(candidates, key=lambda candidate: candidate.keyword_score or 0, reverse=True)[
            :limit
        ]

    def _keyword_terms(self, query: str) -> list[str]:
        stop_words = {
            "about",
            "across",
            "all",
            "and",
            "are",
            "best",
            "compare",
            "changed",
            "change",
            "candidate",
            "docs",
            "documents",
            "did",
            "does",
            "for",
            "from",
            "how",
            "mentioning",
            "principal",
            "published",
            "release",
            "releases",
            "show",
            "the",
            "update",
            "updates",
            "what",
            "when",
            "where",
            "which",
            "with",
            "work",
            "would",
        }
        terms = [
            {
                "fixed": "fix",
                "fixes": "fix",
                "fixing": "fix",
            }.get(term, term)
            for term in re.findall(r"[a-zA-Z0-9_+-]+", query.lower())
            if len(term) > 2 and term not in stop_words
        ]
        return list(dict.fromkeys(terms))

    def _keyword_match_score(
        self,
        query: str,
        terms: list[str],
        title: str,
        content: str,
    ) -> float:
        if not terms:
            return 0
        normalized_title = title.lower()
        normalized_content = content.lower()
        title_matches = sum(term in normalized_title for term in terms)
        content_matches = sum(term in normalized_content for term in terms)
        phrase = query.lower()
        phrase_bonus = 0.5 if phrase in f"{normalized_title}\n{normalized_content}" else 0
        # Title matches are strong document-identity evidence. Counting them
        # separately prevents long changelogs from outranking a sparse exact release
        # merely because the changelog repeats more generic query terms.
        return round(
            (content_matches / len(terms))
            + (title_matches / len(terms))
            + phrase_bonus,
            4,
        )

    def _rank_candidates(self, candidates: list[Candidate], search_mode: str) -> list[Candidate]:
        max_keyword = max((candidate.keyword_score or 0 for candidate in candidates), default=0)

        def score(candidate: Candidate) -> float:
            vector_score = candidate.vector_similarity or 0
            keyword_score = 0
            if max_keyword > 0 and candidate.keyword_score is not None:
                keyword_score = candidate.keyword_score / max_keyword
            candidate.keyword_normalized = round(keyword_score, 4)

            if search_mode == "vector":
                candidate.combined_score = vector_score
                return candidate.combined_score
            if search_mode == "keyword":
                candidate.combined_score = keyword_score
                return candidate.combined_score
            if candidate.document.source_type == "release":
                candidate.combined_score = (
                    (0.60 * vector_score)
                    + (0.25 * keyword_score)
                    + (0.15 * candidate.recency_score)
                )
            else:
                candidate.combined_score = (0.7 * vector_score) + (0.3 * keyword_score)
            return candidate.combined_score

        return sorted(candidates, key=score, reverse=True)

    def _to_retrieved_chunk(self, candidate: Candidate) -> RetrievedChunk:
        keyword_score = candidate.keyword_normalized or 0
        display_score = candidate.vector_similarity if candidate.vector_similarity is not None else keyword_score
        if candidate.vector_similarity is not None and candidate.keyword_score is not None:
            display_score = candidate.combined_score

        return RetrievedChunk(
            chunk_id=str(candidate.chunk.id),
            document_id=str(candidate.document.id),
            document_title=candidate.document.title,
            source_name=candidate.document.source_name,
            url=candidate.document.url,
            content=candidate.chunk.content,
            similarity=round(display_score, 4),
            chunk_index=candidate.chunk.chunk_index,
            vector_similarity=candidate.vector_similarity,
            keyword_score=candidate.keyword_score,
            combined_score=round(candidate.combined_score, 4),
            recency_score=round(candidate.recency_score, 4),
            source_type=candidate.document.source_type,
            published_at=candidate.document.published_at,
            tool=candidate.document.doc_metadata.get("tool"),
            category=(
                candidate.document.doc_metadata.get("primary_topic")
                or candidate.document.doc_metadata.get("category")
            ),
            event_types=list(candidate.document.doc_metadata.get("event_types") or []),
            source_category=candidate.document.doc_metadata.get("source_type"),
            maturity=candidate.document.doc_metadata.get("maturity"),
        )

    def _apply_filters(self, stmt, request: SearchRequest):
        if request.source_names:
            stmt = stmt.where(Document.source_name.in_(request.source_names))
        if request.collection == "docs":
            stmt = stmt.where(Document.source_type == "docs")
        elif request.collection == "updates":
            stmt = stmt.where(Document.source_type == "release")
        if request.tools:
            stmt = stmt.where(Document.doc_metadata["tool"].astext.in_(request.tools))
        if request.categories:
            stmt = stmt.where(
                or_(
                    Document.doc_metadata["primary_topic"].astext.in_(request.categories),
                    Document.doc_metadata["category"].astext.in_(request.categories),
                )
            )
        if request.event_types:
            stmt = stmt.where(
                or_(
                    *[
                        Document.doc_metadata["event_types"].contains([event_type])
                        for event_type in request.event_types
                    ]
                )
            )
        if request.source_types:
            stmt = stmt.where(Document.doc_metadata["source_type"].astext.in_(request.source_types))
        if request.maturities:
            stmt = stmt.where(Document.doc_metadata["maturity"].astext.in_(request.maturities))
        if request.published_after:
            stmt = stmt.where(Document.published_at >= self._naive_utc(request.published_after))
        if request.published_before:
            stmt = stmt.where(Document.published_at <= self._naive_utc(request.published_before))
        return stmt

    def _recency_score(self, document: Document) -> float:
        if document.source_type != "release" or not document.published_at:
            return 0
        published = document.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (datetime.now(timezone.utc) - published).total_seconds() / 86400)
        return round(math.exp(-age_days / 21), 4)

    def _naive_utc(self, value: datetime) -> datetime:
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def _available_sources(self) -> list[str]:
        return list(self.db.scalars(select(Document.source_name).distinct()).all())

    def _diversify_documents(
        self,
        candidates: list[Candidate],
        limit: int,
        max_per_document: int = 2,
    ) -> list[Candidate]:
        selected: list[Candidate] = []
        counts: dict[str, int] = {}
        for candidate in candidates:
            document_id = str(candidate.document.id)
            if counts.get(document_id, 0) >= max_per_document:
                continue
            selected.append(candidate)
            counts[document_id] = counts.get(document_id, 0) + 1
            if len(selected) == limit:
                break
        return selected

    def _elapsed_ms(self, started: float) -> int:
        return int((time.perf_counter() - started) * 1000)


def max_optional(left: float | None, right: float | None) -> float | None:
    if left is None:
        return right
    if right is None:
        return left
    return max(left, right)
