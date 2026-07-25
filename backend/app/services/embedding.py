from openai import OpenAI

from app.core.settings import settings


class EmbeddingService:
    def __init__(self) -> None:
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for embedding generation.")
        self.client = OpenAI(api_key=settings.openai_api_key)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self.client.embeddings.create(
            model=settings.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]
