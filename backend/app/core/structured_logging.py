import json
import logging
import re
import sys
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any


_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_SENSITIVE_FIELDS = {
    "api_key",
    "authorization",
    "context",
    "cookie",
    "database_url",
    "openai_api_key",
    "password",
    "prompt",
    "raw_text",
    "secret",
    "source_text",
}
_VALUE_PATTERNS = (
    (re.compile(r"(?i)\bBearer\s+[^\s,;]+"), "Bearer [REDACTED]"),
    (re.compile(r"(?i)\bsk-[A-Za-z0-9_-]{8,}"), "[REDACTED]"),
    (
        re.compile(r"(?i)(postgres(?:ql)?(?:\+[a-z0-9_]+)?://[^:\s/@]+:)[^@\s]+@"),
        r"\1[REDACTED]@",
    ),
    (
        re.compile(r"(?i)\b(api[_-]?key|password|secret|access_token)=([^&\s]+)"),
        r"\1=[REDACTED]",
    ),
)


def _redact_string(value: str) -> str:
    redacted = value
    for pattern, replacement in _VALUE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def sanitize_log_value(value: Any, *, field_name: str = "") -> Any:
    normalized_field = field_name.strip().lower()
    if normalized_field in _SENSITIVE_FIELDS or normalized_field.endswith(
        ("_api_key", "_password", "_secret")
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            str(key): sanitize_log_value(item, field_name=str(key))
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set)):
        return [sanitize_log_value(item) for item in value]
    if isinstance(value, str):
        return _redact_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return _redact_string(str(value))


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname.lower(),
            "logger": record.name,
        }
        event = getattr(record, "event", None)
        if event:
            payload["event"] = sanitize_log_value(event)
        else:
            payload["message"] = sanitize_log_value(record.getMessage())

        fields = getattr(record, "structured_fields", {})
        if isinstance(fields, dict):
            payload.update(sanitize_log_value(fields))
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, separators=(",", ":"), sort_keys=True)


class DynamicStdoutHandler(logging.StreamHandler):
    """Write to the current stdout so test capture and container logs both work."""

    def emit(self, record: logging.LogRecord) -> None:
        self.stream = sys.stdout
        super().emit(record)


def configure_structured_logging(level: int = logging.INFO) -> logging.Logger:
    root = logging.getLogger("knowledge_engine")
    if not any(getattr(handler, "knowledge_engine_json", False) for handler in root.handlers):
        handler = DynamicStdoutHandler()
        handler.setFormatter(JsonLogFormatter())
        handler.knowledge_engine_json = True
        root.addHandler(handler)
    root.setLevel(level)
    root.propagate = False
    return root


def get_logger(name: str) -> logging.Logger:
    configure_structured_logging()
    return logging.getLogger(f"knowledge_engine.{name}")


def set_request_id(value: str) -> Token:
    return _request_id.set(value)


def reset_request_id(token: Token) -> None:
    _request_id.reset(token)


def log_event(
    logger: logging.Logger,
    event: str,
    *,
    level: int = logging.INFO,
    **fields: Any,
) -> None:
    current_request_id = _request_id.get()
    if current_request_id and "request_id" not in fields:
        fields["request_id"] = current_request_id
    logger.log(
        level,
        event,
        extra={"event": event, "structured_fields": fields},
    )
