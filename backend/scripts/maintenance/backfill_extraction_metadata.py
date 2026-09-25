import argparse
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "extraction_metadata_backfill_report_2026-07-26.json"
)
METADATA_VERSION = "2026-07-26-v1"


def http_status_from_error(error: str) -> int | None:
    match = re.search(r"\b([45]\d{2})\b", error)
    return int(match.group(1)) if match else None


def error_code(status: int | None, error: str) -> str | None:
    if status == 403:
        return "http_forbidden"
    if status == 404:
        return "http_not_found"
    if status is not None and status >= 400:
        return "http_error"
    if "Full article extraction produced only" in error:
        return "content_incomplete"
    if error:
        return "unknown_error"
    return None


def extraction_values(document: Document, metadata: dict) -> dict:
    hydration_status = str(metadata.get("hydration_status") or "not_requested")
    hydration_error = str(metadata.get("hydration_error") or "").strip()
    body = str(document.raw_text or "").removeprefix(str(document.title or "")).strip()
    existing_status = str(metadata.get("extraction_status") or "").strip()

    if existing_status:
        extraction_status = existing_status
    elif hydration_status == "full_article":
        extraction_status = "full_article"
    elif hydration_status == "failed":
        extraction_status = "feed_excerpt_only" if body else "title_only"
    else:
        extraction_status = "source_entry"

    summary_input_source = str(metadata.get("summary_input_source") or "").strip()
    if not summary_input_source:
        summary_input_source = {
            "full_article": "full_article",
            "feed_excerpt_only": "feed_excerpt",
            "title_only": "title",
        }.get(extraction_status, "source_entry")

    attempted = metadata.get("full_article_fetch_attempted_at")
    if attempted is None and hydration_status in {
        "full_article",
        "failed",
    }:
        attempted = document.fetched_at.isoformat() if document.fetched_at else None

    status = metadata.get("full_article_fetch_http_status")
    if status is None:
        if hydration_status == "full_article":
            status = 200
        elif hydration_error:
            status = http_status_from_error(hydration_error)

    fetch_error_code = metadata.get("full_article_fetch_error_code")
    if fetch_error_code is None:
        fetch_error_code = error_code(status, hydration_error)

    return {
        "hydration_status": hydration_status,
        "hydration_error": hydration_error or None,
        "extraction_status": extraction_status,
        "summary_input_source": summary_input_source,
        "full_article_fetch_attempted_at": attempted,
        "full_article_fetch_http_status": status,
        "full_article_fetch_error_code": fetch_error_code,
        "extraction_metadata_version": METADATA_VERSION,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill structured full-article extraction metadata."
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    arguments = parser.parse_args()

    counts: Counter[str] = Counter()
    changes: list[dict] = []
    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(Document)
                .where(Document.source_type == "release")
                .order_by(Document.source_name, Document.id)
            )
        )
        for document in documents:
            metadata = dict(document.doc_metadata or {})
            values = extraction_values(document, metadata)
            counts[values["extraction_status"]] += 1
            if values["full_article_fetch_error_code"]:
                counts[f"error:{values['full_article_fetch_error_code']}"] += 1

            before = {
                field: metadata.get(field)
                for field in values
            }
            updated_metadata = {**metadata, **values}
            if updated_metadata != metadata:
                document.doc_metadata = updated_metadata
                changes.append(
                    {
                        "document_id": str(document.id),
                        "source_name": document.source_name,
                        "title": document.title,
                        "summary_generated_by": metadata.get(
                            "summary_generated_by"
                        ),
                        "before": before,
                        "after": values,
                    }
                )

        if arguments.dry_run:
            db.rollback()
        else:
            db.commit()

    report = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "mode": "dry-run" if arguments.dry_run else "committed",
        "metadata_version": METADATA_VERSION,
        "documents_inspected": len(documents),
        "documents_changed": len(changes),
        "counts": dict(counts),
        "changes": changes,
        "change_history": [
            {
                "date": "2026-07-26",
                "change": (
                    "Separated source extraction completeness, summary input, "
                    "full-article fetch diagnostics, and summary-generation provenance."
                ),
                "note": (
                    "Historical fetch-attempt timestamps use the stored fetched_at "
                    "time because the exact prior request time was not retained."
                ),
            }
        ],
    }
    output = arguments.report.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    mode = "Dry run" if arguments.dry_run else "Committed"
    print(f"{mode}: {len(documents)} release documents inspected")
    print(f"Documents changed: {len(changes)}")
    print(f"Counts: {dict(counts)}")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
