import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Document
from app.db.session import SessionLocal
from app.services.taxonomy import EVENT_TYPES, MATURITY_LEVELS, PRIMARY_TOPICS


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_review_sample.json"
)
SOURCE_CONFIG_PATH = Path(__file__).resolve().parents[1] / "data" / "update_sources.yml"
VERSIONED_LIBRARY_SOURCES = {
    "langgraph",
    "litellm",
    "qdrant",
    "transformers",
    "vllm",
}
RC_VERSION_PATTERN = re.compile(
    r"\bv?\d+(?:\.\d+)+(?:[-_.]?rc(?:[.-]?\d+)?)\b",
    re.IGNORECASE,
)
REVIEW_VALUES = ("not_reviewed", "correct", "change_required", "uncertain")


def source_configs() -> dict[str, dict]:
    payload = yaml.safe_load(SOURCE_CONFIG_PATH.read_text(encoding="utf-8"))
    return {item["slug"]: item for item in payload["sources"]}


def load_documents() -> list[Document]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Document)
                .where(Document.source_type == "release")
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
    title = str(document.title or "")

    if RC_VERSION_PATTERN.search(title) and taxonomy["maturity"] != "release-candidate":
        reasons.append("release_candidate_mismatch")
    if (
        document.source_name in VERSIONED_LIBRARY_SOURCES
        and "library-release" not in event_types
    ):
        reasons.append("versioned_library_missing_library_release")
    if (
        document.source_name in VERSIONED_LIBRARY_SOURCES
        and "model-launch" in event_types
    ):
        reasons.append("versioned_library_marked_model_launch")
    if taxonomy["primary_topic"] != config.get("default_primary_topic"):
        reasons.append("primary_topic_overrides_source_default")
    if default_events and event_types != default_events:
        reasons.append("event_types_differ_from_source_default")
    if taxonomy["maturity"] != "stable":
        reasons.append("non_stable_maturity")
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

    priority_limits = {
        "release_candidate_mismatch": 6,
        "versioned_library_marked_model_launch": 3,
        "versioned_library_missing_library_release": 4,
    }
    for reason, limit in priority_limits.items():
        added = 0
        for item in items:
            if reason in item["review_focus"] and added < limit:
                before = len(selected)
                append(item)
                if len(selected) > before:
                    added += 1

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

    for maturity in MATURITY_LEVELS:
        candidate = next(
            (
                item
                for item in items
                if item["generated_taxonomy"]["maturity"] == maturity
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
    maturities: Counter[str] = Counter()
    focus_counts: Counter[str] = Counter()
    all_items: list[dict] = []

    for document in documents:
        metadata = dict(document.doc_metadata or {})
        taxonomy = {
            "primary_topic": str(metadata.get("primary_topic") or ""),
            "topic_tags": list(metadata.get("topic_tags") or []),
            "event_types": list(metadata.get("event_types") or []),
            "entity_tags": list(metadata.get("entity_tags") or []),
            "maturity": str(metadata.get("maturity") or ""),
        }
        config = configs[document.source_name]
        focus = review_focus(document, config, taxonomy)
        topics[taxonomy["primary_topic"]] += 1
        events.update(taxonomy["event_types"])
        maturities[taxonomy["maturity"]] += 1
        focus_counts.update(focus)
        key = review_key(document, taxonomy)
        prior = prior_reviews.get(key, {})
        all_items.append(
            {
                "document_id": str(document.id),
                "review_key": key,
                "source_name": document.source_name,
                "source_type": str(metadata.get("source_type") or "unknown"),
                "title": document.title,
                "url": document.canonical_url or document.url,
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
                    "display_headline": metadata.get("display_headline"),
                    "summary": metadata.get("summary"),
                    "why_it_matters": metadata.get("why_it_matters"),
                    "key_points": list(metadata.get("key_points") or []),
                },
                "source_text": document.raw_text,
                "primary_topic_review": preserved_value(
                    prior, "primary_topic_review"
                ),
                "proposed_primary_topic": prior.get("proposed_primary_topic"),
                "event_types_review": preserved_value(prior, "event_types_review"),
                "proposed_event_types": list(prior.get("proposed_event_types") or []),
                "maturity_review": preserved_value(prior, "maturity_review"),
                "proposed_maturity": prior.get("proposed_maturity"),
                "taxonomy_notes": str(prior.get("taxonomy_notes") or ""),
            }
        )

    sampled_items = select_sample(all_items, max(0, arguments.sample_size))
    sampled_ids = {item["document_id"] for item in sampled_items}
    generated_at = datetime.now(timezone.utc).isoformat()
    payload = {
        "schema_version": 1,
        "generated_at": generated_at,
        "purpose": (
            "Human review of primary topic, event types, and maturity as separate axes."
        ),
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
            "Review event_types first using TAXONOMY_REMEDIATION_PLAN.md.",
            "Review maturity second as artifact lifecycle.",
            "Review primary_topic last after event and maturity decisions stabilize.",
        ],
        "allowed_review_values": list(REVIEW_VALUES),
        "allowed_primary_topics": list(PRIMARY_TOPICS),
        "allowed_event_types": list(EVENT_TYPES),
        "allowed_maturity_levels": list(MATURITY_LEVELS),
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
            "maturity_counts": dict(maturities.most_common()),
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
