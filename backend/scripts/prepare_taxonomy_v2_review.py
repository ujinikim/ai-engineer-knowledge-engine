import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Document, UpdateSource
from app.db.session import SessionLocal
from app.services.article_summary import ArticleSummaryService
from app.services.taxonomy import EVENT_TYPES, PRIMARY_TOPICS, TAXONOMY_POLICY_VERSION
from scripts.backfill_taxonomy_v2 import classify_excerpt, load_sources


DEFAULT_OUTPUT = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "eval"
    / "summaries"
    / "taxonomy_v2_review_sample_2026-09-13.json"
)
RELEVANCE_TIERS = ("core", "contextual", "excluded")
REVIEW_VALUES = ("not_reviewed", "correct", "change_required", "uncertain")
MODEL_TEXT_LIMIT = 12_000
SOURCE_PREVIEW_LIMIT = 800


def load_documents() -> list[Document]:
    with SessionLocal() as db:
        return list(
            db.scalars(
                select(Document)
                .join(UpdateSource, UpdateSource.slug == Document.source_name)
                .where(
                    Document.source_type == "release",
                    UpdateSource.enabled.is_(True),
                    Document.doc_metadata["ingestion_status"].astext == "published",
                )
                .order_by(
                    Document.source_name,
                    Document.published_at.desc().nullslast(),
                    Document.id,
                )
            ).all()
        )


def select_source_balanced(
    documents: list[Document],
    sample_size: int,
    required_document_ids: tuple[str, ...] = (),
) -> list[Document]:
    """Round-robin recent documents so every enabled source is represented."""
    by_id = {str(document.id): document for document in documents}
    missing = [document_id for document_id in required_document_ids if document_id not in by_id]
    if missing:
        raise ValueError(f"Required document IDs are unavailable: {', '.join(missing)}")

    selected = [by_id[document_id] for document_id in dict.fromkeys(required_document_ids)]
    selected_ids = {str(document.id) for document in selected}
    buckets: dict[str, deque[Document]] = defaultdict(deque)
    for document in documents:
        if str(document.id) not in selected_ids:
            buckets[document.source_name].append(document)

    source_names = sorted(buckets)
    while len(selected) < sample_size:
        added = False
        for source_name in source_names:
            if len(selected) >= sample_size:
                break
            if buckets[source_name]:
                selected.append(buckets[source_name].popleft())
                added = True
        if not added:
            break
    return selected


def review_key(document: Document, generated: dict) -> str:
    payload = json.dumps(
        {
            "content_hash": document.content_hash,
            "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
            "generated": generated,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def classify_document(
    document: Document,
    summarizer: ArticleSummaryService,
    source_config: dict,
) -> dict:
    metadata = dict(document.doc_metadata or {})
    default_topic = source_config.get(
        "default_primary_topic",
        "ai-products-engineering-infrastructure",
    )
    default_events = source_config.get("default_event_types", ["analysis"])
    is_excerpt = (
        metadata.get("evidence_level") == "official_feed_excerpt"
        or metadata.get("rag_eligible") is False
    )
    if is_excerpt:
        result = classify_excerpt(document, source_config)
    else:
        result = summarizer.classify_taxonomy(
            title=document.title,
            raw_text=document.raw_text,
            default_topic=default_topic,
            default_event_types=default_events,
        )

    (
        topic,
        events,
        method,
        main_theme,
        category_reason,
        relevance_tier,
        relevance_reason,
        event_reason,
    ) = result
    return {
        "relevance": {
            "tier": relevance_tier,
            "reason": relevance_reason,
        },
        "main_theme": main_theme,
        "category": {
            "primary_topic": topic,
            "reason": category_reason,
        },
        "event": {
            "event_type": events[0],
            "reason": event_reason,
        },
        "classification_method": method,
        "is_feed_excerpt": is_excerpt,
    }


def prepare_review(
    sample_size: int,
    model: str | None,
    required_document_ids: tuple[str, ...] = (),
    prior_payload: dict | None = None,
) -> dict:
    documents = select_source_balanced(
        load_documents(),
        max(0, sample_size),
        required_document_ids,
    )
    source_configs = load_sources()
    summarizer = ArticleSummaryService(model=model)
    prior_payload = prior_payload or {}
    can_reuse = (
        prior_payload.get("taxonomy_policy_version") == TAXONOMY_POLICY_VERSION
        and prior_payload.get("model") == summarizer.model
    )
    prior_items = {
        item["document_id"]: item
        for item in prior_payload.get("items", [])
        if item.get("document_id")
    }
    items: list[dict] = []
    reused_classifications = 0

    for document in documents:
        model_input_text = (document.raw_text or "")[:MODEL_TEXT_LIMIT]
        model_input_sha256 = hashlib.sha256(
            model_input_text.encode("utf-8")
        ).hexdigest()
        prior = prior_items.get(str(document.id), {})
        prior_input_matches = (
            prior.get("model_input_sha256") == model_input_sha256
            or prior.get("source_text") == model_input_text
        )
        if (
            can_reuse
            and prior_input_matches
            and isinstance(prior.get("generated"), dict)
        ):
            generated = prior["generated"]
            reused_classifications += 1
        else:
            generated = classify_document(
                document,
                summarizer,
                source_configs.get(document.source_name, {}),
            )
        items.append(
            {
                "document_id": str(document.id),
                "review_key": review_key(document, generated),
                "source_name": document.source_name,
                "title": document.title,
                "url": document.canonical_url or document.url,
                "published_at": document.published_at.isoformat()
                if document.published_at
                else None,
                "source_preview": model_input_text[:SOURCE_PREVIEW_LIMIT],
                "model_input_sha256": model_input_sha256,
                "source_text_characters": len(document.raw_text or ""),
                "source_text_truncated_for_model": len(document.raw_text or "")
                > MODEL_TEXT_LIMIT,
                "generated": generated,
                "human_review": {
                    "relevance_review": "not_reviewed",
                    "proposed_relevance_tier": None,
                    "primary_topic_review": "not_reviewed",
                    "proposed_primary_topic": None,
                    "event_type_review": "not_reviewed",
                    "proposed_event_type": None,
                    "review_notes": "",
                },
            }
        )

    relevance_counts = Counter(
        item["generated"]["relevance"]["tier"] for item in items
    )
    category_counts = Counter(
        item["generated"]["category"]["primary_topic"] for item in items
    )
    event_counts = Counter(
        item["generated"]["event"]["event_type"] for item in items
    )
    source_counts = Counter(item["source_name"] for item in items)
    generated_at = datetime.now(timezone.utc).isoformat()
    return {
        "schema_version": 2,
        "taxonomy_policy_version": TAXONOMY_POLICY_VERSION,
        "generated_at": generated_at,
        "model": summarizer.model,
        "purpose": (
            "Human evaluation of the taxonomy-v2 relevance, category, and event "
            "decision gates on a source-balanced sample of the current local corpus."
        ),
        "sampling": {
            "method": "round_robin_recent_documents_by_enabled_source",
            "requested_items": sample_size,
            "selected_items": len(items),
            "model_text_limit_characters": MODEL_TEXT_LIMIT,
            "source_preview_limit_characters": SOURCE_PREVIEW_LIMIT,
            "required_document_ids": list(required_document_ids),
            "reused_classifications": reused_classifications,
            "new_classifications": len(items) - reused_classifications,
        },
        "review_order": [
            "Review relevance first; excluded documents do not need category or event corrections.",
            "Review primary category against the article's central AI theme.",
            "Review event type against why the article exists.",
        ],
        "allowed_review_values": list(REVIEW_VALUES),
        "allowed_relevance_tiers": list(RELEVANCE_TIERS),
        "allowed_primary_topics": list(PRIMARY_TOPICS),
        "allowed_event_types": list(EVENT_TYPES),
        "instructions": {
            "correct": "Keep the generated value and leave its proposed field null.",
            "change_required": "Fill its proposed field and explain the correction in review_notes.",
            "uncertain": "Describe the competing interpretations in review_notes.",
            "not_reviewed": "This decision has not yet been reviewed.",
        },
        "generated_summary": {
            "source_counts": dict(sorted(source_counts.items())),
            "relevance_counts": dict(sorted(relevance_counts.items())),
            "category_counts": dict(sorted(category_counts.items())),
            "event_counts": dict(sorted(event_counts.items())),
        },
        "items": items,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a source-balanced taxonomy-v2 human-review sample."
    )
    parser.add_argument("--sample-size", type=int, default=50)
    parser.add_argument("--model", help="Optional model override")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--include-document-id",
        action="append",
        default=[],
        help="Require a document in the sample; may be supplied more than once.",
    )
    arguments = parser.parse_args()

    output = arguments.output.resolve()
    prior_payload = {}
    if output.exists():
        prior_payload = json.loads(output.read_text(encoding="utf-8"))
    payload = prepare_review(
        arguments.sample_size,
        arguments.model,
        tuple(arguments.include_document_id),
        prior_payload,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), **payload["generated_summary"]}))


if __name__ == "__main__":
    main()
