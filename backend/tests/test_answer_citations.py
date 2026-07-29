from types import SimpleNamespace

from app.services.answer import AnswerService


def citation_ids(answer: str, context_count: int):
    service = AnswerService.__new__(AnswerService)
    return service._citation_ids(answer, context_count)


def test_only_used_valid_citations_are_returned():
    used, warnings = citation_ids("The release added streaming [2] and caching [1]. [2]", 3)

    assert used == {1, 2}
    assert warnings == []


def test_unknown_citations_are_reported():
    used, warnings = citation_ids("This claim uses [1] and [9].", 2)

    assert used == {1}
    assert warnings == ["Answer referenced unknown citation [9]."]


def test_uncited_answer_is_reported():
    used, warnings = citation_ids("An answer without evidence.", 2)

    assert used == set()
    assert warnings == ["Answer did not reference any retrieved evidence."]


def test_uncited_insufficient_evidence_answer_is_not_reported_as_citation_failure():
    used, warnings = citation_ids(
        "The context does not include information about that release.",
        2,
    )

    assert used == set()
    assert warnings == []


def test_completion_limit_produces_generation_warning():
    service = AnswerService.__new__(AnswerService)

    assert service._generation_warnings("length") == [
        "Answer reached the completion-token limit and may be truncated."
    ]
    assert service._generation_warnings("stop") == []


def test_context_selection_counts_formatted_metadata():
    service = AnswerService.__new__(AnswerService)
    chunks = [
        SimpleNamespace(
            document_title=f"Release {index}",
            source_name="source",
            published_at=None,
            tool="tool",
            url="https://example.com/release",
            content="update " * 100,
        )
        for index in range(4)
    ]

    selected = service._context_chunks(chunks, max_tokens=150)
    context = service._build_context(selected)

    assert len(selected) == 1
    assert service._count_tokens(context) <= 150


def test_comparison_context_prioritizes_distinct_documents():
    service = AnswerService.__new__(AnswerService)
    chunks = [
        SimpleNamespace(
            document_id="a",
            document_title="Release A",
            source_name="source-a",
            published_at=None,
            tool="tool",
            url="https://example.com/a",
            content="first A",
        ),
        SimpleNamespace(
            document_id="a",
            document_title="Release A",
            source_name="source-a",
            published_at=None,
            tool="tool",
            url="https://example.com/a/",
            content="second A",
        ),
        SimpleNamespace(
            document_id="b",
            document_title="Release B",
            source_name="source-b",
            published_at=None,
            tool="tool",
            url="https://example.com/b",
            content="first B",
        ),
    ]

    selected = service._context_chunks(
        chunks,
        max_tokens=1000,
        prefer_document_diversity=True,
    )

    assert [chunk.content for chunk in selected] == ["first A", "first B", "second A"]


def test_context_selection_tries_later_chunks_when_one_does_not_fit():
    service = AnswerService.__new__(AnswerService)
    chunks = [
        SimpleNamespace(
            document_id="a",
            document_title="Release A",
            source_name="source-a",
            published_at=None,
            tool="tool",
            url="https://example.com/a",
            content="short",
        ),
        SimpleNamespace(
            document_id="b",
            document_title="Release B",
            source_name="source-b",
            published_at=None,
            tool="tool",
            url="https://example.com/b",
            content="large " * 500,
        ),
        SimpleNamespace(
            document_id="c",
            document_title="Release C",
            source_name="source-c",
            published_at=None,
            tool="tool",
            url="https://example.com/c",
            content="also short",
        ),
    ]

    selected = service._context_chunks(chunks, max_tokens=100)

    assert [chunk.document_id for chunk in selected] == ["a", "c"]
