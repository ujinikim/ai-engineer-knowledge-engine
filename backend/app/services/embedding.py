from openai import OpenAI

from app.core.model_usage import ModelUsage
from app.core.settings import settings


class EmbeddingService:
    def __init__(self, usage: ModelUsage | None = None) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for embedding generation.")
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.usage = usage

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        if self.usage and response.usage:
            input_tokens = getattr(response.usage, "prompt_tokens", None)
            if input_tokens is None:
                input_tokens = response.usage.total_tokens
            self.usage.record_embedding(input_tokens)
        return [item.embedding for item in response.data]
