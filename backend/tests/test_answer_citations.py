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
