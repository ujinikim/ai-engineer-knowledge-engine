import pytest

from app.schemas.ask import AskRequest
from app.schemas.search import SearchRequest


@pytest.mark.parametrize("request_type, query_field", [(SearchRequest, "query"), (AskRequest, "question")])
def test_source_names_are_normalized(request_type, query_field):
    request = request_type(**{query_field: "How do dependencies work?", "source_names": ["FastAPI"]})

    assert request.source_names == ["fastapi"]


@pytest.mark.parametrize("request_type, query_field", [(SearchRequest, "query"), (AskRequest, "question")])
def test_empty_source_names_mean_no_filter(request_type, query_field):
    request = request_type(**{query_field: "How do dependencies work?", "source_names": []})

    assert request.source_names is None


@pytest.mark.parametrize("request_type, query_field", [(SearchRequest, "query"), (AskRequest, "question")])
def test_dynamic_source_names_are_supported(request_type, query_field):
    request = request_type(**{query_field: "What changed?", "source_names": ["New-Tool"]})

    assert request.source_names == ["new-tool"]


@pytest.mark.parametrize("request_type, query_field", [(SearchRequest, "query"), (AskRequest, "question")])
def test_taxonomy_filters_are_normalized(request_type, query_field):
    request = request_type(
        **{
            query_field: "What changed?",
            "categories": ["Inference-Serving"],
            "event_types": ["Library-Release"],
            "source_types": ["Official-Release"],
        }
    )

    assert request.categories == ["inference-serving"]
    assert request.event_types == ["library-release"]
    assert request.source_types == ["official-release"]
