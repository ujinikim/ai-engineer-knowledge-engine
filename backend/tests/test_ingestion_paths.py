"""Characterization tests for every route an entry can take through ingestion."""

import hashlib
import uuid
from types import SimpleNamespace

from sqlalchemy.sql.dml import Delete

from app.db.models import Chunk, Document
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.relevance import RELEVANCE_POLICY_VERSION, RelevanceDecision
from app.ingestion.summary import ArticleSummary
from app.ingestion.taxonomy import TAXONOMY_POLICY_VERSION

CONFIG = {
    "organization": "Example",
    "tool": "Agent SDK",
    "category": "agentic-generative-ai",
    "default_primary_topic": "agentic-generative-ai",
    "source_type": "official-engineering-blog",
    "default_event_types": ["guide"],
}
DETAILED_BODY = " ".join(
    [
        "This guide explains how to build reliable agents with tools and clear boundaries.",
        "It shows how to test tool calls against realistic user tasks and failures.",
        "The workflow records traces so engineers can diagnose broken agent decisions.",
        "A deployment section covers retries, permissions, and monitoring in production.",
        "The examples compare expected results with observed agent behavior.",
    ]
)
TITLE = "Build reliable agents"


class FakeDatabase:
    def __init__(self, existing=None) -> None:
        self.existing = existing
        self.added = []
        self.deletes = 0

    def scalar(self, _statement):
        return self.existing

    def add(self, item) -> None:
        self.added.append(item)

    def execute(self, statement) -> None:
        if isinstance(statement, Delete):
            self.deletes += 1

    def flush(self) -> None:
        pass


class MustNotRun:
    def __init__(self, label: str) -> None:
        self.label = label

    def __getattr__(self, name):
        raise AssertionError(f"{self.label}.{name} should not run on this path")


def make_collector(db: FakeDatabase, *, relevance=None, summarizer=None, chunker=None, embedder=None):
    collector = IngestionPipeline.__new__(IngestionPipeline)
    collector.db = db
    collector.relevance = relevance or MustNotRun("relevance")
    collector.summarizer = summarizer or MustNotRun("summarizer")
    collector.chunker = chunker or MustNotRun("chunker")
    collector.embedder = embedder or MustNotRun("embedder")
    return collector


def core_relevance():
    return SimpleNamespace(
        classify=lambda **_kwargs: RelevanceDecision(
            tier="core", reason="Direct agent engineering guide.", generated_by="gpt-test"
        )
    )


def summarizer():
    return SimpleNamespace(
        summarize=lambda **_kwargs: ArticleSummary(
            display_headline="Reliable agents",
            summary="How to build reliable agents.",
            why_it_matters="Agents fail in production without tests.",
            key_points=["Test tool calls.", "Record traces."],
            primary_topic="agentic-generative-ai",
            event_types=["guide", "analysis"],
            generated_by="gpt-test:official-engineering-blog",
        )
    )


def chunking():
    return SimpleNamespace(
        chunk_text=lambda text, **_kwargs: [
            SimpleNamespace(index=0, content=text[:40], token_count=10),
            SimpleNamespace(index=1, content=text[40:80], token_count=10),
        ]
    )


def embedding():
    return SimpleNamespace(embed_texts=lambda texts: [[0.1] * 3 for _ in texts])


def existing_document(*, raw_text: str, extraction_status: str = "source_entry") -> Document:
    document = Document(
        id=uuid.uuid4(),
        source_name="example",
        title=TITLE,
        url="https://example.com/agents",
        raw_text=raw_text,
        content_hash=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        ingestion_status="published",
        extraction_status=extraction_status,
        relevance_tier="core",
        relevance_reason="Previously classified.",
        relevance_status="classified",
        relevance_policy_version=RELEVANCE_POLICY_VERSION,
        primary_topic="agentic-generative-ai",
        event_types=["guide"],
        taxonomy_policy_version=TAXONOMY_POLICY_VERSION,
        display_headline="Existing headline",
        summary="Existing summary.",
        why_it_matters="Existing reason.",
        key_points=["Existing point."],
        summary_generated_by="gpt-test:official-engineering-blog",
    )
    return document


def test_new_detailed_article_is_summarized_chunked_and_embedded() -> None:
    db = FakeDatabase()
    collector = make_collector(
        db,
        relevance=core_relevance(),
        summarizer=summarizer(),
        chunker=chunking(),
        embedder=embedding(),
    )

    status, chunks = collector._upsert_entry(
        "example", CONFIG, {"title": TITLE, "link": "https://example.com/agents/?utm_source=x", "summary": DETAILED_BODY}
    )

    assert (status, chunks) == ("created", 2)
    document, *chunk_rows = db.added
    assert document.url == "https://example.com/agents"
    assert document.ingestion_status == "published"
    assert document.relevance_tier == "core"
    assert document.summary == "How to build reliable agents."
    assert document.event_types == ["guide"]
    assert document.taxonomy_policy_version == TAXONOMY_POLICY_VERSION
    assert [chunk.chunk_index for chunk in chunk_rows] == [0, 1]
    assert all(isinstance(chunk, Chunk) and chunk.document_id == document.id for chunk in chunk_rows)
    assert chunk_rows[0].content_hash == hashlib.sha256(chunk_rows[0].content.encode()).hexdigest()


def test_changed_content_replaces_card_and_chunks() -> None:
    existing = existing_document(raw_text=f"{TITLE}\n\nAn older, different body.")
    db = FakeDatabase(existing)
    collector = make_collector(
        db,
        relevance=core_relevance(),
        summarizer=summarizer(),
        chunker=chunking(),
        embedder=embedding(),
    )

    status, chunks = collector._upsert_entry(
        "example", CONFIG, {"title": TITLE, "link": "https://example.com/agents", "summary": DETAILED_BODY}
    )

    assert (status, chunks) == ("changed", 2)
    assert db.deletes == 1
    assert existing.raw_text == f"{TITLE}\n\n{DETAILED_BODY}"
    assert existing.summary == "How to build reliable agents."
    assert len(db.added) == 2


def test_unchanged_content_keeps_card_and_relevance_without_model_calls() -> None:
    existing = existing_document(raw_text=f"{TITLE}\n\n{DETAILED_BODY}")
    db = FakeDatabase(existing)
    collector = make_collector(db)

    status, chunks = collector._upsert_entry(
        "example", CONFIG, {"title": TITLE, "link": "https://example.com/agents", "summary": DETAILED_BODY}
    )

    assert (status, chunks) == ("unchanged", 0)
    assert db.deletes == 0
    assert db.added == []
    assert existing.summary == "Existing summary."
    assert existing.relevance_reason == "Previously classified."
    assert existing.key_points == ["Existing point."]


def test_existing_sparse_article_that_fails_the_gate_is_quarantined_and_keeps_its_card() -> None:
    sparse_text = f"{TITLE}\n\nShort note."
    existing = existing_document(raw_text=sparse_text)
    db = FakeDatabase(existing)
    collector = make_collector(db)

    status, chunks = collector._upsert_entry(
        "example", CONFIG, {"title": TITLE, "link": "https://example.com/agents", "summary": "Short note."}
    )

    assert (status, chunks) == ("quarantined", 0)
    assert db.deletes == 1
    assert existing.ingestion_status == "quarantined"
    assert existing.summary == "Existing summary."
    assert existing.relevance_tier == "core"


def test_changed_sparse_article_is_quarantined_with_normalized_url_and_no_card() -> None:
    existing = existing_document(raw_text=f"{TITLE}\n\nAn older, different body.")
    existing.url = "https://example.com/agents/"
    db = FakeDatabase(existing)
    collector = make_collector(db)

    status, chunks = collector._upsert_entry(
        "example", CONFIG, {"title": TITLE, "link": "https://example.com/agents/?utm_source=x", "summary": "Short note."}
    )

    assert (status, chunks) == ("quarantined", 0)
    assert db.deletes == 1
    assert existing.url == "https://example.com/agents"
    assert existing.ingestion_status == "quarantined"
    assert existing.summary is None
    assert existing.relevance_tier is None
    assert existing.raw_text == f"{TITLE}\n\nShort note."
