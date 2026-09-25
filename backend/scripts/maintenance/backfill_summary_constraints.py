import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.article_summary import shorten_at_word_boundary


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPORT = (
    ROOT
    / "data"
    / "eval"
    / "summaries"
    / "summary_constraints_backfill_2026-07-27.json"
)
HEADLINE_LIMIT = 90


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply deterministic display constraints to stored update summaries."
    )
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the change report without committing database updates.",
    )
    arguments = parser.parse_args()

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
            before = str(metadata.get("display_headline") or "")
            after = shorten_at_word_boundary(before, HEADLINE_LIMIT)
            if before == after:
                continue
            document.doc_metadata = {**metadata, "display_headline": after}
            changes.append(
                {
                    "document_id": str(document.id),
                    "source_name": document.source_name,
                    "title": document.title,
                    "before": before,
                    "after": after,
                    "before_characters": len(before),
                    "after_characters": len(after),
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
        "documents_inspected": len(documents),
        "headline_limit": HEADLINE_LIMIT,
        "documents_changed": len(changes),
        "changes": changes,
    }
    output = arguments.report.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    mode = "Dry run" if arguments.dry_run else "Committed"
    print(f"{mode}: {len(documents)} release documents inspected")
    print(f"Headlines shortened: {len(changes)}")
    print(f"Report: {output}")


if __name__ == "__main__":
    main()
