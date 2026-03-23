from typing import Any, Dict, List, Optional

import requests

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.vector_store import VectorStore, VectorStoreError

SYSTEM_PROMPT = (
    "You are a rigorous academic teaching assistant. Answer strictly based on "
    "the provided reference materials. If evidence is insufficient, say so clearly. "
    "Respond in English by default unless the user explicitly requests another language."
)


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
        # If filtering is needed, retrieve more candidates and filter them
        search_k = top_k * 10 if source_filter else top_k
        results = vector_store.search_with_metadata(query_embedding, top_k=search_k)

        if source_filter:
            # Filter by source filename
            # Support both exact match and partial match (for UUID prefixes)
            normalized_filters = [str(s).lower().strip() for s in source_filter]
            filtered = []
            for r in results:
                source = str(r.get("source", "")).lower().strip()
                # Check if any filter matches this source
                for f in normalized_filters:
                    # Exact match or source starts with filter (handles UUID prefixes)
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
        lines.append(f"[S{idx}] source={source} page={page_label}\n{text}")
    return "\n\n".join(lines)


def generate_with_local_qwen(
    query: str,
    context: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = 30,
) -> str:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    resolved_model = model or settings.LOCAL_QWEN_MODEL
    resolved_base_url = base_url or settings.LOCAL_QWEN_BASE_URL
    resolved_timeout = timeout_seconds or settings.LOCAL_QWEN_TIMEOUT_SECONDS

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Reference materials:\n{context}\n\nUser question: {query}",
            },
        ],
        "stream": False,
        "keep_alive": settings.LOCAL_QWEN_KEEP_ALIVE,
    }

    response = requests.post(
        f"{resolved_base_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=resolved_timeout,
    )
    response.raise_for_status()

    data = response.json()
    message = data.get("message", {}).get("content")
    if not message:
        raise LocalRAGError("Invalid response format from local Qwen model")

    return str(message).strip()


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

    headers = {
        "Authorization": f"Bearer {resolved_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/lecture-note-qa",
        "X-Title": "Lecture Note Q&A System",
    }

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Reference materials:\n{context}\n\nUser question: {query}",
            },
        ],
        "temperature": temperature,
        "stream": False,
    }

    response = requests.post(
        f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout_seconds,
    )
    response.raise_for_status()

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise LocalRAGError("Invalid response format from OpenRouter API")

    message = choices[0].get("message", {}).get("content")
    if not message:
        raise LocalRAGError("Empty response from OpenRouter API")

    return str(message).strip()


def generate(
    query: str,
    context: str,
    model: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
) -> str:
    provider = settings.LLM_PROVIDER

    if provider == "openrouter":
        try:
            return generate_with_openrouter(
                query=query,
                context=context,
                model=model,
                temperature=temperature,
                timeout_seconds=timeout_seconds,
            )
        except LocalRAGError as exc:
            # OpenRouter may be misconfigured or have exhausted quota.
            # Fall back to local Qwen to keep chat functional.
            openrouter_error: Exception = exc
        except requests.exceptions.Timeout as exc:
            openrouter_error = exc
        except requests.exceptions.RequestException as exc:
            openrouter_error = exc

        try:
            return generate_with_local_qwen(
                query=query,
                context=context,
                # Always prefer the configured local model for fallback.
                model=settings.LOCAL_QWEN_MODEL,
                timeout_seconds=timeout_seconds,
            )
        except Exception as local_exc:  # noqa: BLE001
            raise LocalRAGError(
                f"OpenRouter failed ({openrouter_error}) and local Qwen also failed ({local_exc})"
            ) from local_exc
    elif provider == "local_qwen":
        return generate_with_local_qwen(
            query=query,
            context=context,
            model=model,
            timeout_seconds=timeout_seconds,
        )
    else:
        raise LocalRAGError(f"Unsupported LLM_PROVIDER: {provider}")
