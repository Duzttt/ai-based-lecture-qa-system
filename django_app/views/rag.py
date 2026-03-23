import json
import time
from pathlib import Path
from typing import Any, Dict, List

import requests
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.local_rag import (
    LocalRAGError,
    build_context_from_sources,
    generate,
    retrieve_with_faiss,
)

from django_app.admin_utils import log_query
from django_app.views.helpers import (
    VALID_PROVIDERS,
    _build_retrieved_chunks,
    _build_source_snippets,
    _error_response,
    _get_json_body,
    _load_persisted_settings,
    _load_rag_config,
    _save_rag_config,
    inject_citation_marks,
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
        answer = generate(query=query, context=context)
    except requests.exceptions.Timeout:
        return _error_response(
            ("LLM request timed out"),
            status=504,
        )
    except requests.exceptions.RequestException as exc:
        return _error_response(
            f"Failed to call LLM: {str(exc)}",
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
    similarity_threshold = float(rag_config.get("similarity_threshold", 0.6))
    started_at = time.perf_counter()
    retrieved_sources: List[Dict[str, Any]] = []

    try:
        retrieved_sources = retrieve_with_faiss(
            query=query, top_k=top_k, source_filter=source_filter
        )
        context = build_context_from_sources(retrieved_sources)
        if not context.strip():
            return _error_response("No indexed context found in FAISS", status=400)

        answer = generate(
            query=query,
            context=context,
            model=llm_model,
            temperature=temperature,
        )
        if not answer:
            raise LocalRAGError("Empty response from LLM")
    except requests.exceptions.Timeout:
        return _error_response("LLM request timed out", status=504)
    except requests.exceptions.RequestException as exc:
        return _error_response(f"Failed to call LLM: {str(exc)}", status=503)
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
    try:
        latency_ms = int((time.perf_counter() - started_at) * 1000)
        log_query(
            query=query,
            latency_ms=latency_ms,
            results_count=len(retrieved_sources),
            query_type="other",
            cache_hit=False,
            top_k=int(top_k),
            similarity_threshold=similarity_threshold,
            retrieved_documents=_build_retrieved_chunks(retrieved_sources),
            user_feedback=None,
            session_id=str(request.headers.get("X-Session-Id", "")),
            llm_model=str(llm_model),
            answer_length=len(answer),
        )
    except Exception:  # noqa: BLE001
        pass

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

    try:
        from app.services.citation_rag import CitationRAGPipeline, CitationRAGError

        pipeline = CitationRAGPipeline(model=llm_model)
        result = pipeline.query(
            question=query,
            top_k=top_k,
            source_filter=source_filter,
        )
    except requests.exceptions.Timeout:
        return _error_response(
            "LLM request timed out",
            status=504,
        )
    except requests.exceptions.RequestException as exc:
        return _error_response(f"Failed to call LLM: {str(exc)}", status=503)
    except CitationRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to process query: {str(exc)}", status=500)

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


@csrf_exempt
@require_http_methods(["GET", "POST"])
def settings_handler(request: HttpRequest) -> JsonResponse:
    from app.config import settings as app_settings

    if request.method == "GET":
        stored_settings = _load_persisted_settings()
        provider = stored_settings.get("provider") or app_settings.LLM_PROVIDER
        if provider not in VALID_PROVIDERS:
            provider = app_settings.LLM_PROVIDER

        if provider == "gemini":
            default_model = app_settings.GEMINI_MODEL
            default_key = app_settings.GEMINI_API_KEY
        elif provider == "local_qwen":
            default_model = app_settings.LOCAL_QWEN_MODEL
            default_key = None
        else:
            default_model = "anthropic/claude-3-haiku"
            default_key = app_settings.OPENROUTER_API_KEY

        model = stored_settings.get("model") or default_model
        api_key = stored_settings.get("api_key") or default_key

        return JsonResponse(
            {
                "provider": provider,
                "model": model,
                "has_api_key": bool(api_key),
            }
        )

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    provider = str(payload.get("provider", "")).strip().lower()
    model = str(payload.get("model", "")).strip()
    existing_settings = _load_persisted_settings()
    api_key: Any
    if "api_key" in payload:
        incoming_key = payload.get("api_key")
        if incoming_key is None:
            api_key = None
        else:
            stripped_key = str(incoming_key).strip()
            api_key = stripped_key or None
    else:
        api_key = existing_settings.get("api_key")

    if provider not in VALID_PROVIDERS:
        return _error_response("Invalid provider", status=400)

    if not model:
        return _error_response("Model cannot be empty", status=400)

    data_to_store: Dict[str, Any] = {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }

    from django_app.views.helpers import SETTINGS_FILE

    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_FILE.open("w", encoding="utf-8") as settings_file:
            json.dump(data_to_store, settings_file)
    except OSError as exc:
        return _error_response(f"Failed to save settings: {str(exc)}", status=500)

    return JsonResponse({"success": True, "message": "Settings updated"})


LLM_PROVIDERS_CATALOG = [
    {
        "id": "gemini",
        "name": "Google Gemini",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.0-flash"],
        "requires_api_key": True,
    },
    {
        "id": "openrouter",
        "name": "OpenRouter",
        "models": [
            "openrouter/free",
            "anthropic/claude-3-haiku",
            "meta-llama/llama-3-70b-instruct",
            "google/gemma-2-9b-it:free",
        ],
        "requires_api_key": True,
    },
    {
        "id": "local_qwen",
        "name": "Local Qwen (Ollama)",
        "models": ["qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b", "qwen2.5:7b"],
        "requires_api_key": False,
    },
]


@csrf_exempt
@require_http_methods(["GET"])
def providers_handler(request: HttpRequest) -> JsonResponse:
    from app.config import settings as app_settings

    stored_settings = _load_persisted_settings()
    current_provider = stored_settings.get("provider") or app_settings.LLM_PROVIDER
    if current_provider not in VALID_PROVIDERS:
        current_provider = app_settings.LLM_PROVIDER

    current_model = stored_settings.get("model") or ""
    if not current_model:
        if current_provider == "gemini":
            current_model = app_settings.GEMINI_MODEL
        elif current_provider == "local_qwen":
            current_model = app_settings.LOCAL_QWEN_MODEL
        else:
            current_model = "anthropic/claude-3-haiku"

    has_gemini_key = bool(app_settings.GEMINI_API_KEY or stored_settings.get("api_key"))
    has_openrouter_key = bool(
        app_settings.OPENROUTER_API_KEY or stored_settings.get("api_key")
    )

    providers = []
    for p in LLM_PROVIDERS_CATALOG:
        entry = {**p}
        if p["id"] == "gemini":
            entry["has_api_key"] = has_gemini_key
        elif p["id"] == "openrouter":
            entry["has_api_key"] = has_openrouter_key
        else:
            entry["has_api_key"] = False
        providers.append(entry)

    return JsonResponse(
        {
            "current": {"provider": current_provider, "model": current_model},
            "providers": providers,
        }
    )


@require_http_methods(["GET"])
def get_rag_config(request: HttpRequest) -> JsonResponse:
    config = _load_rag_config()
    return JsonResponse(config)


@csrf_exempt
@require_http_methods(["POST"])
def update_rag_config(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    llm_model = str(payload.get("llm_model", settings.LOCAL_QWEN_MODEL)).strip()
    top_k = int(payload.get("top_k", 3))
    temperature = float(payload.get("temperature", 0.7))

    if top_k < 1:
        top_k = 1
    elif top_k > 20:
        top_k = 20

    if temperature < 0.0:
        temperature = 0.0
    elif temperature > 2.0:
        temperature = 2.0

    config = {
        "llm_model": llm_model,
        "top_k": top_k,
        "temperature": temperature,
    }
    _save_rag_config(config)
    return JsonResponse({"status": "success", "config": config})


@csrf_exempt
@require_http_methods(["POST"])
def reset_faiss_index(request: HttpRequest) -> JsonResponse:
    import shutil

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    confirm_text = str(payload.get("confirm", "")).strip().lower()
    if confirm_text != "reset":
        return _error_response(
            'Please type "reset" to confirm index deletion', status=400
        )

    index_path = Path(settings.FAISS_INDEX_PATH)
    if index_path.exists():
        shutil.rmtree(index_path)
        index_path.mkdir(parents=True, exist_ok=True)

    return JsonResponse({"status": "success", "message": "FAISS index has been reset"})


@csrf_exempt
@require_http_methods(["POST"])
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
            answer = generate(
                query=query,
                context=context,
                model=llm_model,
                temperature=temperature,
            )
            if not answer:
                answer = "Empty response from LLM."
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


@csrf_exempt
@require_http_methods(["POST"])
def compare_documents(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    sources = payload.get("sources")

    if not query:
        return _error_response("Query cannot be empty", status=400)

    if not sources or not isinstance(sources, list):
        return _error_response("Sources must be a list of document names", status=400)

    if len(sources) < 2:
        return _error_response(
            "At least 2 documents required for comparison", status=400
        )

    if len(sources) > 3:
        return _error_response(
            "Maximum 3 documents can be compared at once", status=400
        )

    from django_app.views.helpers import analyze_differences

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    results: List[Dict[str, Any]] = []

    for source in sources:
        try:
            retrieved = retrieve_with_faiss(
                query=query,
                top_k=top_k,
                source_filter=[source],
            )
            context = build_context_from_sources(retrieved)

            if not context.strip():
                results.append(
                    {
                        "source": source,
                        "answer": "No relevant content found in this document.",
                        "success": True,
                    }
                )
                continue

            answer = generate(
                query=query,
                context=context,
                model=llm_model,
                temperature=temperature,
            )
            if not answer:
                answer = "Empty response from model."

            results.append(
                {
                    "source": source,
                    "answer": answer,
                    "success": True,
                }
            )

        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "source": source,
                    "answer": f"Error: {str(exc)}",
                    "success": False,
                }
            )

    common_points, different_points = analyze_differences(
        [r["answer"] for r in results if r["success"]]
    )

    return JsonResponse(
        {
            "results": results,
            "analysis": {
                "common": common_points,
                "different": different_points,
            },
        }
    )
