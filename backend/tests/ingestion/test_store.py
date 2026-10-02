from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy.dialects import postgresql

from app.ingestion.store import apply_fields, find_existing_article


def test_apply_fields_writes_columns_and_resets_fields_absent_from_the_write() -> None:
    document = SimpleNamespace(summary="Old card.", key_points=["Old point."], why_it_matters="Old.")
    event_types = ["guide"]
    apply_fields(
        document,
        {
            "ingestion_status": "quarantined",
            "extraction_status": "title_only",
            "event_types": event_types,
            "organization": "Ignored: not a document field.",
        },
    )

    assert document.ingestion_status == "quarantined"
    assert document.extraction_status == "title_only"
    assert document.event_types == ["guide"]
    assert document.event_types is not event_types
    assert document.summary is None
    assert document.why_it_matters is None
    assert document.key_points == []
    assert not hasattr(document, "organization")


def test_existing_document_lookup_uses_url_without_duplicate_column():
    db = MagicMock()
    db.scalar.return_value = None

    find_existing_article(
        db,
        SimpleNamespace(
            source_slug="example",
            raw_url="https://example.com/article/",
            title="Agent article",
            content_hash="hash",
        ),
    )

    statement = db.scalar.call_args.args[0]
    sql = str(
        statement.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": True},
        )
    )
    assert "documents.url IN ('https://example.com/article', 'https://example.com/article/')" in sql
    assert "canonical_url" not in sql
