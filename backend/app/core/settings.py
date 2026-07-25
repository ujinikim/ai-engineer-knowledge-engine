from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    openai_api_key: str = ""
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/knowledge_engine"
    embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    chat_model: str = "gpt-4.1-mini"
    max_completion_tokens: int = 300
    max_context_tokens: int = 3500
    top_k: int = 6
    cors_origins: list[str] = ["http://localhost:5173"]


settings = Settings()
