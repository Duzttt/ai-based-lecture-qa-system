import time
from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.runtime_embedding import load_runtime_embedding_settings
from app.services.runtime_llm import load_runtime_llm_settings
from app.services.vector_store import VectorStore, VectorStoreError

TraceStage = Dict[str, Any]
TracePayload = Dict[str, Any]


class LocalRAGError(Exception):
    pass


def retrieve_with_faiss(
    query: str,
    top_k: int = 5,
    source_filter: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    from app.services.local_rag import LocalRAGError as RuntimeLocalRAGError
    from app.services.local_rag import retrieve_with_faiss as runtime_retrieve

    try:
        return runtime_retrieve(query=query, top_k=top_k, source_filter=source_filter)
    except RuntimeLocalRAGError as exc:
        raise LocalRAGError(str(exc)) from exc


def build_context_from_sources(sources: List[Dict[str, Any]]) -> str:
    from app.services.local_rag import build_context_from_sources as runtime_build_context

    return runtime_build_context(sources)


def generate(
    query: str,
    context: str,
    timeout_seconds: int = 60,
) -> Any:
    from app.services.local_rag import LocalRAGError as RuntimeLocalRAGError
    from app.services.local_rag import generate as runtime_generate

    try:
        return runtime_generate(
            query=query,
            context=context,
            timeout_seconds=timeout_seconds,
        )
    except RuntimeLocalRAGError as exc:
        raise LocalRAGError(str(exc)) from exc


def _duration_ms(started_at: float) -> int:
    return int((time.perf_counter() - started_at) * 1000)


def _new_stage(
    stage_id: str,
    title: str,
    status: str,
    duration_ms: int,
    summary: str,
    details: Optional[Dict[str, Any]] = None,
    technical: Optional[Dict[str, Any]] = None,
    results: Optional[List[Dict[str, Any]]] = None,
    error: Optional[str] = None,
) -> TraceStage:
    stage: TraceStage = {
        "id": stage_id,
        "title": title,
        "status": status,
        "duration_ms": max(duration_ms, 0),
        "summary": summary,
    }
    if details is not None:
        stage["details"] = details
    if technical is not None:
        stage["technical"] = technical
    if results is not None:
        stage["results"] = results
    if error:
        stage["error"] = error
    return stage


def _clip_text(text: Any, limit: int = 320) -> str:
    value = str(text or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 1].rstrip() + "..."


def _normalize_source_filter(source_filter: Any) -> Optional[List[str]]:
    if source_filter is None:
        return None
    if isinstance(source_filter, str):
        normalized = source_filter.strip()
        return [normalized] if normalized else None
    if isinstance(source_filter, list):
        values = [str(item).strip() for item in source_filter if str(item).strip()]
        return values or None
    return None


def _source_matches(source: Any, source_filter: Optional[List[str]]) -> bool:
    if not source_filter:
        return True
    normalized_source = str(source or "").lower().strip()
    for item in source_filter:
        normalized_filter = str(item).lower().strip()
        if (
            normalized_source == normalized_filter
            or normalized_source.startswith(normalized_filter)
            or normalized_filter in normalized_source
        ):
            return True
    return False


def _score_from_distance(distance: Any, max_distance: float) -> float:
    try:
        numeric_distance = float(distance)
    except (TypeError, ValueError):
        numeric_distance = max_distance
    return round(max(0.0, 1.0 - (numeric_distance / max_distance)), 3)


def _format_retrieved_chunks(sources: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    distances = [float(item.get("distance", 0) or 0) for item in sources]
    max_distance = max(distances) if distances else 1.0
    max_distance = max(max_distance, 0.001)

    chunks: List[Dict[str, Any]] = []
    for item in sources:
        text = str(item.get("text") or "")
        distance = item.get("distance", 0)
        score = item.get("score")
        if score is None:
            score = _score_from_distance(distance, max_distance)
        chunks.append(
            {
                "text": text,
                "preview": _clip_text(text, 160),
                "score": round(float(score or 0), 3),
                "distance": round(float(distance or 0), 4),
                "source": str(item.get("source") or "unknown"),
                "page": item.get("page"),
            }
        )
    return chunks


def _build_bm25_stage(
    query: str,
    chunks: List[Dict[str, Any]],
    top_k: int,
    source_filter: Optional[List[str]],
) -> TraceStage:
    started_at = time.perf_counter()
    try:
        from retrieval.bm25_index import BM25Index

        documents: List[Dict[str, str]] = []
        chunk_by_id: Dict[str, Dict[str, Any]] = {}
        for index, chunk in enumerate(chunks):
            if not isinstance(chunk, dict):
                continue
            if not _source_matches(chunk.get("source"), source_filter):
                continue
            text = str(chunk.get("text") or "")
            if not text.strip():
                continue
            doc_id = f"chunk_{index}"
            documents.append({"id": doc_id, "text": text})
            chunk_by_id[doc_id] = chunk

        if not documents:
            return _new_stage(
                "bm25_retrieval",
                "BM25 Retrieval",
                "skipped",
                _duration_ms(started_at),
                "BM25 retrieval was skipped because no indexed text matched the selected sources.",
                technical={"candidate_count": 0},
                results=[],
            )

        bm25_index = BM25Index(documents)
        raw_results = bm25_index.search(query, top_k=top_k)
        results = []
        for rank, item in enumerate(raw_results, start=1):
            doc_id, score = item
            chunk = chunk_by_id.get(doc_id, {})
            results.append(
                {
                    "rank": rank,
                    "id": doc_id,
                    "score": round(float(score), 4),
                    "source": str(chunk.get("source") or "unknown"),
                    "page": chunk.get("page"),
                    "preview": _clip_text(chunk.get("text"), 160),
                }
            )

        return _new_stage(
            "bm25_retrieval",
            "BM25 Retrieval",
            "completed",
            _duration_ms(started_at),
            "Keyword retrieval finds chunks that share important words with the question.",
            technical={"candidate_count": len(documents), "top_k": top_k},
            results=results,
        )
    except Exception as exc:  # noqa: BLE001
        return _new_stage(
            "bm25_retrieval",
            "BM25 Retrieval",
            "skipped",
            _duration_ms(started_at),
            "BM25 retrieval was skipped because the keyword index could not be built.",
            technical={"reason": str(exc)},
            results=[],
        )


def _extract_answer(generation_result: Any) -> str:
    if isinstance(generation_result, tuple):
        return str(generation_result[0] or "")
    return str(generation_result or "")


def build_rag_demo_trace(
    query: str,
    source_filter: Any = None,
    top_k: int = 5,
    include_answer: bool = True,
) -> TracePayload:
    normalized_query = str(query or "").strip()
    normalized_sources = _normalize_source_filter(source_filter)
    bounded_top_k = min(max(int(top_k or 5), 1), 10)
    trace_id = f"trace_{int(time.time() * 1000)}"
    total_started_at = time.perf_counter()
    stages: List[TraceStage] = []
    retrieved_sources: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []
    context = ""
    answer = ""

    stages.append(
        _new_stage(
            "user_question",
            "User Question",
            "completed",
            0,
            "The demo starts from the user question and optional source filter.",
            details={"query": normalized_query, "sources": normalized_sources or []},
        )
    )

    query_started_at = time.perf_counter()
    tokens = normalized_query.lower().split()
    stages.append(
        _new_stage(
            "query_processing",
            "Query Processing",
            "completed",
            _duration_ms(query_started_at),
            "The question is normalized and split into searchable terms.",
            details={"processed_query": normalized_query.lower(), "tokens": tokens},
            technical={"token_count": len(tokens)},
        )
    )

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )
        chunks = vector_store.chunks if isinstance(vector_store.chunks, list) else []
        if not chunks:
            stages.append(
                _new_stage(
                    "embedding_generation",
                    "Embedding",
                    "failed",
                    0,
                    "No indexed document chunks are available. Upload and index PDFs before running the demo.",
                    error="No indexed chunks found",
                )
            )
            return {
                "trace_id": trace_id,
                "query": normalized_query,
                "stages": stages,
                "retrieved_chunks": [],
                "context_preview": "",
                "answer": "",
                "total_duration_ms": _duration_ms(total_started_at),
            }

        embedding_started_at = time.perf_counter()
        embedding_service = EmbeddingService(model_name=rt["model_id"])
        query_embedding = embedding_service.embed_query(normalized_query)
        stages.append(
            _new_stage(
                "embedding_generation",
                "Embedding",
                "completed",
                _duration_ms(embedding_started_at),
                "The question is converted into a vector so semantic matches can be found.",
                details={"model": rt["model_id"], "dimension": len(query_embedding)},
                technical={"embedding_dim": rt["embedding_dim"]},
            )
        )
    except (EmbeddingError, VectorStoreError, LocalRAGError, ValueError) as exc:
        stages.append(
            _new_stage(
                "embedding_generation",
                "Embedding",
                "failed",
                0,
                "The system could not generate the query embedding.",
                error=str(exc),
            )
        )
        return {
            "trace_id": trace_id,
            "query": normalized_query,
            "stages": stages,
            "retrieved_chunks": [],
            "context_preview": "",
            "answer": "",
            "total_duration_ms": _duration_ms(total_started_at),
        }

    stages.append(
        _build_bm25_stage(
            query=normalized_query,
            chunks=chunks,
            top_k=bounded_top_k,
            source_filter=normalized_sources,
        )
    )

    dense_started_at = time.perf_counter()
    search_k = bounded_top_k * 10 if normalized_sources else bounded_top_k
    dense_results = vector_store.search_with_metadata(query_embedding, top_k=search_k)
    if normalized_sources:
        dense_results = [
            item
            for item in dense_results
            if _source_matches(item.get("source"), normalized_sources)
        ][:bounded_top_k]
    distances = [float(item.get("distance", 0) or 0) for item in dense_results]
    max_distance = max(max(distances) if distances else 1.0, 0.001)
    stages.append(
        _new_stage(
            "dense_retrieval",
            "Dense Retrieval",
            "completed",
            _duration_ms(dense_started_at),
            "Vector retrieval finds chunks that are semantically close to the question.",
            technical={"top_k": bounded_top_k, "searched_k": search_k},
            results=[
                {
                    "rank": rank,
                    "source": str(item.get("source") or "unknown"),
                    "page": item.get("page"),
                    "score": _score_from_distance(item.get("distance"), max_distance),
                    "distance": round(float(item.get("distance", 0) or 0), 4),
                    "preview": _clip_text(item.get("text"), 160),
                }
                for rank, item in enumerate(dense_results[:bounded_top_k], start=1)
            ],
        )
    )

    hybrid_started_at = time.perf_counter()
    try:
        retrieved_sources = retrieve_with_faiss(
            query=normalized_query,
            top_k=bounded_top_k,
            source_filter=normalized_sources,
        )
        retrieved_chunks = _format_retrieved_chunks(retrieved_sources)
        stages.append(
            _new_stage(
                "hybrid_ranking",
                "Hybrid Ranking",
                "completed",
                _duration_ms(hybrid_started_at),
                "The system combines keyword and semantic signals to choose the strongest evidence.",
                technical={"top_k": bounded_top_k, "source_filter": normalized_sources or []},
                results=[
                    {
                        "rank": rank,
                        "source": chunk["source"],
                        "page": chunk["page"],
                        "score": chunk["score"],
                        "distance": chunk["distance"],
                        "preview": chunk["preview"],
                    }
                    for rank, chunk in enumerate(retrieved_chunks, start=1)
                ],
            )
        )
    except LocalRAGError as exc:
        stages.append(
            _new_stage(
                "hybrid_ranking",
                "Hybrid Ranking",
                "failed",
                _duration_ms(hybrid_started_at),
                "Hybrid retrieval could not return evidence for this question.",
                error=str(exc),
            )
        )
        return {
            "trace_id": trace_id,
            "query": normalized_query,
            "stages": stages,
            "retrieved_chunks": [],
            "context_preview": "",
            "answer": "",
            "total_duration_ms": _duration_ms(total_started_at),
        }

    context_started_at = time.perf_counter()
    context = build_context_from_sources(retrieved_sources)
    context_status = "completed" if context.strip() else "failed"
    context_summary = (
        "The selected chunks are formatted into a context block for the language model."
        if context.strip()
        else "No usable context was built from the retrieved chunks."
    )
    stages.append(
        _new_stage(
            "context_building",
            "Context Building",
            context_status,
            _duration_ms(context_started_at),
            context_summary,
            details={"context_preview": _clip_text(context, 500)},
            technical={"context_length": len(context), "chunks_used": len(retrieved_sources)},
        )
    )

    if include_answer and context.strip():
        llm_started_at = time.perf_counter()
        runtime_llm = load_runtime_llm_settings()
        try:
            generation_result = generate(
                query=normalized_query,
                context=context,
                timeout_seconds=20,
            )
            answer = _extract_answer(generation_result)
            stages.append(
                _new_stage(
                    "llm_generation",
                    "LLM Generation",
                    "completed",
                    _duration_ms(llm_started_at),
                    "The language model writes an answer grounded in the retrieved context.",
                    details={"provider": runtime_llm["provider"], "model": runtime_llm["model"]},
                    technical={"answer_length": len(answer)},
                )
            )
        except requests.exceptions.Timeout as exc:
            stages.append(
                _new_stage(
                    "llm_generation",
                    "LLM Generation",
                    "failed",
                    _duration_ms(llm_started_at),
                    "LLM generation timed out after retrieval and context building completed.",
                    details={"provider": runtime_llm["provider"], "model": runtime_llm["model"]},
                    error=str(exc),
                )
            )
        except (requests.exceptions.RequestException, LocalRAGError, ValueError) as exc:
            stages.append(
                _new_stage(
                    "llm_generation",
                    "LLM Generation",
                    "failed",
                    _duration_ms(llm_started_at),
                    "LLM generation failed after retrieval and context building completed.",
                    details={"provider": runtime_llm["provider"], "model": runtime_llm["model"]},
                    error=str(exc),
                )
            )
    else:
        stages.append(
            _new_stage(
                "llm_generation",
                "LLM Generation",
                "skipped",
                0,
                "LLM generation was skipped for this trace request.",
                technical={"include_answer": include_answer, "has_context": bool(context.strip())},
            )
        )

    final_status = "completed" if answer else "skipped"
    final_summary = (
        "The final answer is ready and can be shown with the supporting evidence."
        if answer
        else "No final answer was produced for this trace."
    )
    stages.append(
        _new_stage(
            "final_answer",
            "Final Answer",
            final_status,
            0,
            final_summary,
            details={"answer": answer, "source_count": len(retrieved_chunks)},
        )
    )

    return {
        "trace_id": trace_id,
        "query": normalized_query,
        "stages": stages,
        "retrieved_chunks": retrieved_chunks,
        "context_preview": _clip_text(context, 800),
        "answer": answer,
        "total_duration_ms": _duration_ms(total_started_at),
    }


__all__ = ["build_rag_demo_trace"]
