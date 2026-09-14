from dataclasses import dataclass

import tiktoken


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str
    token_count: int


class ChunkingService:
    def __init__(self, encoding_name: str = "cl100k_base") -> None:
        self.encoding = tiktoken.get_encoding(encoding_name)

    def chunk_text(
        self,
        text: str,
        max_tokens: int = 850,
        overlap_tokens: int = 120,
    ) -> list[TextChunk]:
        blocks = [block.strip() for block in text.split("\n\n") if block.strip()]
        chunks: list[TextChunk] = []
        current_blocks: list[str] = []
        current_tokens = 0
        index = 0

        for block in blocks:
            block_tokens = self._count_tokens(block)
            if current_blocks and current_tokens + block_tokens > max_tokens:
                content = "\n\n".join(current_blocks).strip()
                chunks.append(TextChunk(index=index, content=content, token_count=current_tokens))
                index += 1
                current_blocks = self._overlap_blocks(current_blocks, overlap_tokens)
                current_tokens = self._count_tokens("\n\n".join(current_blocks))

            if block_tokens > max_tokens:
                for piece in self._split_large_block(block, max_tokens, overlap_tokens):
                    if current_blocks:
                        content = "\n\n".join(current_blocks).strip()
                        chunks.append(TextChunk(index=index, content=content, token_count=current_tokens))
                        index += 1
                        current_blocks = []
                        current_tokens = 0
                    chunks.append(
                        TextChunk(index=index, content=piece, token_count=self._count_tokens(piece))
                    )
                    index += 1
                continue

            current_blocks.append(block)
            current_tokens += block_tokens

        if current_blocks:
            content = "\n\n".join(current_blocks).strip()
            chunks.append(TextChunk(index=index, content=content, token_count=current_tokens))

        return chunks

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _overlap_blocks(self, blocks: list[str], overlap_tokens: int) -> list[str]:
        selected: list[str] = []
        total = 0
        for block in reversed(blocks):
            block_tokens = self._count_tokens(block)
            if selected and total + block_tokens > overlap_tokens:
                break
            selected.insert(0, block)
            total += block_tokens
        return selected

    def _split_large_block(
        self,
        block: str,
        max_tokens: int,
        overlap_tokens: int,
    ) -> list[str]:
        pieces: list[str] = []
        start = 0
        safe_overlap = max(0, min(overlap_tokens, max_tokens - 1))
        while start < len(block):
            end = self._largest_character_end(block, start, max_tokens)
            piece = block[start:end].strip()
            if piece:
                pieces.append(piece)
            if end == len(block):
                break
            start = self._overlap_character_start(block, start, end, safe_overlap)
        return pieces

    def _largest_character_end(self, text: str, start: int, max_tokens: int) -> int:
        """Find a token-bounded slice without decoding partial UTF-8 token bytes."""
        low = start + 1
        high = len(text)
        best = low
        while low <= high:
            candidate = (low + high) // 2
            if self._count_tokens(text[start:candidate]) <= max_tokens:
                best = candidate
                low = candidate + 1
            else:
                high = candidate - 1
        return best

    def _overlap_character_start(
        self,
        text: str,
        previous_start: int,
        end: int,
        overlap_tokens: int,
    ) -> int:
        if overlap_tokens <= 0:
            return end
        low = previous_start + 1
        high = end
        best = end
        while low <= high:
            candidate = (low + high) // 2
            if self._count_tokens(text[candidate:end]) <= overlap_tokens:
                best = candidate
                high = candidate - 1
            else:
                low = candidate + 1
        return best
