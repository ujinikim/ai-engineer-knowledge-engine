import asyncio
import hashlib
import sys
import uuid
from pathlib import Path

import yaml
from sqlalchemy import delete, select

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.db.models import Chunk, Document
from app.db.session import SessionLocal
from app.services.chunking import ChunkingService
from app.services.embedding import EmbeddingService
from app.services.ingestion import FetchedDocument, IngestionService


SOURCE_FILE = Path(__file__).resolve().parents[1] / "data" / "sources.yml"
BATCH_SIZE = 32


async def main() -> None:
    sources = load_sources()
    ingestion = IngestionService()
    chunker = ChunkingService()
    embedder = EmbeddingService()

    with SessionLocal() as db:
        for source in sources:
            for url in source["urls"]:
                print(f"Fetching {url}")
                fetched = await ingestion.fetch_document(
                    source_name=source["source_name"],
                    source_type=source.get("source_type", "docs"),
                    url=url,
                )
                document = upsert_document(db, fetched)
                chunks = chunker.chunk_text(fetched.raw_text)
                db.execute(delete(Chunk).where(Chunk.document_id == document.id))

                for start in range(0, len(chunks), BATCH_SIZE):
                    batch = chunks[start : start + BATCH_SIZE]
                    embeddings = embedder.embed_texts([chunk.content for chunk in batch])
                    for chunk, embedding in zip(batch, embeddings, strict=True):
                        db.add(
                            Chunk(
                                id=uuid.uuid4(),
                                document_id=document.id,
                                chunk_index=chunk.index,
                                content=chunk.content,
                                embedding=embedding,
                                token_count=chunk.token_count,
                                content_hash=hash_text(chunk.content),
                                chunk_metadata={},
                            )
                        )
                db.commit()
                print(f"Stored {len(chunks)} chunks for {fetched.title}")


def load_sources() -> list[dict]:
    with SOURCE_FILE.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)
    return data["sources"]


def upsert_document(db, fetched: FetchedDocument) -> Document:
    existing = db.execute(select(Document).where(Document.url == fetched.url)).scalar_one_or_none()
    if existing:
        existing.source_name = fetched.source_name
        existing.source_type = fetched.source_type
        existing.title = fetched.title[:500]
        existing.raw_text = fetched.raw_text
        existing.content_hash = fetched.content_hash
        return existing

    document = Document(
        id=uuid.uuid4(),
        source_name=fetched.source_name,
        source_type=fetched.source_type,
        title=fetched.title[:500],
        url=fetched.url,
        canonical_url=fetched.url,
        raw_text=fetched.raw_text,
        content_hash=fetched.content_hash,
        doc_metadata={},
    )
    db.add(document)
    db.flush()
    return document


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


if __name__ == "__main__":
    asyncio.run(main())
