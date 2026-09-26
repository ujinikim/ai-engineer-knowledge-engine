from types import SimpleNamespace

from app.services.ingestion_policy import (
    PUBLISHED,
    QUARANTINED,
    evaluate_ingestion_candidate,
)
from app.services.update_collector import UpdateCollectorService
from app.services.article_relevance import RelevanceDecision


def test_detailed_source_is_publishable() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="detailed",
        hydration_status="full_article",
        extraction_status="full_article",
        event_types=["engineering-analysis"],
    )

    assert decision.status == PUBLISHED
    assert decision.failure_codes == ()


def test_failed_hydration_and_sparse_excerpt_are_quarantined() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="sparse",
        hydration_status="failed",
        extraction_status="feed_excerpt_only",
        event_types=["product-release"],
    )

    assert decision.status == QUARANTINED
    assert decision.failure_codes == (
        "article_hydration_failed",
        "insufficient_source_detail",
    )


def test_important_sparse_event_can_publish_when_fetch_did_not_fail() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="sparse",
        hydration_status="not_requested",
        extraction_status="source_entry",
        event_types=["security-issue"],
    )

    assert decision.status == PUBLISHED


def test_approved_official_feed_excerpt_is_dashboard_only_evidence() -> None:
    decision = evaluate_ingestion_candidate(
        content_detail="sparse",
        hydration_status="failed",
        extraction_status="feed_excerpt_only",
        event_types=["product-release"],
        publish_feed_excerpt=True,
    )

    assert decision.status == PUBLISHED
    assert decision.failure_codes == ()
    assert decision.warning_codes == (
        "article_hydration_failed",
        "insufficient_source_detail",
    )
    assert decision.evidence_level == "official_feed_excerpt"
    assert decision.default_feed_eligible is True
    assert decision.rag_eligible is False


def test_quarantined_candidate_skips_summary_and_embeddings() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.added = []

        def scalar(self, _statement):
            return None

        def add(self, item) -> None:
            self.added.append(item)

        def flush(self) -> None:
            pass

    class MustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"{name} should not run for a quarantined candidate")

    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = FakeDatabase()
    collector.summarizer = MustNotRun()
    collector.relevance = MustNotRun()
    collector.chunker = MustNotRun()
    collector.embedder = MustNotRun()

    status, chunk_count = collector._upsert_entry(
        SimpleNamespace(slug="openai-news"),
        {
            "organization": "OpenAI",
            "tool": "OpenAI",
            "category": "models-apis",
            "default_primary_topic": "models-apis",
            "source_type": "official-product-news",
            "default_event_types": ["product-release"],
        },
        {
            "title": "Sparse announcement",
            "link": "https://example.com/sparse-announcement/",
            "summary": "A short feed excerpt.",
            "_hydration_status": "failed",
            "_extraction_status": "feed_excerpt_only",
            "_full_article_fetch_error_code": "http_forbidden",
        },
    )

    assert status == "quarantined"
    assert chunk_count == 0
    assert len(collector.db.added) == 1
    metadata = collector.db.added[0].doc_metadata
    assert collector.db.added[0].ingestion_status == QUARANTINED
    assert "ingestion_status" not in metadata
    assert "default_feed_eligible" not in metadata


def test_approved_feed_excerpt_skips_summary_and_embeddings_but_publishes() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.added = []

        def scalar(self, _statement):
            return None

        def add(self, item) -> None:
            self.added.append(item)

        def flush(self) -> None:
            pass

    class MustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"{name} should not run for feed-only evidence")

    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = FakeDatabase()
    collector.summarizer = MustNotRun()
    collector.relevance = SimpleNamespace(
        classify=lambda **_kwargs: RelevanceDecision(
            tier="core",
            reason="Direct agent engineering article.",
            generated_by="test",
        )
    )
    collector.chunker = MustNotRun()
    collector.embedder = MustNotRun()

    status, chunk_count = collector._upsert_entry(
        SimpleNamespace(slug="openai-news"),
        {
            "organization": "OpenAI",
            "tool": "OpenAI",
            "category": "models-apis",
            "default_primary_topic": "models-apis",
            "source_type": "official-product-news",
            "default_event_types": ["product-release"],
            "publish_feed_excerpt": True,
        },
        {
            "title": "Agents API announcement",
            "link": "https://example.com/agents-api",
            "summary": "OpenAI announced an API for building and operating agents.",
            "_hydration_status": "failed",
            "_extraction_status": "feed_excerpt_only",
            "_full_article_fetch_error_code": "http_forbidden",
        },
    )

    assert status == "created"
    assert chunk_count == 0
    assert len(collector.db.added) == 1
    metadata = collector.db.added[0].doc_metadata
    assert collector.db.added[0].ingestion_status == PUBLISHED
    assert collector.db.added[0].evidence_level == "official_feed_excerpt"
    assert "rag_eligible" not in metadata
    assert "default_feed_eligible" not in metadata
    assert metadata["summary_generated_by"] == "source-excerpt"
    assert metadata["taxonomy_generated_by"] == "deterministic-keyword"
    assert metadata["summary"] == metadata["excerpt"]


def test_failed_refresh_does_not_replace_an_existing_published_document() -> None:
    existing = SimpleNamespace(
        raw_text="Release\n\nA complete article that was previously published.",
        content_hash="existing-content-hash",
        fetched_at=None,
        ingestion_status=PUBLISHED,
        evidence_level="full_article",
        doc_metadata={},
    )

    class FakeDatabase:
        def scalar(self, _statement):
            return existing

    class MustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"{name} should not run for a failed refresh")

    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = FakeDatabase()
    collector.summarizer = MustNotRun()
    collector.chunker = MustNotRun()
    collector.embedder = MustNotRun()

    status, chunk_count = collector._upsert_entry(
        SimpleNamespace(slug="openai-news"),
        {
            "organization": "OpenAI",
            "tool": "OpenAI",
            "category": "models-apis",
            "default_primary_topic": "models-apis",
            "source_type": "official-product-news",
            "default_event_types": ["product-release"],
            "publish_feed_excerpt": True,
        },
        {
            "title": "Release",
            "link": "https://example.com/release",
            "summary": "Short excerpt.",
            "_hydration_status": "failed",
            "_extraction_status": "feed_excerpt_only",
        },
    )

    assert status == "unchanged"
    assert chunk_count == 0
    assert existing.raw_text == "Release\n\nA complete article that was previously published."
    assert existing.content_hash == "existing-content-hash"
    assert existing.ingestion_status == PUBLISHED
    assert existing.doc_metadata["last_ingestion_attempt_status"] == PUBLISHED
    assert existing.doc_metadata["last_ingestion_failure_codes"] == []
    assert existing.doc_metadata["last_ingestion_warning_codes"] == [
        "article_hydration_failed",
        "insufficient_source_detail",
    ]
    assert existing.doc_metadata["last_ingestion_evidence_level"] == "official_feed_excerpt"


def test_relevance_excluded_article_skips_summary_chunks_and_embeddings() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.added = []

        def scalar(self, _statement):
            return None

        def add(self, item) -> None:
            self.added.append(item)

        def flush(self) -> None:
            pass

    class MustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"{name} should not run for excluded content")

    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = FakeDatabase()
    collector.relevance = SimpleNamespace(
        classify=lambda **_kwargs: RelevanceDecision(
            tier="excluded",
            reason="The article is a general cloud dashboard tutorial.",
            generated_by="gpt-test",
        )
    )
    collector.summarizer = MustNotRun()
    collector.chunker = MustNotRun()
    collector.embedder = MustNotRun()
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

    status, chunk_count = collector._upsert_entry(
        SimpleNamespace(slug="example"),
        {
            "organization": "Example",
            "tool": "Example Cloud",
            "category": "ai-products-engineering-infrastructure",
            "default_primary_topic": "ai-products-engineering-infrastructure",
            "source_type": "official-engineering-blog",
            "default_event_types": ["guide"],
        },
        {
            "title": "Build a cloud dashboard",
            "link": "https://example.com/cloud-dashboard",
            "summary": body,
        },
    )

    assert status == "created"
    assert chunk_count == 0
    assert len(collector.db.added) == 1
    metadata = collector.db.added[0].doc_metadata
    assert collector.db.added[0].ingestion_status == PUBLISHED
    assert "rag_eligible" not in metadata
    assert not {
        "ingestion_status", "evidence_level", "relevance_tier", "relevance_reason",
        "primary_topic", "ingestion_warning_codes", "taxonomy_main_theme",
        "extraction_metadata_version",
    }.intersection(metadata)
    assert collector.db.added[0].evidence_level == "source_entry"
    assert collector.db.added[0].relevance_tier == "excluded"
    assert collector.db.added[0].relevance_reason == "The article is a general cloud dashboard tutorial."
    assert metadata["summary_generated_by"] == "relevance-excluded"
    assert collector.db.added[0].relevance_tier == "excluded"
    assert "relevance_reason" not in metadata
    assert metadata["relevance_generated_by"] == "gpt-test"
    assert metadata["relevance_classification_status"] == "classified"


def test_failed_relevance_stays_unclassified_and_retries_without_content_change() -> None:
    class FakeDatabase:
        def __init__(self) -> None:
            self.document = None

        def scalar(self, _statement):
            return self.document

        def add(self, document) -> None:
            self.document = document

        def execute(self, _statement) -> None:
            pass

        def flush(self) -> None:
            pass

    class MustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"{name} should not run before relevance classification")

    attempts = []

    def classify(**_kwargs):
        attempts.append(True)
        return RelevanceDecision(tier=None, reason="Model unavailable.", generated_by="classification-error", status="failed")

    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = FakeDatabase()
    collector.relevance = SimpleNamespace(classify=classify)
    collector.summarizer = MustNotRun()
    collector.chunker = MustNotRun()
    collector.embedder = MustNotRun()
    config = {
        "organization": "Example",
        "tool": "Agent SDK",
        "category": "agentic-generative-ai",
        "default_primary_topic": "agentic-generative-ai",
        "source_type": "official-engineering-blog",
        "default_event_types": ["guide"],
    }
    entry = {
        "title": "Build reliable agents",
        "link": "https://example.com/agents",
        "summary": " ".join(
            [
                "This guide explains how to build reliable agents with tools and clear boundaries.",
                "It shows how to test tool calls against realistic user tasks and failures.",
                "The workflow records traces so engineers can diagnose broken agent decisions.",
                "A deployment section covers retries, permissions, and monitoring in production.",
                "The examples compare expected results with observed agent behavior.",
            ]
        ),
    }

    status, chunks = collector._upsert_entry("example", config, entry)
    assert (status, chunks) == ("created", 0)
    assert collector.db.document.relevance_tier is None
    assert "rag_eligible" not in collector.db.document.doc_metadata
    assert "default_feed_eligible" not in collector.db.document.doc_metadata

    status, chunks = collector._upsert_entry("example", config, entry)
    assert (status, chunks) == ("unchanged", 0)
    assert len(attempts) == 2

    collector.relevance = SimpleNamespace(
        classify=lambda **_kwargs: RelevanceDecision(
            tier="core", reason="Direct agent engineering guide.", generated_by="gpt-test"
        )
    )
    collector.summarizer = SimpleNamespace(
        summarize=lambda **_kwargs: SimpleNamespace(
            primary_topic="agentic-generative-ai",
            metadata=lambda: {"event_types": ["guide"], "summary": "Agent guide summary."},
        )
    )
    collector.chunker = SimpleNamespace(chunk_text=lambda *_args, **_kwargs: [])
    collector.embedder = SimpleNamespace(embed_texts=lambda *_args, **_kwargs: [])

    status, chunks = collector._upsert_entry("example", config, entry)
    assert (status, chunks) == ("changed", 0)
    assert collector.db.document.relevance_tier == "core"
    assert "default_feed_eligible" not in collector.db.document.doc_metadata


def test_failed_reclassification_keeps_existing_good_article() -> None:
    existing = SimpleNamespace(
        raw_text="Original agent article",
        content_hash="original-hash",
        relevance_tier="core",
        fetched_at=None,
        ingestion_status=PUBLISHED,
        doc_metadata={"relevance_classification_status": "classified"},
    )

    class FakeDatabase:
        def scalar(self, _statement):
            return existing

    class MustNotRun:
        def __getattr__(self, name):
            raise AssertionError(f"{name} should not run for failed reclassification")

    collector = UpdateCollectorService.__new__(UpdateCollectorService)
    collector.db = FakeDatabase()
    collector.relevance = SimpleNamespace(
        classify=lambda **_kwargs: RelevanceDecision(
            tier=None,
            reason="Model unavailable.",
            generated_by="classification-error",
            status="failed",
        )
    )
    collector.summarizer = MustNotRun()
    collector.chunker = MustNotRun()
    collector.embedder = MustNotRun()
    body = " ".join(
        [
            "This article explains how to build reliable agents with tools and clear boundaries.",
            "It shows how to test tool calls against realistic user tasks and failures.",
            "The workflow records traces so engineers can diagnose broken agent decisions.",
            "A deployment section covers retries, permissions, and monitoring in production.",
            "The examples compare expected results with observed agent behavior.",
        ]
    )

    status, chunks = collector._upsert_entry(
        "example",
        {
            "organization": "Example",
            "tool": "Agent SDK",
            "category": "agentic-generative-ai",
            "default_primary_topic": "agentic-generative-ai",
            "source_type": "official-engineering-blog",
            "default_event_types": ["guide"],
        },
        {"title": "Changed agent article", "link": "https://example.com/agents", "summary": body},
    )

    assert (status, chunks) == ("unchanged", 0)
    assert existing.raw_text == "Original agent article"
    assert existing.content_hash == "original-hash"
    assert existing.relevance_tier == "core"
    assert existing.doc_metadata["last_relevance_attempt_status"] == "failed"
