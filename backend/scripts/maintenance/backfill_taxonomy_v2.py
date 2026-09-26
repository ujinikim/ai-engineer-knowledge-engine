import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts._source_config import update_source_map

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.update_visibility import configured_active_source_slugs
from app.services.article_summary import ArticleSummaryService
from app.services.source_extraction import article_excerpt
from app.services.taxonomy import (
    TAXONOMY_POLICY_VERSION,
    classify_topic_with_method,
    infer_event_types,
)


def load_sources() -> dict[str, dict]:
    return update_source_map()


def classify_excerpt(
    document: Document,
    config: dict,
) -> tuple[str, list[str], str, str | None, str | None, str, str, str | None]:
    excerpt = article_excerpt(document.title, document.raw_text)
    default_topic = config.get(
        "default_primary_topic",
        "ai-products-engineering-infrastructure",
    )
    default_events = config.get("default_event_types", ["analysis"])
    topic, method = classify_topic_with_method(
        f"{document.title}\n{document.title}\n{excerpt}",
        default_topic,
    )
    events = infer_event_types(
        f"{document.title}\n{excerpt}",
        default_events,
    )
    return (
        topic,
        events or ["analysis"],
        method,
        None,
        "Official feed excerpt used deterministic taxonomy rules.",
        None,
        None,
        "Official feed excerpt used deterministic event rules.",
    )


def build_query(source: str | None):
    query = (
        select(Document)
        .where(
            Document.source_name.in_(configured_active_source_slugs()),
            Document.ingestion_status == "published",
        )
        .order_by(Document.published_at.desc(), Document.id)
    )
    if source:
        query = query.where(Document.source_name == source)
    return query


def run(
    *,
    limit: int | None,
    source: str | None,
    model: str | None,
    apply: bool,
    force: bool,
) -> dict:
    sources = load_sources()
    summarizer = ArticleSummaryService(model=model)
    records: list[dict] = []
    skipped_current = 0

    with SessionLocal() as db:
        documents = list(db.scalars(build_query(source)).all())
        for document in documents:
            if document.taxonomy_policy_version == TAXONOMY_POLICY_VERSION and not force:
                skipped_current += 1
                continue
            if limit is not None and len(records) >= limit:
                break

            config = sources.get(document.source_name, {})
            default_topic = config.get(
                "default_primary_topic",
                "ai-products-engineering-infrastructure",
            )
            default_events = config.get("default_event_types", ["analysis"])
            is_excerpt = document.extraction_status == "feed_excerpt_only"
            if is_excerpt:
                (
                    new_topic,
                    new_events,
                    method,
                    _main_theme,
                    classification_reason,
                    _relevance_tier,
                    _relevance_reason,
                    event_reason,
                ) = classify_excerpt(document, config)
            else:
                (
                    new_topic,
                    new_events,
                    method,
                    _main_theme,
                    classification_reason,
                    _relevance_tier,
                    _relevance_reason,
                    event_reason,
                ) = summarizer.classify_taxonomy(
                    title=document.title,
                    raw_text=document.raw_text,
                    default_topic=default_topic,
                    default_event_types=default_events,
                )

            before = {
                "primary_topic": document.primary_topic,
                "event_types": list(document.event_types or []),
                "taxonomy_policy_version": document.taxonomy_policy_version,
            }
            after = {
                "primary_topic": new_topic,
                "event_types": new_events[:1],
                "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
            }
            changed = before != after
            records.append(
                {
                    "document_id": str(document.id),
                    "source": document.source_name,
                    "title": document.title,
                    "url": document.url,
                    "classification_method": method,
                    "classification_reason": classification_reason,
                    "event_reason": event_reason,
                    "changed": changed,
                    "before": before,
                    "after": after,
                }
            )
            if apply and changed:
                document.primary_topic = new_topic
                document.event_types = after["event_types"]
                document.taxonomy_policy_version = TAXONOMY_POLICY_VERSION

        if apply:
            db.commit()

    categories = Counter(record["after"]["primary_topic"] for record in records)
    events = Counter(record["after"]["event_types"][0] for record in records)
    return {
        "mode": "apply" if apply else "dry-run",
        "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
        "model": summarizer.model,
        "scope": {
            "source": source,
            "enabled_sources_only": True,
            "published_updates_only": True,
        },
        "processed": len(records),
        "changed": sum(record["changed"] for record in records),
        "skipped_already_current": skipped_current,
        "category_counts": dict(sorted(categories.items())),
        "event_counts": dict(sorted(events.items())),
        "records": records,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Preview or apply taxonomy v2 to enabled, published update-feed documents. "
            "Dry-run is the default."
        )
    )
    parser.add_argument("--limit", type=int, help="Maximum documents to classify")
    parser.add_argument("--source", help="Restrict classification to one enabled source slug")
    parser.add_argument("--model", help="Override the configured classification model")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Write taxonomy metadata; otherwise only print the report",
    )
    mode.add_argument(
        "--dry-run",
        action="store_false",
        dest="apply",
        help="Print the report without writing (the default)",
    )
    parser.set_defaults(apply=False)
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reclassify records already on taxonomy v2",
    )
    arguments = parser.parse_args()
    report = run(
        limit=max(1, arguments.limit) if arguments.limit else None,
        source=arguments.source,
        model=arguments.model,
        apply=arguments.apply,
        force=arguments.force,
    )
    print(json.dumps(report, indent=2, default=str))
