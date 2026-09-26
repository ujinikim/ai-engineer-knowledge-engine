import hashlib
import re
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable
from urllib.parse import urlparse


BOILERPLATE_TERMS = (
    "accept cookies",
    "cookie policy",
    "privacy policy",
    "sign up for",
    "subscribe",
    "share on facebook",
    "share on linkedin",
    "all rights reserved",
    "related articles",
)


@dataclass(frozen=True)
class ExtractionThresholds:
    short_release_characters: int = 100
    short_article_characters: int = 1000
    high_boilerplate_ratio: float = 0.20
    high_duplicate_line_ratio: float = 0.15
    minimum_duplicate_lines: int = 3
    future_date_tolerance_days: int = 1
    collection_date_tolerance_seconds: int = 10


@dataclass(frozen=True)
class ExtractionEvaluation:
    document_id: str
    source_name: str
    title: str
    url: str
    extraction_method: str
    source_category: str
    published_at: str | None
    fetched_at: str | None
    body_characters: int
    word_count: int
    line_count: int
    paragraph_count: int
    chunks_expected: bool
    chunk_count: int
    embedded_chunk_count: int
    total_chunk_tokens: int
    title_present: bool
    valid_url: bool
    content_hash_valid: bool
    chunk_indexes_sequential: bool
    chunks_nonempty: bool
    chunk_hashes_valid: bool
    chunks_traceable_to_document: bool
    embeddings_complete: bool
    publication_date_confidence: str
    suspected_excerpt: bool
    suspected_collection_page: bool
    boilerplate_ratio: float
    duplicate_line_ratio: float
    duplicate_line_count: int
    quality_status: str
    warnings: list[str]
    failures: list[str]

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExtractionQualityService:
    def __init__(self, thresholds: ExtractionThresholds | None = None) -> None:
        self.thresholds = thresholds or ExtractionThresholds()

    def evaluate(
        self,
        document: Any,
        chunks: Iterable[Any],
        *,
        source_kind: str = "unknown",
        now: datetime | None = None,
    ) -> ExtractionEvaluation:
        chunks = sorted(chunks, key=lambda chunk: chunk.chunk_index)
        stored_text = str(document.raw_text or "")
        raw_text = stored_text.strip()
        title = str(document.title or "").strip()
        metadata = dict(document.doc_metadata or {})
        lines = [self._normalize(line) for line in raw_text.splitlines() if line.strip()]
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n", raw_text) if part.strip()]
        words = re.findall(r"\b\w+[+#.-]*\b", raw_text)
        source_category = str(metadata.get("source_type") or "unknown")
        extraction_method = source_kind
        ingestion_status = str(getattr(document, "ingestion_status", None) or "published")
        evidence_level = str(getattr(document, "evidence_level", None) or "source_entry")
        relevance_tier = getattr(document, "relevance_tier", None)
        chunks_expected = (
            ingestion_status == "published"
            and evidence_level != "official_feed_excerpt"
            and relevance_tier in {"core", "contextual"}
        )
        warnings: list[str] = []
        failures: list[str] = []

        valid_url = self._valid_url(str(document.url or ""))
        title_present = bool(title and title.lower() in raw_text[: max(1000, len(title) * 3)].lower())
        content_hash_valid = bool(
            raw_text
            and document.content_hash
            and hashlib.sha256(stored_text.encode("utf-8")).hexdigest() == document.content_hash
        )
        chunk_indexes_sequential = [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
        chunks_nonempty = bool(chunks) and all(str(chunk.content or "").strip() for chunk in chunks)
        chunk_hashes_valid = bool(chunks) and all(
            hashlib.sha256(str(chunk.content).encode("utf-8")).hexdigest() == chunk.content_hash
            for chunk in chunks
            if chunk.content
        )
        chunks_traceable = bool(chunks) and all(
            self._normalize(str(chunk.content or "")) in self._normalize(raw_text) for chunk in chunks
        )
        embedded_chunk_count = sum(1 for chunk in chunks if self._has_embedding(chunk.embedding))
        embeddings_complete = bool(chunks) and embedded_chunk_count == len(chunks)
        total_chunk_tokens = sum(max(0, int(chunk.token_count or 0)) for chunk in chunks)
        duplicate_line_ratio, duplicate_line_count = self._duplicate_line_stats(lines)
        boilerplate_ratio = self._boilerplate_ratio(lines)
        suspected_excerpt = self._suspected_excerpt(len(raw_text), source_category, extraction_method)
        suspected_collection_page = self._suspected_collection_page(
            str(document.url or ""),
            extraction_method,
        )
        date_confidence = self._date_confidence(document, now or datetime.now(), warnings)

        if not raw_text:
            failures.append("empty_body")
        if not title:
            failures.append("missing_title")
        elif not title_present:
            warnings.append("title_not_found_in_body")
        if not valid_url:
            failures.append("invalid_url")
        if raw_text and not content_hash_valid:
            failures.append("content_hash_mismatch")
        if chunks_expected and not chunks:
            failures.append("missing_chunks")
        elif chunks:
            if not chunk_indexes_sequential:
                failures.append("nonsequential_chunk_indexes")
            if not chunks_nonempty:
                failures.append("empty_chunk")
            if not chunk_hashes_valid:
                failures.append("chunk_hash_mismatch")
            if not chunks_traceable:
                warnings.append("chunk_not_traceable_to_document")
            if not embeddings_complete:
                failures.append("missing_chunk_embedding")
            if any(int(chunk.token_count or 0) <= 0 for chunk in chunks):
                failures.append("invalid_chunk_token_count")
        if suspected_excerpt:
            warnings.append("suspected_excerpt")
        if suspected_collection_page:
            warnings.append("suspected_collection_page")
        if (
            metadata.get("extraction_status") in {"feed_excerpt_only", "title_only"}
            or metadata.get("hydration_status") == "failed"
        ):
            warnings.append("article_hydration_failed")
        if boilerplate_ratio > self.thresholds.high_boilerplate_ratio:
            warnings.append("high_boilerplate_ratio")
        if (
            extraction_method != "github_releases"
            and duplicate_line_ratio > self.thresholds.high_duplicate_line_ratio
            and duplicate_line_count >= self.thresholds.minimum_duplicate_lines
        ):
            warnings.append("high_duplicate_line_ratio")

        status = "fail" if failures else "warning" if warnings else "pass"
        return ExtractionEvaluation(
            document_id=str(document.id),
            source_name=str(document.source_name),
            title=title,
            url=str(document.url or ""),
            extraction_method=extraction_method,
            source_category=source_category,
            published_at=self._iso(document.published_at),
            fetched_at=self._iso(document.fetched_at),
            body_characters=len(raw_text),
            word_count=len(words),
            line_count=len(lines),
            paragraph_count=len(paragraphs),
            chunks_expected=chunks_expected,
            chunk_count=len(chunks),
            embedded_chunk_count=embedded_chunk_count,
            total_chunk_tokens=total_chunk_tokens,
            title_present=title_present,
            valid_url=valid_url,
            content_hash_valid=content_hash_valid,
            chunk_indexes_sequential=chunk_indexes_sequential,
            chunks_nonempty=chunks_nonempty,
            chunk_hashes_valid=chunk_hashes_valid,
            chunks_traceable_to_document=chunks_traceable,
            embeddings_complete=embeddings_complete,
            publication_date_confidence=date_confidence,
            suspected_excerpt=suspected_excerpt,
            suspected_collection_page=suspected_collection_page,
            boilerplate_ratio=round(boilerplate_ratio, 4),
            duplicate_line_ratio=round(duplicate_line_ratio, 4),
            duplicate_line_count=duplicate_line_count,
            quality_status=status,
            warnings=list(dict.fromkeys(warnings)),
            failures=list(dict.fromkeys(failures)),
        )

    def aggregate(self, evaluations: list[ExtractionEvaluation]) -> dict[str, Any]:
        statuses = Counter(item.quality_status for item in evaluations)
        warning_counts = Counter(warning for item in evaluations for warning in item.warnings)
        failure_counts = Counter(failure for item in evaluations for failure in item.failures)
        by_source: dict[str, Counter[str]] = defaultdict(Counter)
        by_method: dict[str, Counter[str]] = defaultdict(Counter)
        for item in evaluations:
            by_source[item.source_name][item.quality_status] += 1
            by_method[item.extraction_method][item.quality_status] += 1

        return {
            "documents_evaluated": len(evaluations),
            "status_counts": self._complete_counts(statuses),
            "warning_counts": dict(warning_counts.most_common()),
            "failure_counts": dict(failure_counts.most_common()),
            "by_source": {
                source: self._complete_counts(counts) for source, counts in sorted(by_source.items())
            },
            "by_extraction_method": {
                method: self._complete_counts(counts) for method, counts in sorted(by_method.items())
            },
        }

    def _suspected_collection_page(self, url: str, extraction_method: str) -> bool:
        if extraction_method != "html_listing":
            return False
        path = urlparse(url).path.lower()
        markers = ("/tag/", "/category/", "/search/", "/page/")
        return any(marker in path for marker in markers)

    def select_review_sample(
        self,
        evaluations: list[ExtractionEvaluation],
        sample_size: int,
    ) -> list[ExtractionEvaluation]:
        if sample_size <= 0:
            return []
        ordered = sorted(
            evaluations,
            key=lambda item: (
                {"fail": 0, "warning": 1, "pass": 2}[item.quality_status],
                item.source_name,
                item.document_id,
            ),
        )
        selected: list[ExtractionEvaluation] = []
        seen_ids: set[str] = set()

        for source in sorted({item.source_name for item in ordered}):
            source_item = next(item for item in ordered if item.source_name == source)
            self._append_unique(selected, seen_ids, source_item)
            if len(selected) >= sample_size:
                return selected

        candidate_groups = [
            iter(ordered),
            iter(sorted(evaluations, key=lambda item: item.body_characters)),
            iter(sorted(evaluations, key=lambda item: item.body_characters, reverse=True)),
        ]
        while len(selected) < sample_size:
            added = False
            for candidates in candidate_groups:
                for item in candidates:
                    if item.document_id not in seen_ids:
                        self._append_unique(selected, seen_ids, item)
                        added = True
                        break
                if len(selected) >= sample_size:
                    break
            if not added:
                break
        return selected

    def _date_confidence(self, document: Any, now: datetime, warnings: list[str]) -> str:
        published_at = document.published_at
        if not published_at:
            warnings.append("missing_published_at")
            return "missing"
        if published_at > now + timedelta(days=self.thresholds.future_date_tolerance_days):
            warnings.append("future_published_at")
            return "low"
        fetched_at = document.fetched_at
        if fetched_at and abs((fetched_at - published_at).total_seconds()) <= (
            self.thresholds.collection_date_tolerance_seconds
        ):
            warnings.append("published_at_matches_collection_time")
            return "low"
        return "high"

    def _suspected_excerpt(self, length: int, source_category: str, method: str) -> bool:
        if method == "github_releases" or source_category == "official-changelog":
            return False
        is_release = source_category == "official-release"
        minimum = (
            self.thresholds.short_release_characters
            if is_release
            else self.thresholds.short_article_characters
        )
        return 0 < length < minimum

    def _boilerplate_ratio(self, lines: list[str]) -> float:
        if not lines:
            return 0.0
        hits = sum(
            1 for line in lines if any(term in line.lower() for term in BOILERPLATE_TERMS)
        )
        return hits / len(lines)

    def _duplicate_line_stats(self, lines: list[str]) -> tuple[float, int]:
        meaningful = [line.lower() for line in lines if self._duplicate_candidate(line)]
        if not meaningful:
            return 0.0, 0
        counts = Counter(meaningful)
        duplicates = sum(count - 1 for count in counts.values() if count > 1)
        return duplicates / len(meaningful), duplicates

    def _duplicate_candidate(self, line: str) -> bool:
        stripped = line.strip()
        if len(stripped) < 80 or stripped.lower().startswith(("http", "#", "//")):
            return False
        words = re.findall(r"[a-zA-Z]{2,}", stripped)
        if len(words) < 12:
            return False
        code_symbols = sum(stripped.count(symbol) for symbol in "{}[]=<>\\")
        return code_symbols / len(stripped) < 0.08

    def _valid_url(self, value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    def _has_embedding(self, value: Any) -> bool:
        if value is None:
            return False
        try:
            return len(value) > 0
        except TypeError:
            return True

    def _normalize(self, value: str) -> str:
        return " ".join(value.split())

    def _iso(self, value: datetime | None) -> str | None:
        return value.isoformat() if value else None

    def _complete_counts(self, counts: Counter[str]) -> dict[str, int]:
        return {status: counts.get(status, 0) for status in ("pass", "warning", "fail")}

    def _append_unique(
        self,
        selected: list[ExtractionEvaluation],
        seen_ids: set[str],
        item: ExtractionEvaluation,
    ) -> None:
        if item.document_id not in seen_ids:
            selected.append(item)
            seen_ids.add(item.document_id)
