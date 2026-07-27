import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.schemas.search import SearchRequest
from app.services.retriever import RetrieverService


EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "eval"
QUESTIONS_FILE = EVAL_DIR / "questions.yml"
RESULTS_FILE = EVAL_DIR / "results.jsonl"
SUMMARY_FILE = EVAL_DIR / "summary.json"


def main() -> None:
    questions = load_questions()
    EVAL_DIR.mkdir(parents=True, exist_ok=True)

    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        retriever = RetrieverService(db)
        for item in questions:
            row = evaluate_question(retriever, item)
            rows.append(row)
            print_question_result(row)

    write_jsonl(RESULTS_FILE, rows)
    summary = summarize(rows)
    SUMMARY_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print_summary(summary)
    print(f"\nWrote {RESULTS_FILE}")
    print(f"Wrote {SUMMARY_FILE}")


def load_questions() -> list[dict[str, Any]]:
    with QUESTIONS_FILE.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data["questions"]


def evaluate_question(retriever: RetrieverService, item: dict[str, Any]) -> dict[str, Any]:
    request = search_request(item)
    top_k = request.top_k
    response = retriever.search(request)
    expected_sources = item["expected_sources"]
    expected_title_terms = item.get("expected_title_terms", [])
    expected_keywords = item.get("expected_keywords", [])
    retrieved_sources = [result.source_name for result in response.results]
    retrieved_titles = [result.document_title for result in response.results]
    retrieved_text = "\n".join(
        f"{result.document_title}\n{result.content}"
        for result in response.results
    ).lower()
    similarities = [result.similarity for result in response.results]

    source_ranks = {
        source: first_rank(retrieved_sources, source)
        for source in expected_sources
    }
    hit_sources = [source for source, rank in source_ranks.items() if rank is not None]
    title_term_hits = terms_found(expected_title_terms, "\n".join(retrieved_titles))
    keyword_hits = terms_found(expected_keywords, retrieved_text)

    return {
        "id": item["id"],
        "question": item["question"],
        "difficulty": item.get("difficulty", "unknown"),
        "expected_sources": expected_sources,
        "expected_title_terms": expected_title_terms,
        "expected_keywords": expected_keywords,
        "retrieved_sources": retrieved_sources,
        "retrieved_titles": retrieved_titles,
        "similarities": similarities,
        "source_ranks": source_ranks,
        "title_term_hits": title_term_hits,
        "title_hint_hit": len(title_term_hits) > 0 if expected_title_terms else None,
        "keyword_hits": keyword_hits,
        "keyword_coverage": coverage(keyword_hits, expected_keywords),
        "source_hit": bool(hit_sources),
        "all_expected_sources_hit": len(hit_sources) == len(expected_sources),
        "top_3_source_hit": any(source in retrieved_sources[:3] for source in expected_sources),
        "top_score": similarities[0] if similarities else 0,
        "avg_score": round(statistics.mean(similarities), 4) if similarities else 0,
        "embedding_ms": response.metrics.embedding_ms,
        "retrieval_ms": response.metrics.retrieval_ms,
        "total_ms": response.metrics.total_ms,
        "top_k": top_k,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "notes": item.get("notes", ""),
    }


def search_request(item: dict[str, Any]) -> SearchRequest:
    return SearchRequest(
        query=item["question"],
        top_k=int(item.get("top_k", 6)),
        collection=item.get("collection", "docs"),
    )


def first_rank(values: list[str], expected: str) -> int | None:
    for index, value in enumerate(values, start=1):
        if value == expected:
            return index
    return None


def terms_found(expected_terms: list[str], text: str) -> list[str]:
    normalized = text.lower()
    return [term for term in expected_terms if term.lower() in normalized]


def coverage(found_terms: list[str], expected_terms: list[str]) -> float | None:
    if not expected_terms:
        return None
    return round(len(found_terms) / len(expected_terms), 4)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as file:
        for row in rows:
            file.write(json.dumps(row, ensure_ascii=False) + "\n")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_difficulty: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_difficulty.setdefault(row["difficulty"], []).append(row)

    return {
        "question_count": len(rows),
        "source_hit_rate": rate(row["source_hit"] for row in rows),
        "all_expected_sources_hit_rate": rate(row["all_expected_sources_hit"] for row in rows),
        "top_3_source_hit_rate": rate(row["top_3_source_hit"] for row in rows),
        "title_hint_hit_rate": nullable_rate(row["title_hint_hit"] for row in rows),
        "avg_keyword_coverage": nullable_avg(row["keyword_coverage"] for row in rows),
        "avg_top_score": avg(row["top_score"] for row in rows),
        "avg_embedding_ms": avg(row["embedding_ms"] for row in rows),
        "avg_retrieval_ms": avg(row["retrieval_ms"] for row in rows),
        "avg_total_ms": avg(row["total_ms"] for row in rows),
        "by_difficulty": {
            difficulty: {
                "question_count": len(group),
                "source_hit_rate": rate(row["source_hit"] for row in group),
                "all_expected_sources_hit_rate": rate(
                    row["all_expected_sources_hit"] for row in group
                ),
                "title_hint_hit_rate": nullable_rate(row["title_hint_hit"] for row in group),
                "avg_keyword_coverage": nullable_avg(row["keyword_coverage"] for row in group),
                "avg_top_score": avg(row["top_score"] for row in group),
            }
            for difficulty, group in sorted(by_difficulty.items())
        },
    }


def rate(values) -> float:
    items = list(values)
    if not items:
        return 0
    return round(sum(1 for item in items if item) / len(items), 4)


def avg(values) -> float:
    items = list(values)
    if not items:
        return 0
    return round(statistics.mean(items), 4)


def nullable_rate(values) -> float | None:
    items = [item for item in values if item is not None]
    if not items:
        return None
    return round(sum(1 for item in items if item) / len(items), 4)


def nullable_avg(values) -> float | None:
    items = [item for item in values if item is not None]
    if not items:
        return None
    return round(statistics.mean(items), 4)


def print_question_result(row: dict[str, Any]) -> None:
    status = "PASS" if row["all_expected_sources_hit"] else "PARTIAL" if row["source_hit"] else "FAIL"
    print(f"\n[{status}] {row['id']}")
    print(f"Q: {row['question']}")
    print(f"Expected: {', '.join(row['expected_sources'])}")
    print(f"Retrieved: {', '.join(row['retrieved_sources'])}")
    print(f"Ranks: {row['source_ranks']}")
    if row["expected_title_terms"]:
        print(f"Title terms hit: {row['title_term_hits']}")
    if row["expected_keywords"]:
        print(f"Keyword coverage: {row['keyword_coverage']:.0%} {row['keyword_hits']}")
    print(f"Top score: {row['top_score']} | Total: {row['total_ms']}ms")


def print_summary(summary: dict[str, Any]) -> None:
    print("\nSummary")
    print(f"Questions: {summary['question_count']}")
    print(f"Source hit rate: {summary['source_hit_rate']:.0%}")
    print(f"All expected sources hit rate: {summary['all_expected_sources_hit_rate']:.0%}")
    print(f"Top-3 source hit rate: {summary['top_3_source_hit_rate']:.0%}")
    if summary["title_hint_hit_rate"] is not None:
        print(f"Title hint hit rate: {summary['title_hint_hit_rate']:.0%}")
    if summary["avg_keyword_coverage"] is not None:
        print(f"Avg keyword coverage: {summary['avg_keyword_coverage']:.0%}")
    print(f"Avg top score: {summary['avg_top_score']}")
    print(f"Avg embedding latency: {summary['avg_embedding_ms']}ms")
    print(f"Avg retrieval latency: {summary['avg_retrieval_ms']}ms")
    print(f"Avg total latency: {summary['avg_total_ms']}ms")


if __name__ == "__main__":
    main()
