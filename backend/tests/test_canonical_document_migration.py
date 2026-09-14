from importlib import import_module
from unittest.mock import Mock


def test_canonical_field_migration_is_non_destructive_and_backfills_compatibility_data(
    monkeypatch,
) -> None:
    migration = import_module(
        "migrations.versions.20260913_0004_canonical_document_fields"
    )
    operation = Mock()
    monkeypatch.setattr(migration, "op", operation)

    migration.upgrade()

    added_document_columns = {
        call.args[1].name
        for call in operation.add_column.call_args_list
        if call.args[0] == "documents"
    }
    added_chunk_columns = {
        call.args[1].name
        for call in operation.add_column.call_args_list
        if call.args[0] == "chunks"
    }
    executed_sql = "\n".join(call.args[0] for call in operation.execute.call_args_list)

    assert added_document_columns == {
        "ingestion_status",
        "evidence_level",
        "relevance_tier",
        "relevance_reason",
        "primary_topic",
        "event_type",
        "summary",
        "processing_metadata",
    }
    assert added_chunk_columns == {"embedding_model", "chunking_version"}
    assert "doc_metadata->>'feed_relevance_tier'" in executed_sql
    assert "doc_metadata->'event_types'->>0" in executed_sql
    assert "doc_metadata->>'summary'" in executed_sql
    assert "doc_metadata->'processing_metadata'" in executed_sql
    assert "chunk_metadata->>'embedding_model'" in executed_sql
    assert "chunk_metadata->>'chunking_version'" in executed_sql
    assert "DROP COLUMN" not in executed_sql.upper()
    assert operation.drop_column.call_count == 0


def test_canonical_field_migration_follows_current_revision_chain() -> None:
    migration = import_module(
        "migrations.versions.20260913_0004_canonical_document_fields"
    )

    assert migration.revision == "20260913_0004"
    assert migration.down_revision == "20260912_0003"
