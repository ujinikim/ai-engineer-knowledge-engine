import pytest
from pydantic import ValidationError

from app.core.settings import Settings
from app.main import LOCAL_DEVELOPMENT_ORIGINS, allowed_cors_origins


VALID_PRODUCTION_SETTINGS = {
    "app_environment": "production",
    "openai_api_key": "ci-validation-key",
    "database_url": "postgresql+psycopg://app:secret@database.internal:5432/knowledge_engine",
    "cors_origins": ["https://example.cloudfront.net"],
}


def build_settings(**overrides: object) -> Settings:
    values = {**VALID_PRODUCTION_SETTINGS, **overrides}
    return Settings(_env_file=None, **values)


def test_development_defaults_remain_available() -> None:
    settings = Settings(_env_file=None, app_environment="development")

    assert settings.app_environment == "development"
    assert not settings.is_production
    assert LOCAL_DEVELOPMENT_ORIGINS.issubset(allowed_cors_origins(settings))


def test_valid_production_configuration_uses_only_explicit_cors_origins() -> None:
    settings = build_settings()

    assert settings.is_production
    assert allowed_cors_origins(settings) == ["https://example.cloudfront.net"]


@pytest.mark.parametrize("openai_api_key", ["", "replace_me", "changeme"])
def test_production_rejects_missing_or_placeholder_openai_key(openai_api_key: str) -> None:
    with pytest.raises(ValidationError, match="OPENAI_API_KEY must be set"):
        build_settings(openai_api_key=openai_api_key)


@pytest.mark.parametrize(
    "database_url",
    [
        "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_engine",
        "sqlite:///knowledge_engine.db",
        "postgresql+psycopg://database.internal:5432/knowledge_engine",
    ],
)
def test_production_rejects_unsafe_database_url(database_url: str) -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        build_settings(database_url=database_url)


@pytest.mark.parametrize(
    "cors_origins",
    [
        [],
        ["*"],
        ["http://app.example.com"],
        ["https://localhost:5173"],
        ["https://app.example.com/api"],
        ["https://user:password@app.example.com"],
        ["https://*.example.com"],
    ],
)
def test_production_rejects_unsafe_cors_origins(cors_origins: list[str]) -> None:
    with pytest.raises(ValidationError, match="CORS_ORIGINS"):
        build_settings(cors_origins=cors_origins)
