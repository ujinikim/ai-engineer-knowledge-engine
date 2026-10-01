"""Every route an article can take through `ArticleIngestor.ingest`."""

import hashlib
import uuid
from types import SimpleNamespace

from app.db.models import Chunk, Document
from app.domain import PUBLISHED, QUARANTINED, evidence_level
from app.ingestion.ingest import ArticleIngestor
from app.ingestion.relevance import RELEVANCE_POLICY_VERSION, RelevanceDecision
from app.ingestion.summary import ArticleSummary
from app.ingestion.taxonomy import TAXONOMY_POLICY_VERSION
from tests.fakes import FakeDatabase, MustNotRun, make_ingestor

AGENT_SOURCE = {
    "organization": "Example",
    "tool": "Agent SDK",
    "category": "agentic-generative-ai",
    "default_primary_topic": "agentic-generative-ai",
    "source_type": "official-engineering-blog",
    "default_event_types": ["guide"],
}
OPENAI_SOURCE = {
    "organization": "OpenAI",
    "tool": "OpenAI",
    "category": "models-apis",
    "default_primary_topic": "models-apis",
    "source_type": "official-product-news",
    "default_event_types": ["product-release"],
}
TITLE = "Build reliable agents"
DETAILED_BODY = " ".join(
    [
        "This guide explains how to build reliable agents with tools and clear boundaries.",
        "It shows how to test tool calls against realistic user tasks and failures.",
        "The workflow records traces so engineers can diagnose broken agent decisions.",
        "A deployment section covers retries, permissions, and monitoring in production.",
        "The examples compare expected results with observed agent behavior.",
    ]
)
AGENT_ENTRY = {"title": TITLE, "link": "https://example.com/agents", "summary": DETAILED_BODY}


def classifies(tier: str | None, reason: str = "A reason.", status: str = "classified"):
    return SimpleNamespace(
        classify=lambda **_kwargs: RelevanceDecision(
            tier=tier, reason=reason, generated_by="gpt-test", status=status
        )
    )


def summarizes():
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


def chunks_in_two():
    return SimpleNamespace(
        chunk_text=lambda text, **_kwargs: [
            SimpleNamespace(index=0, content=text[:40], token_count=10),
            SimpleNamespace(index=1, content=text[40:80], token_count=10),
        ]
    )


def embeds():
    return SimpleNamespace(embed_texts=lambda texts: [[0.1] * 3 for _ in texts])


def stored_article(*, raw_text: str, extraction_status: str = "source_entry") -> Document:
    return Document(
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


def full_pipeline(db: FakeDatabase) -> ArticleIngestor:
    return make_ingestor(
        db,
        relevance=classifies("core", "Direct agent engineering guide."),
        summarizer=summarizes(),
        chunker=chunks_in_two(),
        embedder=embeds(),
    )


# New and changed content -----------------------------------------------------


def test_new_detailed_article_is_summarized_chunked_and_embedded() -> None:
    db = FakeDatabase()
    entry = {**AGENT_ENTRY, "link": "https://example.com/agents/?utm_source=x"}

    status, chunks = full_pipeline(db).ingest("example", AGENT_SOURCE, entry)

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
    existing = stored_article(raw_text=f"{TITLE}\n\nAn older, different body.")
    db = FakeDatabase(existing)

    status, chunks = full_pipeline(db).ingest("example", AGENT_SOURCE, AGENT_ENTRY)

    assert (status, chunks) == ("changed", 2)
    assert db.deletes == 1
    assert existing.raw_text == f"{TITLE}\n\n{DETAILED_BODY}"
    assert existing.summary == "How to build reliable agents."
    assert len(db.added) == 2


def test_unchanged_content_keeps_card_and_relevance_without_model_calls() -> None:
    existing = stored_article(raw_text=f"{TITLE}\n\n{DETAILED_BODY}")
    db = FakeDatabase(existing)

    status, chunks = make_ingestor(db).ingest("example", AGENT_SOURCE, AGENT_ENTRY)

    assert (status, chunks) == ("unchanged", 0)
    assert db.deletes == 0
    assert db.added == []
    assert existing.summary == "Existing summary."
    assert existing.relevance_reason == "Previously classified."
    assert existing.key_points == ["Existing point."]


# Quarantine ------------------------------------------------------------------


def test_new_sparse_feed_excerpt_is_quarantined_without_card_or_embeddings() -> None:
    db = FakeDatabase()
    entry = {
        "title": "Sparse announcement",
        "link": "https://example.com/sparse-announcement/",
        "summary": "A short feed excerpt.",
        "_extraction_status": "feed_excerpt_only",
        "_full_article_fetch_error_code": "http_forbidden",
    }

    status, chunks = make_ingestor(db).ingest("openai-news", OPENAI_SOURCE, entry)

    assert (status, chunks) == ("quarantined", 0)
    assert len(db.added) == 1
    assert db.document.ingestion_status == QUARANTINED
    assert db.document.extraction_status == "feed_excerpt_only"
    assert db.document.summary is None


def test_existing_sparse_article_that_fails_the_gate_is_quarantined_and_keeps_its_card() -> None:
    existing = stored_article(raw_text=f"{TITLE}\n\nShort note.")
    db = FakeDatabase(existing)
    entry = {"title": TITLE, "link": "https://example.com/agents", "summary": "Short note."}

    status, chunks = make_ingestor(db).ingest("example", AGENT_SOURCE, entry)

    assert (status, chunks) == ("quarantined", 0)
    assert db.deletes == 1
    assert existing.ingestion_status == "quarantined"
    assert existing.summary == "Existing summary."
    assert existing.relevance_tier == "core"


def test_changed_sparse_article_is_quarantined_with_normalized_url_and_no_card() -> None:
    existing = stored_article(raw_text=f"{TITLE}\n\nAn older, different body.")
    existing.url = "https://example.com/agents/"
    db = FakeDatabase(existing)
    entry = {"title": TITLE, "link": "https://example.com/agents/?utm_source=x", "summary": "Short note."}

    status, chunks = make_ingestor(db).ingest("example", AGENT_SOURCE, entry)

    assert (status, chunks) == ("quarantined", 0)
    assert db.deletes == 1
    assert existing.url == "https://example.com/agents"
    assert existing.ingestion_status == "quarantined"
    assert existing.summary is None
    assert existing.relevance_tier is None
    assert existing.raw_text == f"{TITLE}\n\nShort note."


# Excerpt cards ---------------------------------------------------------------


def test_approved_feed_excerpt_publishes_without_summary_or_embeddings() -> None:
    db = FakeDatabase()
    entry = {
        "title": "Agents API announcement",
        "link": "https://example.com/agents-api",
        "summary": "OpenAI announced an API for building and operating agents.",
        "_extraction_status": "feed_excerpt_only",
        "_full_article_fetch_error_code": "http_forbidden",
    }
    ingestor = make_ingestor(db, relevance=classifies("core", "Direct agent engineering article."))

    status, chunks = ingestor.ingest(
        "openai-news", {**OPENAI_SOURCE, "publish_feed_excerpt": True}, entry
    )

    assert (status, chunks) == ("created", 0)
    assert len(db.added) == 1
    document = db.document
    assert document.ingestion_status == PUBLISHED
    assert document.extraction_status == "feed_excerpt_only"
    assert evidence_level(
        extraction_status=document.extraction_status,
        ingestion_status=document.ingestion_status,
    ) == "official_feed_excerpt"
    assert document.summary_generated_by == "source-excerpt"
    assert document.summary == "OpenAI announced an API for building and operating agents."


def test_relevance_excluded_article_gets_an_excerpt_card_without_summary_or_embeddings() -> None:
    db = FakeDatabase()
    body = " ".join(
        [
            "This tutorial explains how to configure a general cloud dashboard.",
            "Readers create charts and arrange panels for business reporting.",
            "The walkthrough covers colors, labels, legends, and layout controls.",
            "It then shows how to share the finished dashboard with colleagues.",
            "The article includes examples for several ordinary analytics datasets.",
            "No artificial intelligence or agent workflow is part of the tutorial.",
        ]
    )
    entry = {"title": "Build a cloud dashboard", "link": "https://example.com/cloud-dashboard", "summary": body}
    ingestor = make_ingestor(
        db, relevance=classifies("excluded", "The article is a general cloud dashboard tutorial.")
    )

    status, chunks = ingestor.ingest("example", AGENT_SOURCE, entry)

    assert (status, chunks) == ("created", 0)
    assert len(db.added) == 1
    document = db.document
    assert document.ingestion_status == PUBLISHED
    assert document.extraction_status == "source_entry"
    assert document.relevance_tier == "excluded"
    assert document.relevance_reason == "The article is a general cloud dashboard tutorial."
    assert document.relevance_status == "classified"
    assert document.summary_generated_by == "relevance-excluded"


# Refreshes that must not make an article worse -----------------------------


def test_failed_refresh_does_not_replace_an_existing_published_article(caplog) -> None:
    existing = SimpleNamespace(
        raw_text="Release\n\nA complete article that was previously published.",
        content_hash="existing-content-hash",
        fetched_at=None,
        ingestion_status=PUBLISHED,
        extraction_status="full_article",
    )
    entry = {
        "title": "Release",
        "link": "https://example.com/release",
        "summary": "Short excerpt.",
        "_extraction_status": "feed_excerpt_only",
    }

    status, chunks = make_ingestor(FakeDatabase(existing)).ingest(
        "openai-news", {**OPENAI_SOURCE, "publish_feed_excerpt": True}, entry
    )

    assert (status, chunks) == ("unchanged", 0)
    assert existing.raw_text == "Release\n\nA complete article that was previously published."
    assert existing.content_hash == "existing-content-hash"
    assert existing.ingestion_status == PUBLISHED
    retained = next(
        record.structured_fields
        for record in caplog.records
        if getattr(record, "event", None) == "stored_article_retained"
    )
    assert retained["attempt_status"] == PUBLISHED
    assert retained["failure_codes"] == []
    assert retained["warning_codes"] == ["article_hydration_failed", "insufficient_source_detail"]
    assert retained["evidence_level"] == "official_feed_excerpt"


def test_failed_reclassification_keeps_the_existing_good_article(caplog) -> None:
    existing = SimpleNamespace(
        raw_text="Original agent article",
        content_hash="original-hash",
        relevance_tier="core",
        fetched_at=None,
        ingestion_status=PUBLISHED,
        extraction_status="source_entry",
        relevance_status="classified",
    )
    ingestor = make_ingestor(
        FakeDatabase(existing),
        relevance=classifies(None, "Model unavailable.", status="failed"),
    )
    entry = {**AGENT_ENTRY, "title": "Changed agent article"}

    status, chunks = ingestor.ingest("example", AGENT_SOURCE, entry)

    assert (status, chunks) == ("unchanged", 0)
    assert existing.raw_text == "Original agent article"
    assert existing.content_hash == "original-hash"
    assert existing.relevance_tier == "core"
    assert any(
        getattr(record, "event", None) == "relevance_classification_retained"
        for record in caplog.records
    )


def test_failed_relevance_stays_unclassified_and_retries_without_content_change() -> None:
    db = FakeDatabase()
    attempts = []

    def failing_classify(**_kwargs):
        attempts.append(True)
        return RelevanceDecision(
            tier=None, reason="Model unavailable.", generated_by="classification-error", status="failed"
        )

    ingestor = make_ingestor(db, relevance=SimpleNamespace(classify=failing_classify))

    status, chunks = ingestor.ingest("example", AGENT_SOURCE, AGENT_ENTRY)
    assert (status, chunks) == ("created", 0)
    assert db.document.relevance_tier is None
    assert db.document.relevance_status == "failed"

    status, chunks = ingestor.ingest("example", AGENT_SOURCE, AGENT_ENTRY)
    assert (status, chunks) == ("unchanged", 0)
    assert len(attempts) == 2

    ingestor.relevance = classifies("core", "Direct agent engineering guide.")
    ingestor.summarizer = SimpleNamespace(
        summarize=lambda **_kwargs: SimpleNamespace(
            primary_topic="agentic-generative-ai",
            fields=lambda: {"event_types": ["guide"], "summary": "Agent guide summary."},
        )
    )
    ingestor.chunker = SimpleNamespace(chunk_text=lambda *_args, **_kwargs: [])
    ingestor.embedder = SimpleNamespace(embed_texts=lambda *_args, **_kwargs: [])

    status, chunks = ingestor.ingest("example", AGENT_SOURCE, AGENT_ENTRY)
    assert (status, chunks) == ("changed", 0)
    assert db.document.relevance_tier == "core"
    assert db.document.summary == "Agent guide summary."


def test_must_not_run_fails_when_used() -> None:
    """Guards the fakes themselves: MustNotRun really fails when it is used."""
    try:
        MustNotRun("summarizer").summarize()
    except AssertionError as error:
        assert "summarizer.summarize should not run" in str(error)
    else:
        raise AssertionError("MustNotRun did not fail")
