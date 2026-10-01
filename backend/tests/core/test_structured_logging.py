import asyncio
import json
import logging

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient, Response

from app.core.settings import Settings
from app.core.structured_logging import JsonLogFormatter
from app.main import create_app


def request(application: FastAPI, path: str, headers: dict[str, str] | None = None) -> Response:
    async def send() -> Response:
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://log-test") as client:
            return await client.get(path, headers=headers)

    return asyncio.run(send())


def json_log_lines(output: str) -> list[dict]:
    return [json.loads(line) for line in output.splitlines() if line.startswith("{")]


def test_formatter_redacts_sensitive_fields_and_values() -> None:
    record = logging.LogRecord(
        name="knowledge_engine.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="safe event",
        args=(),
        exc_info=None,
    )
    record.event = "redaction_test"
    record.structured_fields = {
        "api_key": "sk-field-secret123",
        "database_url": "postgresql://app:database-password@db.internal/app",
        "detail": (
            "Bearer bearer-secret and sk-value-secret123 and "
            "postgresql://user:password@db.internal/app"
        ),
        "prompt_tokens": 42,
    }

    payload = json.loads(JsonLogFormatter().format(record))
    serialized = json.dumps(payload)

    assert payload["api_key"] == "[REDACTED]"
    assert payload["database_url"] == "[REDACTED]"
    assert payload["prompt_tokens"] == 42
    assert "bearer-secret" not in serialized
    assert "value-secret" not in serialized
    assert "database-password" not in serialized
    assert "password@" not in serialized


def test_api_log_has_request_metadata_without_query_or_credentials(capsys) -> None:
    application = create_app(Settings(_env_file=None, app_environment="test"))

    response = request(
        application,
        "/health?api_key=sk-query-secret123",
        headers={
            "X-Request-ID": "review-request-123",
            "Authorization": "Bearer header-secret",
        },
    )
    events = json_log_lines(capsys.readouterr().out)
    request_event = next(event for event in events if event["event"] == "api_request_completed")

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "review-request-123"
    assert request_event == {
        "duration_ms": request_event["duration_ms"],
        "event": "api_request_completed",
        "level": "info",
        "logger": "knowledge_engine.api",
        "method": "GET",
        "path": "/health",
        "request_id": "review-request-123",
        "status_code": 200,
        "timestamp": request_event["timestamp"],
    }
    assert "query-secret" not in json.dumps(request_event)
    assert "header-secret" not in json.dumps(request_event)


def test_successful_liveness_probe_is_not_logged(capsys) -> None:
    application = create_app(Settings(_env_file=None, app_environment="test"))

    response = request(application, "/health/live")

    assert response.status_code == 200
    assert json_log_lines(capsys.readouterr().out) == []
