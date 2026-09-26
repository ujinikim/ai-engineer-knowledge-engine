from app.db.models import Document
from app.services.taxonomy import EVENT_TYPES, PRIMARY_TOPICS, TAXONOMY_POLICY_VERSION
from scripts.maintenance.backfill_taxonomy_v2 import build_query, classify_excerpt, load_sources
from sqlalchemy.dialects import postgresql


def test_backfill_query_scopes_to_enabled_published_updates() -> None:
    sql = str(
        build_query("openai-news").compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    ).lower()

    assert "documents.source_type" not in sql
    assert "anthropic-engineering" in sql
    assert "ingestion_status" in sql
    assert "documents.source_name" in sql


def test_excerpt_backfill_is_deterministic() -> None:
    document = Document(
        source_name="openai-news",
        title="Introducing a new agent model",
        url="https://example.com/agent",
        raw_text="Introducing a new agent model\n\nThe model uses tools to complete tasks.",
        content_hash="hash",
        doc_metadata={"excerpt": "The model uses tools to complete tasks."},
    )
    config = {
        "default_primary_topic": "agentic-generative-ai",
        "default_event_types": ["release-update"],
    }

    (
        topic,
        events,
        method,
        main_theme,
        reason,
        relevance_tier,
        relevance_reason,
        event_reason,
    ) = classify_excerpt(document, config)

    assert topic == "agentic-generative-ai"
    assert events == ["release-update"]
    assert method == "deterministic-keyword"
    assert main_theme is None
    assert reason == "Official feed excerpt used deterministic taxonomy rules."
    assert relevance_tier is None
    assert relevance_reason is None
    assert event_reason == "Official feed excerpt used deterministic event rules."
    assert TAXONOMY_POLICY_VERSION == "2026-09-12-v2"


def test_all_source_defaults_use_taxonomy_v2() -> None:
    for source in load_sources().values():
        assert source["default_primary_topic"] in PRIMARY_TOPICS
        assert len(source["default_event_types"]) == 1
        assert source["default_event_types"][0] in EVENT_TYPES
