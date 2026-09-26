import argparse
import json
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


def extraction_values(document: Document, metadata: dict) -> dict:
    hydration_status = str(metadata.get("hydration_status") or "not_requested")
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

    return {
        "hydration_status": hydration_status,
        "extraction_status": extraction_status,
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
                .order_by(Document.source_name, Document.id)
            )
        )
        for document in documents:
            metadata = dict(document.doc_metadata or {})
            values = extraction_values(document, metadata)
            counts[values["extraction_status"]] += 1

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
            },
            {
                "date": "2026-09-25",
                "change": (
                    "Fetch-attempt diagnostics moved to collector logs; the backfill "
                    "now derives only hydration and extraction status."
                ),
            },
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
