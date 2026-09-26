from types import SimpleNamespace

from app.services.source_extraction import article_excerpt
from app.services.update_collector import UpdateCollectorService
from app.services.update_visibility import source_attribute, source_slugs_with


def test_source_attributes_come_from_configuration() -> None:
    assert source_attribute("github-changelog", "source_type") == "official-changelog"
    assert source_attribute("github-changelog", "tool") == "GitHub Copilot"
    assert source_attribute("retired-source", "tool") is None
    assert source_attribute("retired-source", "credibility_weight", 1.0) == 1.0
    assert source_slugs_with("tool", ["GitHub Copilot"]) == ["github-changelog"]
    assert "simon-agentic-engineering" in source_slugs_with("source_type", ["editorial-analysis"])


def test_excerpt_is_derived_from_body_after_title() -> None:
    assert article_excerpt("Title", "Title\n\nBody   text here.") == "Body text here."
    assert article_excerpt("Title only", "Title only") == "Title only"
    long_excerpt = article_excerpt("T", "T\n\n" + "word " * 200)
    assert long_excerpt == article_excerpt("T", "T\n\n" + "word " * 300)
    assert len(long_excerpt) <= 422
    assert long_excerpt.endswith("...")


def test_apply_fields_writes_columns_and_resets_fields_absent_from_the_write() -> None:
    document = SimpleNamespace(summary="Old card.", key_points=["Old point."], why_it_matters="Old.")
    event_types = ["guide"]
    UpdateCollectorService._apply_fields(
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
