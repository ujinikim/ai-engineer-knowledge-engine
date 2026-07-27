from datetime import datetime
from types import SimpleNamespace
from uuid import uuid4

from scripts.prepare_update_retrieval_snapshot import corpus_hash, snapshot_document


def test_snapshot_document_preserves_retrieval_identity_and_policy() -> None:
    document = SimpleNamespace(
        id=uuid4(),
        source_name="example",
        title="Example update",
        url="https://example.com/update",
        canonical_url=None,
        published_at=datetime(2026, 7, 27, 10, 0),
        fetched_at=datetime(2026, 7, 27, 11, 0),
        content_hash="content-hash",
        doc_metadata={
            "tool": "Example",
            "primary_topic": "developer-tools",
            "event_types": ["product-release"],
            "source_type": "official-product-news",
            "maturity": "stable",
            "content_detail": "detailed",
            "taxonomy_policy_version": "policy-v1",
            "extraction_metadata_version": "extraction-v1",
            "summary_generated_by": "model:source",
        },
    )

    item = snapshot_document(document, chunk_count=3)

    assert item["document_id"] == str(document.id)
    assert item["canonical_url"] == document.url
    assert item["chunk_count"] == 3
    assert item["taxonomy_policy_version"] == "policy-v1"
    assert item["published_at"].endswith("+00:00")


def test_corpus_hash_changes_with_content_or_chunk_identity() -> None:
    base = [{"document_id": "1", "content_hash": "a", "chunk_count": 2}]

    assert corpus_hash(base) == corpus_hash([dict(base[0])])
    assert corpus_hash(base) != corpus_hash(
        [{"document_id": "1", "content_hash": "b", "chunk_count": 2}]
    )
    assert corpus_hash(base) != corpus_hash(
        [{"document_id": "1", "content_hash": "a", "chunk_count": 3}]
    )
