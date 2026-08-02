from sqlalchemy import UniqueConstraint

from app.db.models import Chunk, Document, UpdateSource


def test_model_metadata_matches_baseline_tables_and_indexes() -> None:
    tables = {Document.__table__.name, Chunk.__table__.name, UpdateSource.__table__.name}
    indexes = {
        index.name
        for table in (Document.__table__, Chunk.__table__, UpdateSource.__table__)
        for index in table.indexes
    }

    assert tables == {"documents", "chunks", "update_sources"}
    assert indexes == {
        "documents_source_name_idx",
        "documents_content_hash_idx",
        "documents_source_type_idx",
        "documents_published_at_idx",
        "chunks_document_id_idx",
        "chunks_content_hash_idx",
        "chunks_embedding_hnsw_idx",
        "chunks_content_fts_idx",
        "update_sources_slug_idx",
        "update_sources_tool_idx",
        "update_sources_category_idx",
    }


def test_chunk_position_is_unique_and_document_delete_cascades() -> None:
    unique_column_sets = {
        tuple(column.name for column in constraint.columns)
        for constraint in Chunk.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    document_foreign_key = next(iter(Chunk.__table__.c.document_id.foreign_keys))

    assert ("document_id", "chunk_index") in unique_column_sets
    assert document_foreign_key.ondelete == "CASCADE"
