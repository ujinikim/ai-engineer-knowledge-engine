from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url


ApplicationEnvironment = Literal["development", "test", "production"]
PLACEHOLDER_OPENAI_KEYS = {"", "replace_me", "changeme"}
LOCAL_DATABASE_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "postgres"}
LOCAL_CORS_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
RUNTIME_SECRETS_DIRECTORY = Path("/run/secrets")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        secrets_dir=RUNTIME_SECRETS_DIRECTORY if RUNTIME_SECRETS_DIRECTORY.is_dir() else None,
        extra="ignore",
    )

    app_environment: ApplicationEnvironment = "development"
    openai_api_key: str = ""
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_engine"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4.1-mini"
    max_completion_tokens: int = 500
    max_context_tokens: int = 3500
    top_k: int = 6
    cors_origins: list[str] = ["http://localhost:5173"]

    @property
    def is_production(self) -> bool:
        return self.app_environment == "production"

    @model_validator(mode="after")
    def validate_production_configuration(self) -> "Settings":
        if not self.is_production:
            return self

        problems: list[str] = []
        if self.openai_api_key.strip().lower() in PLACEHOLDER_OPENAI_KEYS:
            problems.append("OPENAI_API_KEY must be set to a non-placeholder value")

        try:
            database_url = make_url(self.database_url)
        except Exception:
            problems.append("DATABASE_URL must be a valid SQLAlchemy PostgreSQL URL")
        else:
            if not database_url.drivername.startswith("postgresql"):
                problems.append("DATABASE_URL must use PostgreSQL")
            if not database_url.host or database_url.host.lower() in LOCAL_DATABASE_HOSTS:
                problems.append("DATABASE_URL must point to a non-local database host")
            if not database_url.username or not database_url.password:
                problems.append("DATABASE_URL must include a database username and password")

        for origin in self.cors_origins:
            parsed_origin = urlsplit(origin)
            if "*" in origin:
                problems.append("CORS_ORIGINS cannot contain a wildcard")
            elif (
                parsed_origin.scheme != "https"
                or not parsed_origin.hostname
                or parsed_origin.hostname.lower() in LOCAL_CORS_HOSTS
                or parsed_origin.username is not None
                or parsed_origin.password is not None
                or parsed_origin.path
                or parsed_origin.query
                or parsed_origin.fragment
            ):
                problems.append(
                    f"CORS_ORIGINS entry {origin!r} must be an HTTPS origin without a path"
                )

        if problems:
            raise ValueError("Invalid production configuration: " + "; ".join(problems))

        return self


settings = Settings()
