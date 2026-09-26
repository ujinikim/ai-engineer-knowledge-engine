import argparse
import json
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal
from app.schemas.search import RetrievedChunk, SearchRequest
from app.services.retriever import RetrieverService


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_QUESTIONS = (
    ROOT
    / "data"
    / "eval"
    / "retrieval"
    / "updates_questions_2026-07-27.yml"
)
DEFAULT_SNAPSHOT = (
    ROOT
    / "data"
    / "eval"
    / "retrieval"
    / "updates_snapshot_2026-07-27.json"
)
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "eval"
    / "retrieval"
    / "updates_baseline.json"
)
SEARCH_MODES = ("vector", "keyword", "hybrid")
RETRIEVAL_STRATEGIES = ("standard", "source_balanced")


def unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(values))


def first_relevant_rank(
    retrieved_document_ids: list[str],
    relevant_document_ids: set[str],
) -> int | None:
    for index, document_id in enumerate(retrieved_document_ids, start=1):
        if document_id in relevant_document_ids:
            return index
    return None


def retrieval_metrics(
    retrieved_document_ids: list[str],
    relevant_document_ids: list[str],
) -> dict[str, float | int | None]:
    relevant = set(relevant_document_ids)
    if not relevant:
        return {
            "recall_at_k": None,
            "precision_at_k": None,
            "reciprocal_rank": None,
            "first_relevant_rank": None,
            "all_relevant_documents_hit": None,
        }

    unique_retrieved = unique(retrieved_document_ids)
    hits = relevant.intersection(unique_retrieved)
    rank = first_relevant_rank(retrieved_document_ids, relevant)
    return {
        "recall_at_k": round(len(hits) / len(relevant), 4),
        "precision_at_k": round(len(hits) / len(unique_retrieved), 4)
        if unique_retrieved
        else 0.0,
        "reciprocal_rank": round(1 / rank, 4) if rank else 0.0,
        "first_relevant_rank": rank,
        "all_relevant_documents_hit": len(hits) == len(relevant),
    }


def normalized_text(value: str) -> str:
    return " ".join(value.lower().split())


def required_text_coverage(
    results: list[RetrievedChunk],
    required_terms: list[str],
) -> tuple[list[str], float | None]:
    if not required_terms:
        return [], None
    haystack = normalized_text(
        "\n".join(f"{result.document_title}\n{result.content}" for result in results)
    )
    hits = [term for term in required_terms if normalized_text(term) in haystack]
    return hits, round(len(hits) / len(required_terms), 4)


def filter_violations(
    results: list[RetrievedChunk],
    request: SearchRequest,
) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for result in results:
        checks = {
            "source_names": (
                request.source_names is None or result.source_name in request.source_names
            ),
            "tools": request.tools is None or result.tool in request.tools,
            "categories": (
                request.categories is None or result.category in request.categories
            ),
            "event_types": (
                request.event_types is None
                or bool(set(result.event_types).intersection(request.event_types))
            ),
            "source_types": (
                request.source_types is None
                or result.source_category in request.source_types
            ),
            "published_after": (
                request.published_after is None
                or (
                    result.published_at is not None
                    and utc_datetime(result.published_at)
                    >= utc_datetime(request.published_after)
                )
            ),
            "published_before": (
                request.published_before is None
                or (
                    result.published_at is not None
                    and utc_datetime(result.published_at)
                    <= utc_datetime(request.published_before)
                )
            ),
        }
        for field, passed in checks.items():
            if not passed:
                violations.append(
                    {
                        "document_id": result.document_id,
                        "field": field,
                    }
                )
    return violations


def utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def validate_question_set(payload: dict[str, Any], snapshot: dict[str, Any]) -> None:
    questions = list(payload.get("questions") or [])
    if not questions:
        raise ValueError("Question set must contain at least one question.")

    question_ids = [str(item.get("id") or "") for item in questions]
    if any(not question_id for question_id in question_ids):
        raise ValueError("Every question requires a non-empty id.")
    if len(question_ids) != len(set(question_ids)):
        raise ValueError("Question ids must be unique.")

    if payload.get("snapshot_corpus_hash") != snapshot.get("corpus_hash"):
        raise ValueError("Question set snapshot hash does not match the corpus snapshot.")

    snapshot_ids = {
        str(item["document_id"]) for item in snapshot.get("documents", [])
    }
    for item in questions:
        if item.get("split") not in {"calibration", "holdout"}:
            raise ValueError(f"{item['id']}: split must be calibration or holdout.")
        if item.get("expected_outcome") not in {"answerable", "insufficient_evidence"}:
            raise ValueError(f"{item['id']}: invalid expected_outcome.")
        request = SearchRequest.model_validate(
            {"query": item["question"], **dict(item.get("request") or {})}
        )
        if request.collection != "updates":
            raise ValueError(f"{item['id']}: collection must be updates.")
        relevant_ids = list(item.get("relevant_document_ids") or [])
        if item["expected_outcome"] == "answerable" and not relevant_ids:
            raise ValueError(f"{item['id']}: answerable cases require relevant documents.")
        unknown = set(relevant_ids) - snapshot_ids
        if unknown:
            raise ValueError(
                f"{item['id']}: relevant documents missing from snapshot: {sorted(unknown)}"
            )


def evaluate_question(
    retriever: RetrieverService,
    item: dict[str, Any],
    *,
    search_mode: str | None,
    retrieval_strategy: str | None,
    top_k: int | None,
) -> dict[str, Any]:
    request_payload = {
        "query": item["question"],
        **dict(item.get("request") or {}),
    }
    if search_mode:
        request_payload["search_mode"] = search_mode
    if retrieval_strategy:
        request_payload["retrieval_strategy"] = retrieval_strategy
    if top_k:
        request_payload["top_k"] = top_k
    request = SearchRequest.model_validate(request_payload)
    response = retriever.search(request)
    results = response.results
    retrieved_document_ids = [result.document_id for result in results]
    relevant_document_ids = list(item.get("relevant_document_ids") or [])
    required_sources = list(item.get("required_source_names") or [])
    retrieved_sources = [result.source_name for result in results]
    fact_hits, fact_coverage = required_text_coverage(
        results,
        list(item.get("required_text_terms") or []),
    )
    violations = filter_violations(results, request)
    metrics = retrieval_metrics(retrieved_document_ids, relevant_document_ids)
    minimum_results = int(item.get("minimum_results", 1))

    return {
        "id": item["id"],
        "question": item["question"],
        "intent": item["intent"],
        "split": item["split"],
        "expected_outcome": item["expected_outcome"],
        "request": request.model_dump(mode="json"),
        "relevant_document_ids": relevant_document_ids,
        "required_source_names": required_sources,
        "required_text_terms": list(item.get("required_text_terms") or []),
        "retrieved_document_ids": retrieved_document_ids,
        "retrieved_chunk_ids": [result.chunk_id for result in results],
        "retrieved_sources": retrieved_sources,
        "retrieved_titles": [result.document_title for result in results],
        "scores": [result.similarity for result in results],
        **metrics,
        "all_required_sources_hit": (
            all(source in retrieved_sources for source in required_sources)
            if required_sources
            else None
        ),
        "required_text_hits": fact_hits,
        "required_text_coverage": fact_coverage,
        "filter_correct": not violations,
        "filter_violations": violations,
        "minimum_results": minimum_results,
        "minimum_results_met": len(results) >= minimum_results,
        "embedding_ms": response.metrics.embedding_ms,
        "retrieval_ms": response.metrics.retrieval_ms,
        "total_ms": response.metrics.total_ms,
        "notes": item.get("notes", ""),
    }


def average(values: Iterable[float | int | None]) -> float | None:
    items = [float(value) for value in values if value is not None]
    return round(statistics.mean(items), 4) if items else None


def rate(values: Iterable[bool | None]) -> float | None:
    items = [value for value in values if value is not None]
    return round(sum(bool(value) for value in items) / len(items), 4) if items else None


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "question_count": len(rows),
        "recall_at_k": average(row["recall_at_k"] for row in rows),
        "precision_at_k": average(row["precision_at_k"] for row in rows),
        "mean_reciprocal_rank": average(row["reciprocal_rank"] for row in rows),
        "all_relevant_documents_hit_rate": rate(
            row["all_relevant_documents_hit"] for row in rows
        ),
        "all_required_sources_hit_rate": rate(
            row["all_required_sources_hit"] for row in rows
        ),
        "filter_correct_rate": rate(row["filter_correct"] for row in rows),
        "minimum_results_met_rate": rate(row["minimum_results_met"] for row in rows),
        "required_text_coverage": average(
            row["required_text_coverage"] for row in rows
        ),
        "avg_embedding_ms": average(row["embedding_ms"] for row in rows),
        "avg_retrieval_ms": average(row["retrieval_ms"] for row in rows),
        "avg_total_ms": average(row["total_ms"] for row in rows),
    }


def grouped_aggregates(
    rows: list[dict[str, Any]],
    field: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row[field])].append(row)
    return {
        key: aggregate(group)
        for key, group in sorted(grouped.items())
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate exact-document retrieval over the frozen update corpus."
    )
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--snapshot", type=Path, default=DEFAULT_SNAPSHOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--split", choices=("all", "calibration", "holdout"), default="all")
    parser.add_argument(
        "--intent",
        choices=(
            "all",
            "exact_lookup",
            "temporal",
            "comparison",
            "filter",
            "synthesis",
            "insufficient_evidence",
        ),
        default="all",
    )
    parser.add_argument("--top-k", type=int, choices=range(1, 21))
    parser.add_argument("--search-mode", choices=SEARCH_MODES)
    parser.add_argument("--retrieval-strategy", choices=RETRIEVAL_STRATEGIES)
    arguments = parser.parse_args()

    questions_payload = yaml.safe_load(
        arguments.questions.resolve().read_text(encoding="utf-8")
    )
    snapshot = json.loads(arguments.snapshot.resolve().read_text(encoding="utf-8"))
    validate_question_set(questions_payload, snapshot)
    questions = list(questions_payload["questions"])
    if arguments.split != "all":
        questions = [
            item for item in questions if item["split"] == arguments.split
        ]
    if arguments.intent != "all":
        questions = [
            item for item in questions if item["intent"] == arguments.intent
        ]

    with SessionLocal() as db:
        retriever = RetrieverService(db)
        rows = [
            evaluate_question(
                retriever,
                item,
                search_mode=arguments.search_mode,
                retrieval_strategy=arguments.retrieval_strategy,
                top_k=arguments.top_k,
            )
            for item in questions
        ]

    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "questions_file": str(arguments.questions.resolve()),
        "snapshot_file": str(arguments.snapshot.resolve()),
        "snapshot_corpus_hash": snapshot["corpus_hash"],
        "overrides": {
            "split": arguments.split,
            "intent": arguments.intent,
            "top_k": arguments.top_k,
            "search_mode": arguments.search_mode,
            "retrieval_strategy": arguments.retrieval_strategy,
        },
        "summary": aggregate(rows),
        "by_intent": grouped_aggregates(rows, "intent"),
        "by_split": grouped_aggregates(rows, "split"),
        "questions": rows,
    }
    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    print(json.dumps(payload["summary"], indent=2))
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
