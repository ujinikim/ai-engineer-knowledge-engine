import argparse
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.source_detail import classify_content_detail, sparse_visibility_metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backfill source-detail and default-feed visibility metadata."
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
                .where(Document.source_type == "release")
                .order_by(Document.source_name, Document.id)
            )
        )
        for document in documents:
            metadata = dict(document.doc_metadata or {})
            content_detail = classify_content_detail(
                str(document.title or ""),
                str(document.raw_text or ""),
            )
            visibility = sparse_visibility_metadata(
                content_detail,
                list(metadata.get("event_types") or []),
            )
            counts[content_detail] += 1
            if visibility["default_feed_eligible"]:
                counts["default_feed_eligible"] += 1
            else:
                counts["default_feed_suppressed"] += 1

            updated_metadata = {**metadata, **visibility}
            if updated_metadata != metadata:
                document.doc_metadata = updated_metadata
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
    print(f"Default-feed eligible: {counts['default_feed_eligible']}")
    print(f"Default-feed suppressed: {counts['default_feed_suppressed']}")


if __name__ == "__main__":
    main()
