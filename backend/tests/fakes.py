"""Test doubles shared across the suite."""

from sqlalchemy.sql.dml import Delete

from app.db.models import Document
from app.ingestion.ingest import ArticleIngestor


class FakeDatabase:
    """Records writes; `scalar` returns the article an ingestion lookup should find."""

    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added: list = []
        self.deletes = 0

    @property
    def document(self) -> Document | None:
        """The article most recently added."""
        return next((item for item in reversed(self.added) if isinstance(item, Document)), None)

    def scalar(self, _statement):
        return self.existing if self.existing is not None else self.document

    def add(self, item) -> None:
        self.added.append(item)

    def execute(self, statement) -> None:
        if isinstance(statement, Delete):
            self.deletes += 1

    def flush(self) -> None:
        pass


class MustNotRun:
    """A collaborator the code under test must not touch on this path."""

    def __init__(self, label: str) -> None:
        self.label = label

    def __getattr__(self, name):
        raise AssertionError(f"{self.label}.{name} should not run on this path")


def make_ingestor(
    db: FakeDatabase, *, relevance=None, summarizer=None, chunker=None, embedder=None
) -> ArticleIngestor:
    """An ingestor whose collaborators fail the test unless a path explicitly needs them."""
    return ArticleIngestor(
        db,
        relevance=relevance or MustNotRun("relevance"),
        summarizer=summarizer or MustNotRun("summarizer"),
        chunker=chunker or MustNotRun("chunker"),
        embedder=embedder or MustNotRun("embedder"),
    )
