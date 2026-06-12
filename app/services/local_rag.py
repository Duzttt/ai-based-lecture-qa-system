import json
import logging
import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.vector_store import VectorStore, VectorStoreError

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = (
    "You are a rigorous academic teaching assistant. Answer strictly based on "
    "the provided reference materials. If evidence is insufficient, say so clearly. "
    "Respond in English by default unless the user explicitly requests another language."
)


class LocalRAGError(Exception):
    pass


class CitationRAGError(Exception):
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
        lines.append(f"[S{idx}] source={source} page={page_label}\n{text}")
    return "\n\n".join(lines)


def generate_with_local_qwen(
    query: str,
    context: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
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

    with httpx.Client(timeout=resolved_timeout) as client:
        response = client.post(
            f"{resolved_base_url.rstrip('/')}/api/chat",
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    message = data.get("message", {}).get("content")
    if not message:
        raise LocalRAGError("Invalid response format from local Qwen model")

    return str(message).strip()


def _build_citation_prompt(query: str, chunks: List[Dict[str, Any]]) -> str:
    context_lines = []
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id", "?")
        source = chunk.get("source", "unknown")
        page = chunk.get("page", "unknown")
        text = chunk.get("text", "")
        context_lines.append(f"[{chunk_id}] Source: {source}, Page: {page}\n{text}")
    context_text = "\n\n".join(context_lines)

    return f"""You are a rigorous academic teaching assistant. Your task is to answer questions based ONLY on the provided reference materials.

IMPORTANT: You must output your answer as a valid JSON object with the following structure:
{{
  "sentences": [
    {{"text": "First sentence of your answer.", "citations": [1, 2]}},
    {{"text": "Second sentence with different sources.", "citations": [1]}},
    {{"text": "General knowledge sentence.", "citations": []}}
  ]
}}

Rules for citations:
1. Each sentence MUST have a "citations" array
2. If a sentence uses information from a chunk, include that chunk's ID number in the citations array
3. If a sentence is general knowledge or doesn't use the provided sources, use an empty array []
4. A sentence can cite multiple chunks if it combines information from multiple sources
5. Only cite chunks that actually support the statement
6. Do not make up information not found in the provided context

Reference Materials:
{context_text}

Question: {query}

Output ONLY the JSON object. No additional text, no markdown code blocks, no explanations."""


def _generate_citation_with_qwen(
    prompt: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = None,
) -> str:
    resolved_model = model or settings.LOCAL_QWEN_MODEL
    resolved_base_url = base_url or settings.LOCAL_QWEN_BASE_URL
    resolved_timeout = timeout_seconds or settings.LOCAL_QWEN_TIMEOUT_SECONDS

    payload = {
        "model": resolved_model,
        "messages": [
            {"role": "system", "content": "You are a helpful assistant that outputs valid JSON."},
            {"role": "user", "content": prompt},
        ],
        "stream": False,
        "keep_alive": settings.LOCAL_QWEN_KEEP_ALIVE,
        "options": {"temperature": 0.3},
    }

    with httpx.Client(timeout=resolved_timeout) as client:
        response = client.post(
            f"{resolved_base_url.rstrip('/')}/api/chat",
            json=payload,
        )
        response.raise_for_status()

    data = response.json()
    message = data.get("message", {}).get("content")
    if not message:
        raise CitationRAGError("Invalid response format from local Qwen model")

    return str(message).strip()


def _parse_citation_response(raw_response: str) -> Dict[str, Any]:
    json_match = re.search(r"\{[\s\S]*\}", raw_response)
    if json_match:
        raw_response = json_match.group()

    try:
        parsed = json.loads(raw_response)
    except json.JSONDecodeError as e:
        raise CitationRAGError(f"Failed to parse LLM response as JSON: {e}") from e

    if not isinstance(parsed, dict) or "sentences" not in parsed:
        raise CitationRAGError("Response must be a JSON object with 'sentences' array")

    sentences = parsed["sentences"]
    if not isinstance(sentences, list):
        raise CitationRAGError("'sentences' must be an array")

    for i, sentence in enumerate(sentences):
        if not isinstance(sentence, dict):
            raise CitationRAGError(f"Sentence {i} must be an object")
        if "text" not in sentence:
            raise CitationRAGError(f"Sentence {i} must have 'text' field")
        if "citations" not in sentence:
            raise CitationRAGError(f"Sentence {i} must have 'citations' field")
        if not isinstance(sentence["citations"], list):
            raise CitationRAGError(f"Sentence {i} citations must be an array")

    return parsed


def _build_citation_response(
    sentences_data: Dict[str, Any],
    chunks: List[Dict[str, Any]],
) -> Dict[str, Any]:
    sources = {}
    for chunk in chunks:
        chunk_id = str(chunk.get("chunk_id", ""))
        if chunk_id:
            sources[chunk_id] = {
                "file": chunk.get("source", "unknown"),
                "page": chunk.get("page"),
                "text": chunk.get("text", ""),
            }
    return {
        "sentences": sentences_data.get("sentences", []),
        "sources": sources,
    }


def query_with_citations(
    question: str,
    top_k: int = 3,
    source_filter: Optional[List[str]] = None,
    model: Optional[str] = None,
) -> Dict[str, Any]:
    if not question.strip():
        raise CitationRAGError("Query cannot be empty")

    embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
    vector_store = VectorStore.get_cached(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )

    query_embedding = embedding_service.embed_query(question)
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
        results = filtered[:top_k]
    else:
        results = results[:top_k]

    for idx, chunk in enumerate(results, start=1):
        chunk["chunk_id"] = idx

    if not results:
        return {
            "sentences": [
                {
                    "text": "No relevant information found in the uploaded documents.",
                    "citations": [],
                }
            ],
            "sources": {},
        }

    prompt = _build_citation_prompt(question, results)
    raw_response = _generate_citation_with_qwen(prompt, model=model)
    parsed = _parse_citation_response(raw_response)
    return _build_citation_response(parsed, results)
