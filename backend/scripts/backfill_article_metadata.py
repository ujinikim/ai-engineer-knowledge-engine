import argparse
import json
import sys
from pathlib import Path

import yaml
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.article_summary import ArticleSummaryService


SOURCE_FILE = Path(__file__).resolve().parents[1] / "data" / "update_sources.yml"


def load_sources() -> dict[str, dict]:
    with SOURCE_FILE.open("r", encoding="utf-8") as file:
        sources = yaml.safe_load(file)["sources"]
    return {source["slug"]: source for source in sources}


def main(limit: int | None, force: bool) -> None:
    sources = load_sources()
    summarizer = ArticleSummaryService()
    updated = 0
    skipped = 0

    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(Document)
                .where(Document.source_type == "release")
                .order_by(Document.published_at.desc())
            ).all()
        )
        for document in documents:
            if limit is not None and updated >= limit:
                break
            if document.doc_metadata.get("summary") and not force:
                skipped += 1
                continue

            config = sources.get(document.source_name, {})
            metadata = dict(document.doc_metadata)
            default_topic = config.get(
                "default_primary_topic",
                metadata.get("primary_topic")
                or metadata.get("category")
                or "ai-products-engineering-infrastructure",
            )
            source_type = config.get(
                "source_type",
                metadata.get("source_type") or "official-release",
            )
            article = summarizer.summarize(
                title=document.title,
                raw_text=document.raw_text,
                organization=str(metadata.get("organization") or config.get("organization") or "Unknown"),
                tool=str(metadata.get("tool") or config.get("tool") or "Unknown"),
                source_type=source_type,
                default_topic=default_topic,
                default_event_types=config.get("default_event_types", ["analysis"]),
            )
            document.doc_metadata = {
                **metadata,
                "category": article.primary_topic,
                "source_type": source_type,
                **article.metadata(),
            }
            db.commit()
            updated += 1
            print(f"[{updated}] {document.source_name}: {document.title[:80]}")

    print(json.dumps({"updated": updated, "skipped": skipped}, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate article summaries and taxonomy metadata.")
    parser.add_argument("--limit", type=int, help="Maximum documents to update")
    parser.add_argument("--force", action="store_true", help="Regenerate existing summaries")
    arguments = parser.parse_args()
    main(max(1, arguments.limit) if arguments.limit else None, arguments.force)
