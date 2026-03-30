from typing import Any, Dict, List, Optional

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.llm_client import call_llm
from app.services.vector_store import VectorStore, VectorStoreError

SYSTEM_PROMPT = """You are an academic teaching assistant for lecture notes Q&A.

## Answer Rules
1. Base your answer **strictly** on the provided reference materials. Do not add outside knowledge.
2. Cite sources inline using the bracket labels provided, e.g. [S1], [S2]. Every factual claim must have at least one citation.
3. If the materials do not contain enough information to answer, say so explicitly — do not guess.
4. When multiple sources cover the same topic, synthesize them into a coherent answer and cite all relevant labels.
5. If sources conflict, point out the discrepancy and cite both.

## Output Format
- Start with a direct answer (1-3 sentences).
- Follow with a detailed explanation using bullet points or numbered steps where appropriate.
- End with a **Sources** line listing only the labels you actually cited, e.g. `Sources: [S1], [S3]`.

## Language
- Match the language of the user's question. If the question is in Chinese, answer in Chinese. If in English, answer in English."""


class LocalRAGError(Exception):
    pass


def retrieve_with_faiss(
    query: str, top_k: int = 3, source_filter: Optional[List[str]] = None
) -> List[Dict[str, Any]]:
    if not query.strip():
        raise LocalRAGError("Query cannot be empty")

    embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
    vector_store = VectorStore.get_cached(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )

    try:
        query_embedding = embedding_service.embed_query(query)
        search_k = top_k * 10 if source_filter else top_k
        results = vector_store.search_with_metadata(query_embedding, top_k=search_k)

        if source_filter:
            normalized_filters = [str(s).lower().strip() for s in source_filter]
            filtered = []
            for r in results:
                source = str(r.get("source", "")).lower().strip()
                for f in normalized_filters:
                    if source == f or source.startswith(f) or f in source:
                        filtered.append(r)
                        break
            return filtered[:top_k]

        return results
    except EmbeddingError as exc:
        raise LocalRAGError(str(exc)) from exc
    except VectorStoreError as exc:
        raise LocalRAGError(str(exc)) from exc


def build_context_from_sources(sources: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    for idx, item in enumerate(sources, start=1):
        source = item.get("source", "unknown")
        page = item.get("page")
        page_label = str(page) if page is not None else "unknown"
        text = item.get("text", "")
        lines.append(f"[S{idx}] (source: {source}, page: {page_label})\n{text}")
    return "\n\n".join(lines)


def build_rag_messages(
    query: str,
    context: str,
) -> List[Dict[str, str]]:
    user_content = f"## Reference Materials\n{context}\n\n" f"## Question\n{query}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


def generate_with_local_llm(
    query: str,
    context: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = 30,
) -> str:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    resolved_model = model or settings.LOCAL_LLM_MODEL
    resolved_base_url = base_url or settings.LOCAL_LLM_BASE_URL
    resolved_timeout = timeout_seconds or settings.LOCAL_LLM_TIMEOUT_SECONDS

    try:
        return call_llm(
            provider="local_llm",
            model=resolved_model,
            call_type="rag",
            messages=build_rag_messages(query, context),
            timeout=resolved_timeout,
            query_text=query,
            base_url=resolved_base_url,
            keep_alive=settings.LOCAL_LLM_KEEP_ALIVE,
        )
    except ValueError as exc:
        raise LocalRAGError(str(exc)) from exc


def generate_with_openrouter(
    query: str,
    context: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
) -> str:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    resolved_model = model or settings.OPENROUTER_MODEL
    resolved_key = api_key or settings.OPENROUTER_API_KEY

    if not resolved_key:
        raise LocalRAGError("OPENROUTER_API_KEY is not configured")

    try:
        return call_llm(
            provider="openrouter",
            model=resolved_model,
            call_type="rag",
            messages=build_rag_messages(query, context),
            timeout=timeout_seconds,
            query_text=query,
            api_key=resolved_key,
            base_url=settings.OPENROUTER_BASE_URL,
            temperature=temperature,
        )
    except ValueError as exc:
        raise LocalRAGError(str(exc)) from exc


def generate(
    query: str,
    context: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
) -> str:
    provider = settings.LLM_PROVIDER

    if provider == "openrouter":
        return generate_with_openrouter(
            query=query,
            context=context,
            model=model,
            temperature=temperature,
            timeout_seconds=timeout_seconds,
        )
    elif provider == "local_llm":
        return generate_with_local_llm(
            query=query,
            context=context,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise LocalRAGError(f"Unsupported LLM_PROVIDER: {provider}")
