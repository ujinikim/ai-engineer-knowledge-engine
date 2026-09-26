from sqlalchemy import CheckConstraint, UniqueConstraint

from app.db.models import Chunk, CollectionSourceRun, Document


def test_model_metadata_matches_baseline_tables_and_indexes() -> None:
    tables = {Document.__table__.name, Chunk.__table__.name, CollectionSourceRun.__table__.name}
    indexes = {
        index.name
        for table in (Document.__table__, Chunk.__table__, CollectionSourceRun.__table__)
        for index in table.indexes
    }

    assert tables == {"documents", "chunks", "collection_source_runs"}
    assert indexes == {
        "documents_source_name_idx",
        "documents_content_hash_idx",
        "documents_published_at_idx",
        "documents_ingestion_status_idx",
        "documents_relevance_tier_idx",
        "documents_primary_topic_idx",
        "documents_feed_scope_idx",
        "chunks_document_id_idx",
        "chunks_content_hash_idx",
        "chunks_embedding_hnsw_idx",
        "chunks_content_fts_idx",
        "collection_source_runs_source_finished_idx",
    }


def test_document_model_exposes_canonical_decisions_and_compatibility_metadata() -> None:
    columns = Document.__table__.c
    check_constraints = {
        constraint.name
        for constraint in Document.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert {
        "ingestion_status",
        "evidence_level",
        "relevance_tier",
        "relevance_reason",
        "primary_topic",
        "doc_metadata",
    }.issubset(columns.keys())
    assert {
        "event_type", "summary", "processing_metadata", "source_type", "canonical_url"
    }.isdisjoint(columns.keys())
    assert columns.ingestion_status.nullable is False
    assert columns.evidence_level.nullable is False
    assert columns.relevance_tier.nullable is True
    assert columns.primary_topic.nullable is True
    assert check_constraints == {
        "ck_documents_ingestion_status",
        "ck_documents_evidence_level",
        "ck_documents_relevance_tier",
        "ck_documents_primary_topic",
    }


def test_chunk_model_omits_unpopulated_metadata_columns() -> None:
    for column in ("embedding_model", "chunking_version", "chunk_metadata"):
        assert column not in Chunk.__table__.c


def test_chunk_position_is_unique_and_document_delete_cascades() -> None:
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in Chunk.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    document_foreign_key = next(iter(Chunk.__table__.c.document_id.foreign_keys))

    assert ("document_id", "chunk_index") in unique_column_sets
    assert document_foreign_key.ondelete == "CASCADE"
