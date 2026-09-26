import argparse
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.source_detail import classify_content_detail


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Report source detail calculated from stored article text."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report changes without committing them.",
    )
    arguments = parser.parse_args()

    counts: Counter[str] = Counter()
    changed = 0
    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(Document)
                .order_by(Document.source_name, Document.id)
            )
        )
        for document in documents:
            metadata = dict(document.doc_metadata or {})
            content_detail = classify_content_detail(
                str(document.title or ""),
                str(document.raw_text or ""),
            )
            counts[content_detail] += 1
            if "content_detail" in metadata:
                document.doc_metadata = {key: value for key, value in metadata.items() if key != "content_detail"}
                changed += 1

        if arguments.dry_run:
            db.rollback()
        else:
            db.commit()

    mode = "Dry run" if arguments.dry_run else "Committed"
    print(f"{mode}: {len(documents)} release documents inspected")
    print(f"Metadata changed: {changed}")
    print(f"Detailed: {counts['detailed']}")
    print(f"Sparse: {counts['sparse']}")


if __name__ == "__main__":
    main()
