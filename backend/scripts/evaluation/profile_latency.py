import json
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.session import SessionLocal
from app.schemas.ask import AskRequest
from app.services.answer import AnswerService


OUTPUT_FILE = Path(__file__).resolve().parents[2] / "data" / "eval" / "latency_profile.json"


CASES = [
    AskRequest(
        question="How does LangGraph memory work?",
        top_k=3,
        max_completion_tokens=250,
    ),
    AskRequest(
        question="How does LangGraph memory work?",
        top_k=6,
        max_completion_tokens=300,
    ),
    AskRequest(
        question="Compare LangGraph persistence and OpenAI conversation state.",
        top_k=6,
        search_mode="hybrid",
        retrieval_strategy="standard",
        max_completion_tokens=300,
    ),
    AskRequest(
        question="Compare memory, persistence, and conversation state across LangGraph and OpenAI.",
        top_k=8,
        search_mode="hybrid",
        retrieval_strategy="source_balanced",
        max_completion_tokens=300,
    ),
    AskRequest(
        question="Show all documents mentioning streaming responses.",
        top_k=6,
        search_mode="keyword",
        max_completion_tokens=250,
    ),
]


def main() -> None:
    rows: list[dict[str, Any]] = []
    with SessionLocal() as db:
        service = AnswerService(db)
        for case in CASES:
            print(f"\nProfiling: {case.question}")
            response = service.answer(case)
            row = {
                "question": case.question,
                "top_k": case.top_k,
                "search_mode": case.search_mode,
                "retrieval_strategy": case.retrieval_strategy,
                "max_completion_tokens": case.max_completion_tokens,
                "max_context_tokens": case.max_context_tokens,
                "retrieved_chunks": len(response.retrieved_chunks),
                "embedding_ms": response.metrics.embedding_ms,
                "retrieval_ms": response.metrics.retrieval_ms,
                "llm_ms": response.metrics.llm_ms,
                "total_ms": response.metrics.total_ms,
                "context_tokens": response.metrics.context_tokens,
                "completion_tokens": response.metrics.completion_tokens,
                "estimated_cost_usd": response.metrics.estimated_cost_usd,
                "retrieval_warning": response.retrieval_warning,
                "evaluated_at": datetime.now(timezone.utc).isoformat(),
            }
            rows.append(row)
            print(
                "total={total_ms}ms llm={llm_ms}ms embed={embedding_ms}ms "
                "retrieval={retrieval_ms}ms context={context_tokens} completion={completion_tokens}"
                .format(**row)
            )

    summary = summarize(rows)
    OUTPUT_FILE.write_text(
        json.dumps({"summary": summary, "cases": rows}, indent=2),
        encoding="utf-8",
    )
    print("\nSummary")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print(f"\nWrote {OUTPUT_FILE}")


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "case_count": len(rows),
        "avg_total_ms": avg(row["total_ms"] for row in rows),
        "avg_llm_ms": avg(row["llm_ms"] for row in rows),
        "avg_embedding_ms": avg(row["embedding_ms"] for row in rows),
        "avg_retrieval_ms": avg(row["retrieval_ms"] for row in rows),
        "avg_context_tokens": avg(row["context_tokens"] for row in rows),
        "avg_completion_tokens": avg(row["completion_tokens"] for row in rows),
        "max_total_ms": max(row["total_ms"] for row in rows),
        "max_llm_ms": max(row["llm_ms"] for row in rows),
    }


def avg(values) -> float:
    items = list(values)
    if not items:
        return 0
    return round(statistics.mean(items), 2)


if __name__ == "__main__":
    main()
