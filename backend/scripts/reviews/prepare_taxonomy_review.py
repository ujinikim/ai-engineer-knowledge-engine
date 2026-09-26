import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts._source_config import update_source_map

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.taxonomy import EVENT_TYPES, PRIMARY_TOPICS
from app.services.update_visibility import source_attribute


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_review_sample.json"
)
REVIEW_VALUES = ("not_reviewed", "correct", "change_required", "uncertain")


def source_configs() -> dict[str, dict]:
    return update_source_map()


def load_documents() -> list[Document]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Document)
                .order_by(
                    Document.source_name,
                    Document.published_at.desc().nullslast(),
                    Document.id,
                )
            )
        )


def review_key(document: Document, taxonomy: dict) -> str:
    payload = json.dumps(
        {
            "content_hash": document.content_hash,
            "taxonomy": taxonomy,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def existing_payload(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def existing_reviews(payload: dict) -> dict[str, dict]:
    return {
        str(item["review_key"]): item
        for item in payload.get("items", [])
        if item.get("review_key")
    }


def preserved_value(prior: dict, field: str) -> str:
    value = str(prior.get(field) or "not_reviewed")
    return value if value in REVIEW_VALUES else "not_reviewed"


def review_focus(document: Document, config: dict, taxonomy: dict) -> list[str]:
    reasons: list[str] = []
    event_types = set(taxonomy["event_types"])
    default_events = set(config.get("default_event_types", []))
    if taxonomy["primary_topic"] != config.get("default_primary_topic"):
        reasons.append("primary_topic_overrides_source_default")
    if default_events and event_types != default_events:
        reasons.append("event_types_differ_from_source_default")
    if len(event_types) > 1:
        reasons.append("multiple_event_types")
    return reasons


def select_sample(items: list[dict], sample_size: int) -> list[dict]:
    if sample_size <= 0:
        return []

    selected: list[dict] = []
    seen: set[str] = set()

    def append(item: dict) -> None:
        if item["document_id"] not in seen and len(selected) < sample_size:
            selected.append(item)
            seen.add(item["document_id"])

    for source_name in sorted({item["source_name"] for item in items}):
        candidate = next(item for item in items if item["source_name"] == source_name)
        append(candidate)

    for topic in PRIMARY_TOPICS:
        candidate = next(
            (
                item
                for item in items
                if item["generated_taxonomy"]["primary_topic"] == topic
            ),
            None,
        )
        if candidate:
            append(candidate)

    for event_type in EVENT_TYPES:
        candidate = next(
            (
                item
                for item in items
                if event_type in item["generated_taxonomy"]["event_types"]
            ),
            None,
        )
        if candidate:
            append(candidate)

    for item in items:
        append(item)

    return selected


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a stratified human taxonomy-review artifact."
    )
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--change-note",
        default="Prepared after a fresh all-source collection for taxonomy policy review.",
    )
    arguments = parser.parse_args()

    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    prior_payload = existing_payload(output)
    prior_reviews = existing_reviews(prior_payload)
    configs = source_configs()
    documents = load_documents()

    topics: Counter[str] = Counter()
    events: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    all_items: list[dict] = []

    for document in documents:
        taxonomy = {
            "primary_topic": str(document.primary_topic or ""),
            "event_types": list(document.event_types or []),
        }
        config = configs[document.source_name]
        focus = review_focus(document, config, taxonomy)
        topics[taxonomy["primary_topic"]] += 1
        events.update(taxonomy["event_types"])
        focus_counts.update(focus)
        key = review_key(document, taxonomy)
        prior = prior_reviews.get(key, {})
        all_items.append(
            {
                "document_id": str(document.id),
                "review_key": key,
                "source_name": document.source_name,
                "source_type": str(source_attribute(document.source_name, "source_type") or "unknown"),
                "title": document.title,
                "url": document.url,
                "published_at": document.published_at.isoformat()
                if document.published_at
                else None,
                "review_focus": focus,
                "configured_defaults": {
                    "primary_topic": config.get("default_primary_topic"),
                    "event_types": list(config.get("default_event_types", [])),
                },
                "generated_taxonomy": taxonomy,
                "generated_card": {
                    "display_headline": document.display_headline,
                    "summary": document.summary,
                    "why_it_matters": document.why_it_matters,
                    "key_points": list(document.key_points or []),
                },
                "primary_topic_review": preserved_value(
                    prior, "primary_topic_review"
                ),
                "proposed_primary_topic": prior.get("proposed_primary_topic"),
                "event_types_review": preserved_value(prior, "event_types_review"),
                "proposed_event_types": list(prior.get("proposed_event_types") or []),
                "taxonomy_notes": str(prior.get("taxonomy_notes") or ""),
            }
        )

    sampled_items = select_sample(all_items, max(0, arguments.sample_size))
    sampled_ids = {item["document_id"] for item in sampled_items}
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "purpose": "Human review of primary topic and event types.",
        "change_history": [
            *prior_payload.get("change_history", []),
            {
                "generated_at": generated_at,
                "change_note": arguments.change_note,
                "documents_evaluated": len(documents),
                "sample_size": len(sampled_items),
            },
        ],
        "review_order": [
            "Review event_types first using docs/archive/TAXONOMY_REMEDIATION_PLAN.md.",
            "Review primary_topic after event types.",
        ],
        "allowed_review_values": list(REVIEW_VALUES),
        "allowed_primary_topics": list(PRIMARY_TOPICS),
        "allowed_event_types": list(EVENT_TYPES),
        "instructions": {
            "correct": "Keep the generated value and leave the corresponding proposed field empty.",
            "change_required": "Populate the corresponding proposed field and explain why in taxonomy_notes.",
            "uncertain": "Document the competing interpretations in taxonomy_notes.",
            "not_reviewed": "The axis has not yet been reviewed.",
        },
        "collection_summary": {
            "documents": len(documents),
            "topic_counts": dict(topics.most_common()),
            "event_type_counts": dict(events.most_common()),
            "review_focus_counts": dict(focus_counts.most_common()),
        },
        "items": sampled_items,
        "all_assignments": [
            {
                "document_id": item["document_id"],
                "in_review_sample": item["document_id"] in sampled_ids,
                "source_name": item["source_name"],
                "title": item["title"],
                "url": item["url"],
                "review_focus": item["review_focus"],
                "configured_defaults": item["configured_defaults"],
                "generated_taxonomy": item["generated_taxonomy"],
            }
            for item in all_items
        ],
    }
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Taxonomy review sample: {output}")
    print(f"Documents indexed: {len(documents)}")
    print(f"Human-review items: {len(sampled_items)}")
    print(f"Focus counts: {dict(focus_counts.most_common())}")


if __name__ == "__main__":
    main()
