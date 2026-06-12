import json
import re
from datetime import datetime
from typing import Any, Dict, List

import httpx
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ollama import Client as OllamaClient

from app.config import settings
from app.services.local_rag import (
    LocalRAGError,
    build_context_from_sources,
    generate_with_local_qwen,
    query_with_citations,
    retrieve_with_faiss,
)

from ._helpers import (
    _build_retrieved_chunks,
    _build_source_snippets,
    _error_response,
    _get_json_body,
    _load_rag_config,
)


@csrf_exempt
@require_http_methods(["POST"])
def ask_question(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or payload.get("question") or "").strip()
    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    if not query:
        return _error_response("Query cannot be empty", status=400)

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query, top_k=3, source_filter=source_filter
        )
        context = build_context_from_sources(retrieved_sources)
        answer = generate_with_local_qwen(query=query, context=context)
    except httpx.TimeoutException:
        return _error_response(
            f"Local Qwen model request timed out (timeout={settings.LOCAL_QWEN_TIMEOUT_SECONDS}s)",
            status=504,
        )
    except httpx.RequestError as exc:
        return _error_response(
            f"Failed to call local Qwen model: {str(exc)}",
            status=503,
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to process query: {str(exc)}",
            status=500,
        )

    source_files = sorted(
        {
            str(source.get("source", "unknown"))
            for source in retrieved_sources
            if source.get("source")
        }
    )

    return JsonResponse(
        {
            "answer": answer,
            "sources": source_files,
            "source_snippets": _build_source_snippets(retrieved_sources),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ask_qwen(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    if not query:
        return _error_response("Query cannot be empty", status=400)

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query, top_k=top_k, source_filter=source_filter
        )
        context = build_context_from_sources(retrieved_sources)
        if not context.strip():
            return _error_response("No indexed context found in FAISS", status=400)

        system_prompt = (
            "You are a rigorous academic teaching assistant. Please answer the questions based on the following reference materials."
            "If the evidence is insufficient, please explain clearly. "
            "Respond in English by default unless the user explicitly requests another language."
        )
        user_prompt = f"Reference materials:\n{context}\n\nUser question: {query}"

        ollama_client = OllamaClient(
            host=settings.LOCAL_QWEN_BASE_URL,
            timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
        )
        model_response = ollama_client.chat(
            model=llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            stream=False,
            keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
            options={"temperature": temperature},
        )

        answer = str(model_response.get("message", {}).get("content", "")).strip()
        if not answer:
            raise LocalRAGError("Empty response from local Qwen model")
    except httpx.TimeoutException:
        return _error_response(
            (
                "Local Qwen model request timed out "
                f"(timeout={settings.LOCAL_QWEN_TIMEOUT_SECONDS}s)"
            ),
            status=504,
        )
    except httpx.RequestError as exc:
        return _error_response(
            f"Failed to call local Qwen model: {str(exc)}", status=503
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to process query: {str(exc)}", status=500)

    source_files = sorted(
        {
            str(source.get("source", "unknown"))
            for source in retrieved_sources
            if source.get("source")
        }
    )
    return JsonResponse(
        {
            "answer": answer,
            "sources": source_files,
            "source_snippets": _build_source_snippets(retrieved_sources),
            "retrieved_chunks": _build_retrieved_chunks(retrieved_sources),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def ask_with_citations(request: HttpRequest) -> JsonResponse:
    """
    Ask a question and get an answer with sentence-level citations.

    Returns structured JSON where each sentence has a citations array
    referencing the source chunks that support it.

    Response format:
    {
        "sentences": [
            {"text": "...", "citations": [1, 2]},
            {"text": "...", "citations": [1]},
            {"text": "...", "citations": []}
        ],
        "sources": {
            "1": {"file": "lecture.pdf", "page": 24},
            "2": {"file": "lecture.pdf", "page": 3}
        },
        "retrieved_chunks": [...]
    }
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    if not query:
        return _error_response("Query cannot be empty", status=400)

    # Load configuration
    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)

    try:
        from app.services.local_rag import CitationRAGError

        result = query_with_citations(
            question=query,
            top_k=top_k,
            source_filter=source_filter,
            model=llm_model,
        )
    except httpx.TimeoutException:
        return _error_response(
            f"Local Qwen model request timed out (timeout={settings.LOCAL_QWEN_TIMEOUT_SECONDS}s)",
            status=504,
        )
    except httpx.RequestError as exc:
        return _error_response(f"Failed to call local Qwen model: {str(exc)}", status=503)
    except CitationRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to process query: {str(exc)}", status=500)

    # Build retrieved chunks for visualization
    # Extract chunks from sources in the result
    retrieved_chunks = []
    for chunk_id, source_info in result.get("sources", {}).items():
        retrieved_chunks.append(
            {
                "chunk_id": int(chunk_id),
                "text": source_info.get("text", ""),
                "source": source_info.get("file", "unknown"),
                "page": source_info.get("page"),
            }
        )

    return JsonResponse(
        {
            "sentences": result.get("sentences", []),
            "sources": result.get("sources", {}),
            "retrieved_chunks": (
                _build_retrieved_chunks(retrieved_chunks) if retrieved_chunks else []
            ),
        }
    )


def inject_citation_marks(answer: str, citations: List[Dict[str, Any]]) -> str:
    """
    Inject citation marks [1], [2], etc. into the answer text.
    Places citations at the end of sentences or paragraphs.
    """
    if not citations:
        return answer

    citation_ids = [c.get("citation_id", i + 1) for i, c in enumerate(citations)]

    sentences = re.split(r"([。！？.!?\n]+)", answer)
    result = []
    citation_idx = 0

    for i, part in enumerate(sentences):
        result.append(part)

        if i % 2 == 0 and part.strip() and citation_idx < len(citation_ids):
            if len(part.strip()) > 20:
                result.append(
                    f' <span class="inline-citation" data-citation-id="{citation_ids[citation_idx]}">[{citation_ids[citation_idx]}]</span>'
                )
                citation_idx += 1

    if citation_idx < len(citation_ids):
        result.append(
            ' <span class="inline-citations">'
            + " ".join(
                [
                    f'<span class="inline-citation" data-citation-id="{cid}">[{cid}]</span>'
                    for cid in citation_ids[citation_idx:]
                ]
            )
            + "</span>"
        )

    return "".join(result)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def chat_htmx(request: HttpRequest) -> HttpResponse:
    from datetime import datetime

    query = str(request.POST.get("query", "")).strip()
    if not query:
        return HttpResponse(
            '<div class="chat-message chat-message-error"><div class="chat-message-text">'
            "Question cannot be empty."
            "</div></div>",
            status=400,
        )

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    retrieved_sources: List[Dict[str, Any]] = []
    citations: List[Dict[str, Any]] = []
    retrieved_chunks: List[Dict[str, Any]] = []

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query,
            top_k=top_k,
            source_filter=None,
        )
        context = build_context_from_sources(retrieved_sources)

        distances = [r.get("distance", 0) for r in retrieved_sources]
        max_distance = max(distances) if distances else 1.0
        max_distance = max(max_distance, 0.001)

        for idx, src in enumerate(retrieved_sources, start=1):
            distance = src.get("distance", 0)
            similarity = max(0.0, 1.0 - (distance / max_distance))
            text = src.get("text", "")
            citations.append(
                {
                    "citation_id": idx,
                    "source": src.get("source", "unknown"),
                    "page": src.get("page"),
                    "text": text[:200],
                    "bbox": src.get("bbox"),
                }
            )
            retrieved_chunks.append(
                {
                    "text": text,
                    "preview": text[:100],
                    "score": round(similarity, 3),
                    "distance": round(distance, 4),
                    "source": src.get("source", "unknown"),
                    "page": src.get("page"),
                    "bbox": src.get("bbox"),
                }
            )

        if not context.strip():
            answer = (
                "No indexed context found in FAISS. Please upload and index PDFs first."
            )
        else:
            system_prompt = (
                "You are a rigorous academic teaching assistant. Please answer the questions based on the following reference materials. "
                "If the evidence is insufficient, please explain clearly."
            )
            user_prompt = f"Reference materials:\n{context}\n\nUser question: {query}"

            ollama_client = OllamaClient(
                host=settings.LOCAL_QWEN_BASE_URL,
                timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
            )
            model_response = ollama_client.chat(
                model=llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
                options={"temperature": temperature},
            )
            answer = str(model_response.get("message", {}).get("content", "")).strip()
            if not answer:
                answer = "Empty response from local Qwen model."
            else:
                answer = inject_citation_marks(answer, citations)
    except Exception as exc:  # noqa: BLE001
        answer = f"Failed to process query: {str(exc)}"

    timestamp = datetime.now().strftime("%H:%M")
    message_id = f"msg_{int(datetime.now().timestamp() * 1000)}"

    assistant_html = render_to_string(
        "_chat_message.html",
        {
            "role": "assistant",
            "text": answer,
            "timestamp": timestamp,
            "message_id": f"assistant_{message_id}",
            "citations": citations,
            "citations_json": json.dumps(citations),
            "retrieved_chunks": retrieved_chunks,
        },
    )
    return HttpResponse(assistant_html)


@csrf_exempt
@require_http_methods(["POST"])
def retrieve_chunks(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    top_k = int(payload.get("top_k", 5))
    source_filter = payload.get("sources")

    if not query:
        return _error_response("Query cannot be empty", status=400)

    if isinstance(source_filter, str):
        source_filter = [source_filter]

    try:
        results = retrieve_with_faiss(
            query=query, top_k=top_k, source_filter=source_filter
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)

    if not results:
        return JsonResponse({"chunks": []})

    distances = [r.get("distance", 0) for r in results]
    max_distance = max(distances) if distances else 1.0
    max_distance = max(max_distance, 0.001)

    chunks = []
    for r in results:
        distance = r.get("distance", 0)
        similarity = max(0.0, 1.0 - (distance / max_distance))

        text = r.get("text", "")
        preview = text[:100] + ("..." if len(text) > 100 else "")

        chunks.append(
            {
                "text": text,
                "preview": preview,
                "score": round(similarity, 3),
                "distance": round(distance, 4),
                "source": r.get("source", "unknown"),
                "page": r.get("page"),
            }
        )

    return JsonResponse({"chunks": chunks})
