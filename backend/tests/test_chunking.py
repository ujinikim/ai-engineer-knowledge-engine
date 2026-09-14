from app.services.chunking import ChunkingService


def test_large_unicode_block_chunks_remain_exact_source_substrings() -> None:
    service = ChunkingService()
    text = "Updates 🇬🇧 🤖 🌷 — agent tools and evaluations. " * 300

    chunks = service.chunk_text(text, max_tokens=80, overlap_tokens=12)

    assert len(chunks) > 1
    assert all(chunk.content in text for chunk in chunks)
    assert all("�" not in chunk.content for chunk in chunks)
    assert all(chunk.token_count <= 80 for chunk in chunks)


def test_large_block_overlap_does_not_prevent_progress() -> None:
    service = ChunkingService()
    text = "agent orchestration and evaluation " * 200

    chunks = service.chunk_text(text, max_tokens=20, overlap_tokens=20)

    assert len(chunks) > 1
    assert all(chunk.content in text for chunk in chunks)
    assert all(chunk.token_count <= 20 for chunk in chunks)
