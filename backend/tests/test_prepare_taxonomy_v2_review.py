from app.db.models import Document
from scripts.prepare_taxonomy_v2_review import review_key, select_source_balanced


def document(document_id: str, source_name: str) -> Document:
    return Document(
        id=document_id,
        source_name=source_name,
        source_type="release",
        title=document_id,
        url=f"https://example.com/{document_id}",
        raw_text="Example source text",
        content_hash=f"hash-{document_id}",
        doc_metadata={},
    )


def test_select_source_balanced_round_robins_sources() -> None:
    documents = [
        document("a1", "a"),
        document("a2", "a"),
        document("a3", "a"),
        document("b1", "b"),
        document("b2", "b"),
        document("c1", "c"),
    ]

    selected = select_source_balanced(documents, 5)

    assert [item.id for item in selected] == ["a1", "b1", "c1", "a2", "b2"]


def test_select_source_balanced_keeps_required_boundary_case() -> None:
    documents = [
        document("a1", "a"),
        document("a2", "a"),
        document("b1", "b"),
        document("b2", "b"),
    ]

    selected = select_source_balanced(documents, 3, ("b2",))

    assert [item.id for item in selected] == ["b2", "a1", "b1"]


def test_review_key_changes_when_generated_decision_changes() -> None:
    item = document("a1", "a")
    first = review_key(item, {"relevance": {"tier": "core"}})
    second = review_key(item, {"relevance": {"tier": "excluded"}})

    assert first != second
