import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.model_usage import ModelUsage, estimate_chat_cost_usd
from app.db.session import SessionLocal
from app.services.article_relevance import (
    RELEVANCE_POLICY_VERSION,
    ArticleRelevanceService,
)
from app.services.ingestion_policy import PUBLISHED, stored_ingestion_status


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "article_relevance_evaluation_2026-09-13.json"
)


def build_query(*, source: str | None, document_id: str | None, limit: int | None):
    clauses = ["d.source_type = 'release'", "s.enabled = true"]
    parameters: dict[str, object] = {}
    if source:
        clauses.append("d.source_name = :source")
        parameters["source"] = source
    if document_id:
        clauses.append("d.id = CAST(:document_id AS uuid)")
        parameters["document_id"] = document_id
    limit_sql = ""
    if limit is not None:
        limit_sql = " LIMIT :limit"
        parameters["limit"] = limit
    statement = text(
        """
        SELECT
          d.id::text AS document_id,
          d.source_name,
          d.title,
          d.url,
          d.canonical_url,
          d.raw_text,
          d.content_hash,
          d.published_at,
          d.doc_metadata
        FROM documents AS d
        JOIN update_sources AS s ON s.slug = d.source_name
        WHERE """
        + " AND ".join(clauses)
        + " ORDER BY d.published_at DESC NULLS LAST, d.id"
        + limit_sql
    )
    return statement, parameters


def evidence_level(metadata: dict) -> str:
    explicit = str(metadata.get("evidence_level") or "").strip()
    if explicit:
        return explicit
    if metadata.get("extraction_status") == "full_article":
        return "full_article"
    return "source_entry"


def summarize(records: list[dict]) -> dict:
    tiers = Counter(record["relevance_tier"] for record in records)
    statuses = Counter(record["classification_status"] for record in records)
    default_rag = sum(record["default_rag_eligible"] for record in records)
    contextual_rag = sum(record["contextual_rag_eligible"] for record in records)
    by_source: dict[str, Counter] = defaultdict(Counter)
    for record in records:
        source_counts = by_source[record["source"]]
        source_counts[record["relevance_tier"]] += 1
        source_counts["evaluated"] += 1
        source_counts["default_rag_eligible"] += int(record["default_rag_eligible"])
        source_counts["contextual_rag_eligible"] += int(
            record["contextual_rag_eligible"]
        )
        source_counts["evidence_blocked"] += int(record["evidence_blocked"])
    return {
        "evaluated": len(records),
        "tier_counts": dict(sorted(tiers.items())),
        "classification_status_counts": dict(sorted(statuses.items())),
        "default_rag_eligible": default_rag,
        "rag_eligible_with_contextual": default_rag + contextual_rag,
        "contextual_rag_eligible": contextual_rag,
        "evidence_blocked": sum(record["evidence_blocked"] for record in records),
        "by_source": {
            source: dict(sorted(counts.items()))
            for source, counts in sorted(by_source.items())
        },
    }


def write_report(path: Path, *, records: list[dict], service, usage: ModelUsage) -> dict:
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "read-only-evaluation",
        "model": service.model,
        "relevance_policy_version": RELEVANCE_POLICY_VERSION,
        "summary": summarize(records),
        "usage": {
            "input_tokens": usage.chat_input_tokens,
            "output_tokens": usage.chat_output_tokens,
            "estimated_cost_usd": estimate_chat_cost_usd(
                service.model,
                usage.chat_input_tokens,
                usage.chat_output_tokens,
            ),
        },
        "records": records,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return report


def run(
    *,
    output: Path,
    source: str | None,
    document_id: str | None,
    limit: int | None,
    model: str | None,
) -> dict:
    usage = ModelUsage()
    service = ArticleRelevanceService(usage=usage, model=model)
    records: list[dict] = []
    statement, parameters = build_query(
        source=source,
        document_id=document_id,
        limit=limit,
    )

    with SessionLocal() as db:
        rows = list(db.execute(statement, parameters).mappings())

    for index, row in enumerate(rows, start=1):
        metadata = dict(row["doc_metadata"] or {})
        if stored_ingestion_status(metadata) != PUBLISHED:
            continue
        decision = service.classify(title=row["title"], raw_text=row["raw_text"])
        level = evidence_level(metadata)
        evidence_blocked = level == "official_feed_excerpt"
        records.append(
            {
                "document_id": row["document_id"],
                "source": row["source_name"],
                "title": row["title"],
                "url": row["canonical_url"] or row["url"],
                "content_hash": row["content_hash"],
                "published_at": row["published_at"],
                "evidence_level": level,
                "evidence_blocked": evidence_blocked,
                "relevance_tier": decision.tier,
                "relevance_reason": decision.reason,
                "classification_status": decision.status,
                "generated_by": decision.generated_by,
                "agent_focus": decision.agent_focus,
                "agent_evidence_quote": decision.agent_evidence_quote,
                "default_rag_eligible": decision.tier == "core" and not evidence_blocked,
                "contextual_rag_eligible": (
                    decision.tier == "contextual" and not evidence_blocked
                ),
            }
        )
        write_report(output, records=records, service=service, usage=usage)
        print(
            f"classified {index}/{len(rows)}: {row['source_name']} -> {decision.tier}",
            file=sys.stderr,
            flush=True,
        )

    return write_report(output, records=records, service=service, usage=usage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Evaluate relevance for enabled-source articles without updating the database."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", help="Restrict the evaluation to one source slug")
    parser.add_argument("--document-id", help="Restrict the evaluation to one document UUID")
    parser.add_argument("--limit", type=int, help="Maximum candidate rows to load")
    parser.add_argument("--model", help="Override the configured relevance model")
    arguments = parser.parse_args()
    result = run(
        output=arguments.output,
        source=arguments.source,
        document_id=arguments.document_id,
        limit=max(1, arguments.limit) if arguments.limit else None,
        model=arguments.model,
    )
    print(json.dumps({key: value for key, value in result.items() if key != "records"}, indent=2))
