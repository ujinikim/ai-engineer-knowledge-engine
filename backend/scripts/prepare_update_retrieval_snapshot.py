import argparse
import hashlib
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.core.settings import settings
from app.db.models import Chunk, Document
from app.db.session import SessionLocal


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = (
    ROOT
    / "data"
    / "eval"
    / "retrieval"
    / "updates_snapshot_2026-07-27.json"
)


def isoformat(value: object) -> str | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def snapshot_document(document: Document, chunk_count: int) -> dict[str, Any]:
    metadata = dict(document.doc_metadata or {})
    return {
        "document_id": str(document.id),
        "source_name": document.source_name,
        "title": document.title,
        "url": document.url,
        "canonical_url": document.canonical_url or document.url,
        "published_at": isoformat(document.published_at),
        "fetched_at": isoformat(document.fetched_at),
        "content_hash": document.content_hash,
        "chunk_count": chunk_count,
        "tool": metadata.get("tool"),
        "primary_topic": metadata.get("primary_topic") or metadata.get("category"),
        "event_types": list(metadata.get("event_types") or []),
        "source_category": metadata.get("source_type"),
        "maturity": metadata.get("maturity"),
        "content_detail": metadata.get("content_detail"),
        "taxonomy_policy_version": metadata.get("taxonomy_policy_version"),
        "extraction_metadata_version": metadata.get("extraction_metadata_version"),
        "summary_generated_by": metadata.get("summary_generated_by"),
    }


def corpus_hash(documents: list[dict[str, Any]]) -> str:
    identity = [
        {
            "document_id": item["document_id"],
            "content_hash": item["content_hash"],
            "chunk_count": item["chunk_count"],
        }
        for item in documents
    ]
    payload = json.dumps(identity, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Freeze a versioned manifest of the update retrieval corpus."
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args()

    with SessionLocal() as db:
        documents = list(
            db.scalars(
                select(Document)
                .where(Document.source_type == "release")
                .order_by(Document.source_name, Document.published_at, Document.id)
            )
        )
        chunk_counts = dict(
            db.execute(
                select(Chunk.document_id, func.count(Chunk.id))
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.source_type == "release")
                .group_by(Chunk.document_id)
            ).all()
        )

    records = [
        snapshot_document(document, int(chunk_counts.get(document.id, 0)))
        for document in documents
    ]
    source_counts = Counter(item["source_name"] for item in records)
    topic_counts = Counter(str(item["primary_topic"] or "unknown") for item in records)
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "purpose": "Frozen Phase 3 retrieval benchmark corpus manifest.",
        "document_count": len(records),
        "chunk_count": sum(item["chunk_count"] for item in records),
        "corpus_hash": corpus_hash(records),
        "embedding": {
            "model": settings.embedding_model,
            "dimensions": settings.embedding_dimensions,
        },
        "source_counts": dict(sorted(source_counts.items())),
        "primary_topic_counts": dict(sorted(topic_counts.items())),
        "documents": records,
    }

    output = arguments.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Documents: {payload['document_count']}")
    print(f"Chunks: {payload['chunk_count']}")
    print(f"Corpus hash: {payload['corpus_hash']}")
    print(f"Output: {output}")


if __name__ == "__main__":
    main()
