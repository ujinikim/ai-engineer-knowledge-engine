import json
from types import SimpleNamespace

from app.ingestion.taxonomy_classifier import TaxonomyClassifier

ARGS = {
    "title": "Agent eval guide",
    "raw_text": "Agent eval guide\n\nThis guide explains how to evaluate agents step by step.",
    "default_topic": "agentic-generative-ai",
    "default_event_types": ["analysis"],
}


class ScriptedClient:
    """Returns one scripted JSON reply per model call and records which schema was asked."""

    def __init__(self, replies) -> None:
        self.replies = list(replies)
        self.schemas: list[str] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.schemas.append(kwargs["response_format"]["json_schema"]["name"])
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SimpleNamespace(
            usage=None,
            choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(reply)))],
        )


def classifier(replies) -> TaxonomyClassifier:
    service = TaxonomyClassifier.__new__(TaxonomyClassifier)
    service.model = "gpt-test"
    service.usage = None
    service.client = ScriptedClient(replies) if replies is not None else None
    return service


def test_theme_then_category_then_event() -> None:
    service = classifier(
        [
            {"main_theme": "Measuring whether agents complete tasks"},
            {"primary_topic": "safety-evaluation-governance", "classification_reason": "Measures agents."},
            {"event_type": "guide", "event_reason": "Step-by-step instructions."},
        ]
    )

    result = service.classify(**ARGS)

    assert service.client.schemas == ["article_main_theme", "article_category", "article_event"]
    assert result.primary_topic == "safety-evaluation-governance"
    assert result.event_types == ["guide"]
    assert result.method == "gpt-test"
    assert result.main_theme == "Measuring whether agents complete tasks"


def test_invalid_category_falls_back_but_keeps_the_theme() -> None:
    service = classifier(
        [
            {"main_theme": "Measuring whether agents complete tasks"},
            {"primary_topic": "not-a-category", "classification_reason": "x"},
        ]
    )

    result = service.classify(**ARGS)

    assert result.method == "deterministic-keyword"
    assert result.main_theme == "Measuring whether agents complete tasks"
    assert result.category_reason == "Category gate returned an invalid structured result."


def test_failed_event_step_keeps_the_model_category() -> None:
    service = classifier(
        [
            {"main_theme": "Designing a RAG index"},
            {"primary_topic": "data-search-retrieval", "classification_reason": "Retrieval design."},
            {"event_type": "not-an-event", "event_reason": ""},
        ]
    )

    result = service.classify(**ARGS)

    assert result.primary_topic == "data-search-retrieval"
    assert result.event_reason == "Event gate failed; deterministic fallback used."


def test_model_error_and_missing_client_use_deterministic_rules() -> None:
    for service in (classifier([RuntimeError("boom")]), classifier(None)):
        result = service.classify(**ARGS)
        assert result.method == "deterministic-keyword"
        assert result.main_theme is None
        assert result.event_reason is None
