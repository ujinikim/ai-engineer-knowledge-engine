import re
import time

import tiktoken
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.settings import settings
from app.core.model_usage import estimate_chat_cost_usd
from app.core.structured_logging import get_logger, log_event
from app.schemas.ask import AnswerMetrics, AskRequest, AskResponse, Citation
from app.schemas.search import SearchRequest
from app.services.retriever import RetrieverService


logger = get_logger("answer")


class AnswerService:
    def __init__(self, db: Session) -> None:
        self.db = db
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for answer generation.")
        self.client = OpenAI(api_key=settings.openai_api_key)

    def answer(self, request: AskRequest) -> AskResponse:
        started = time.perf_counter()
        retrieval = RetrieverService(self.db).search(
            SearchRequest(
                query=request.question,
                top_k=request.top_k,
                source_names=request.source_names,
                tools=request.tools,
                categories=request.categories,
                event_types=request.event_types,
                source_types=request.source_types,
                maturities=request.maturities,
                include_contextual=request.include_contextual,
                collection=request.collection,
                published_after=request.published_after,
                published_before=request.published_before,
                search_mode=request.search_mode,
                retrieval_strategy=request.retrieval_strategy,
            )
        )

        warning = self._retrieval_warning(retrieval.results, request.min_similarity)
        if warning:
            log_event(
                logger,
                "answer_generation_skipped",
                reason="weak_retrieval",
                retrieved_chunks=len(retrieval.results),
                total_ms=self._elapsed_ms(started),
            )
            return AskResponse(
                answer=warning,
                citations=[],
                retrieved_chunks=retrieval.results,
                context_chunks=[],
                metrics=AnswerMetrics(
                    embedding_ms=retrieval.metrics.embedding_ms,
                    retrieval_ms=retrieval.metrics.retrieval_ms,
                    total_ms=self._elapsed_ms(started),
                ),
                retrieval_warning=warning,
            )

        context_chunks = self._context_chunks(
            retrieval.results,
            max_tokens=min(request.max_context_tokens, settings.max_context_tokens),
            prefer_document_diversity=self._requires_document_diversity(request),
        )
        context = self._build_context(context_chunks)
        llm_started = time.perf_counter()
        response = self.client.chat.completions.create(
            model=settings.chat_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze dated articles about LLM agent engineering "
                        "using only the provided context, never prior knowledge or memory. "
                        "Cite factual claims with bracketed citation IDs like [1], and use a "
                        "citation only when that exact passage directly supports the claim. "
                        "Treat publication dates as part of the evidence. Never claim something "
                        "is recent unless its date is present in context. Never invent, estimate, "
                        "or infer a requested number from a related metric. If the question asks "
                        "for an exact metric and the context does not explicitly name that metric, "
                        "state that the exact metric is not provided. For comparisons, address "
                        "each named subject separately and do not substitute a broadly related "
                        "article for the requested subject. If evidence is insufficient, lead "
                        "with that limitation and state what evidence is missing instead of "
                        "filling the answer with adjacent facts. Unless the user explicitly asks "
                        "for exhaustive detail or code, answer directly in no more than 200 words "
                        "and do not include code samples. Add citations as you make each supported "
                        "claim rather than waiting until the end. "
                        "For period summaries, output exactly three bullets with no introduction "
                        "or conclusion. Each bullet must cover one distinct update in at most 30 "
                        "words and end with its citation. If fewer than three updates are supported, "
                        "return only the supported bullets and then state what evidence is missing. "
                        "Do not force the three-bullet format for other question types."
                    ),
                },
                {
                    "role": "user",
                    "content": f"Question:\n{request.question}\n\nContext:\n{context}",
                },
            ],
            temperature=0.2,
            max_completion_tokens=min(request.max_completion_tokens, settings.max_completion_tokens),
        )
        llm_ms = self._elapsed_ms(llm_started)
        answer = response.choices[0].message.content or ""
        generation_warnings = self._generation_warnings(
            response.choices[0].finish_reason
        )

        usage = response.usage
        context_tokens = self._count_tokens(context)
        completion_tokens = usage.completion_tokens if usage else self._count_tokens(answer)
        prompt_tokens = usage.prompt_tokens if usage else context_tokens
        citation_ids, citation_warnings = self._citation_ids(answer, len(context_chunks))

        estimated_cost_usd = self._estimate_cost(prompt_tokens, completion_tokens)
        result = AskResponse(
            answer=answer,
            citations=[
                Citation(
                    id=index,
                    title=chunk.document_title,
                    url=chunk.url,
                    chunk_id=chunk.chunk_id,
                )
                for index, chunk in enumerate(context_chunks, start=1)
                if index in citation_ids
            ],
            retrieved_chunks=retrieval.results,
            context_chunks=context_chunks,
            metrics=AnswerMetrics(
                embedding_ms=retrieval.metrics.embedding_ms,
                retrieval_ms=retrieval.metrics.retrieval_ms,
                llm_ms=llm_ms,
                total_ms=self._elapsed_ms(started),
                context_tokens=context_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=estimated_cost_usd or 0,
            ),
            retrieval_warning=None,
            citation_warnings=citation_warnings,
            generation_warnings=generation_warnings,
        )
        log_event(
            logger,
            "answer_generated",
            model=settings.chat_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            estimated_model_cost_usd=estimated_cost_usd,
            retrieved_chunks=len(retrieval.results),
            context_chunks=len(context_chunks),
            citations=len(result.citations),
            total_ms=result.metrics.total_ms,
        )
        return result

    def _retrieval_warning(self, chunks, min_similarity: float) -> str | None:
        if not chunks:
            return (
                "I could not retrieve any matching article passages. "
                "Try broadening the source filters or lowering the similarity threshold."
            )

        top_score = chunks[0].similarity
        if top_score < min_similarity:
            return (
                "The retrieved articles look weak for this question. "
                f"The top similarity score was {top_score:.3f}, below the configured "
                f"threshold of {min_similarity:.3f}. Try lowering the threshold, increasing "
                "top-k, changing filters, or collecting more relevant articles."
            )

        return None

    def _context_chunks(
        self,
        chunks,
        max_tokens: int,
        *,
        prefer_document_diversity: bool = False,
    ):
        ordered_chunks = (
            self._document_diverse_order(chunks)
            if prefer_document_diversity
            else list(chunks)
        )
        selected = []
        total_tokens = 0
        for chunk in ordered_chunks:
            block = self._context_block(chunk, len(selected) + 1)
            if selected:
                block = "\n\n---\n\n" + block
            chunk_tokens = self._count_tokens(block)
            if selected and total_tokens + chunk_tokens > max_tokens:
                continue
            selected.append(chunk)
            total_tokens += chunk_tokens
        return selected

    def _document_diverse_order(self, chunks):
        first_by_document = []
        repeated_documents = []
        seen: set[str] = set()
        for chunk in chunks:
            identity = self._context_document_identity(chunk)
            if identity in seen:
                repeated_documents.append(chunk)
                continue
            seen.add(identity)
            first_by_document.append(chunk)
        return [*first_by_document, *repeated_documents]

    def _context_document_identity(self, chunk) -> str:
        url = str(getattr(chunk, "url", "") or "").strip().lower().rstrip("/")
        if url:
            return url
        return str(getattr(chunk, "document_id", ""))

    def _requires_document_diversity(self, request: AskRequest) -> bool:
        if request.retrieval_strategy == "source_balanced":
            return True
        if request.source_names and len(request.source_names) > 1:
            return True
        return bool(
            re.search(
                r"\b(?:compare|comparison|versus|vs\.?|across)\b",
                request.question,
                flags=re.IGNORECASE,
            )
        )

    def _build_context(self, chunks) -> str:
        parts = []
        for index, chunk in enumerate(chunks, start=1):
            parts.append(self._context_block(chunk, index))
        return "\n\n---\n\n".join(parts)

    def _context_block(self, chunk, index: int) -> str:
        return "\n".join(
            [
                f"[{index}] {chunk.document_title}",
                f"Source: {chunk.source_name}",
                f"Published: {chunk.published_at.isoformat() if chunk.published_at else 'unknown'}",
                f"Tool: {chunk.tool or 'unknown'}",
                f"URL: {chunk.url}",
                chunk.content,
            ]
        )

    def _citation_ids(self, answer: str, context_count: int) -> tuple[set[int], list[str]]:
        referenced = [int(value) for value in re.findall(r"\[(\d+)\]", answer)]
        valid = {value for value in referenced if 1 <= value <= context_count}
        invalid = sorted({value for value in referenced if value < 1 or value > context_count})
        warnings = [f"Answer referenced unknown citation [{value}]." for value in invalid]
        if answer.strip() and not valid and not self._is_insufficient_evidence_answer(answer):
            warnings.append("Answer did not reference any retrieved evidence.")
        return valid, warnings

    def _is_insufficient_evidence_answer(self, answer: str) -> bool:
        normalized = " ".join(answer.lower().split())
        indicators = (
            "context does not include",
            "context does not provide",
            "evidence is missing",
            "insufficient evidence",
            "not provided in the context",
            "no information about",
            "cannot be determined from the context",
        )
        return any(indicator in normalized for indicator in indicators)

    def _generation_warnings(self, finish_reason: str | None) -> list[str]:
        if finish_reason == "length":
            return [
                "Answer reached the completion-token limit and may be truncated."
            ]
        return []

    def _count_tokens(self, text: str) -> int:
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))

    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float | None:
        return estimate_chat_cost_usd(
            settings.chat_model,
            prompt_tokens,
            completion_tokens,
        )

    def _elapsed_ms(self, started: float) -> int:
        return int((time.perf_counter() - started) * 1000)
