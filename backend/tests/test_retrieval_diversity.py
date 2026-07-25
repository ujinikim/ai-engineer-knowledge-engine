from types import SimpleNamespace

from app.services.retriever import Candidate, RetrieverService


def candidate(document_id: str) -> Candidate:
    return Candidate(
        chunk=SimpleNamespace(),
        document=SimpleNamespace(id=document_id),
    )


def test_retrieval_limits_chunks_per_document():
    service = RetrieverService.__new__(RetrieverService)
    candidates = [candidate("a"), candidate("a"), candidate("a"), candidate("b"), candidate("c")]

    selected = service._diversify_documents(candidates, limit=4, max_per_document=2)

    assert [item.document.id for item in selected] == ["a", "a", "b", "c"]
