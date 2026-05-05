import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import _error_response, _get_json_body

SUMMARY_HISTORY_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "summary_history.json"
)


def _load_summary_history() -> List[Dict[str, Any]]:
    if not SUMMARY_HISTORY_FILE.exists():
        return []

    try:
        with SUMMARY_HISTORY_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (OSError, json.JSONDecodeError):
        pass

    return []


def _save_summary_history(history: List[Dict[str, Any]]) -> None:
    SUMMARY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_document_text(filename: str) -> Optional[str]:
    from app.services.runtime_embedding import load_runtime_embedding_settings
    from app.services.vector_store import VectorStore

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )

        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)

        if not doc_chunks:
            return None

        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        full_text = " ".join([str(c.get("text", "")) for c in doc_chunks])

        return full_text
    except Exception:
        return None


def _get_document_chunks(filename: str) -> List[Dict[str, Any]]:
    from app.services.runtime_embedding import load_runtime_embedding_settings
    from app.services.vector_store import VectorStore

    try:
        rt = load_runtime_embedding_settings()
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=rt["embedding_dim"],
        )

        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)

        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        return doc_chunks
    except Exception:
        return []


@csrf_exempt
@require_http_methods(["POST"])
def generate_summary(request: HttpRequest) -> JsonResponse:
    from app.services.summarizer import DocumentSummarizer, SummarizerError

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    document_ids = payload.get("document_ids", [])
    config = payload.get("config", {})

    if not document_ids:
        return _error_response("No documents selected", status=400)

    if not isinstance(document_ids, list):
        return _error_response("document_ids must be a list", status=400)

    default_config = {
        "length": "medium",
        "style": "narrative",
        "language": "zh",
        "include_citations": True,
        "include_comparison": len(document_ids) > 1,
    }
    default_config.update(config)

    documents = []
    for doc_id in document_ids:
        text = _get_document_text(doc_id)
        if text:
            chunks = _get_document_chunks(doc_id)
            documents.append(
                {
                    "name": doc_id,
                    "text": text,
                    "chunks": chunks,
                }
            )

    if not documents:
        return _error_response("No valid documents found", status=404)

    try:
        summarizer = DocumentSummarizer()
        result = summarizer.generate_summary(documents, default_config)

        history = _load_summary_history()
        history_entry = {
            "id": f"summary_{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "documents": [doc["name"] for doc in documents],
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "config": default_config,
            "document_count": len(documents),
        }
        history.insert(0, history_entry)

        if len(history) > 50:
            history = history[:50]

        _save_summary_history(history)

        return JsonResponse(
            {
                "success": True,
                "summary": result["text"],
                "citations": result.get("citations", []),
                "comparison": result.get("comparison", []),
                "document_count": len(documents),
                "documents": [doc["name"] for doc in documents],
                "config": default_config,
                "history_id": history_entry["id"],
            }
        )

    except SummarizerError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to generate summary: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_summary_history(request: HttpRequest) -> JsonResponse:
    try:
        limit = int(request.GET.get("limit", 20))
        limit = min(limit, 50)

        history = _load_summary_history()
        recent_history = history[:limit]

        return JsonResponse(
            {
                "history": recent_history,
                "total": len(history),
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to load history: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def delete_summary(request: HttpRequest, summary_id: str) -> JsonResponse:
    try:
        history = _load_summary_history()
        new_history = [h for h in history if h.get("id") != summary_id]

        if len(new_history) == len(history):
            return _error_response("Summary not found", status=404)

        _save_summary_history(new_history)

        return JsonResponse(
            {
                "success": True,
                "message": "Summary deleted",
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to delete summary: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def regenerate_summary(request: HttpRequest) -> JsonResponse:
    from app.services.summarizer import DocumentSummarizer, SummarizerError

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    history_id = payload.get("history_id")
    new_config = payload.get("config", {})

    if not history_id:
        return _error_response("history_id is required", status=400)

    history = _load_summary_history()
    original = None
    for h in history:
        if h.get("id") == history_id:
            original = h
            break

    if not original:
        return _error_response("Summary not found", status=404)

    config = {**original.get("config", {}), **new_config}

    documents = []
    for doc_name in original.get("documents", []):
        text = _get_document_text(doc_name)
        if text:
            chunks = _get_document_chunks(doc_name)
            documents.append(
                {
                    "name": doc_name,
                    "text": text,
                    "chunks": chunks,
                }
            )

    if not documents:
        return _error_response("Documents not found", status=404)

    try:
        summarizer = DocumentSummarizer()
        result = summarizer.generate_summary(documents, config)

        updated_entry = {
            **original,
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "config": config,
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
        }

        new_history = [
            h if h.get("id") != history_id else updated_entry for h in history
        ]
        _save_summary_history(new_history)

        return JsonResponse(
            {
                "success": True,
                "summary": result["text"],
                "citations": result.get("citations", []),
                "comparison": result.get("comparison", []),
                "config": config,
            }
        )

    except SummarizerError as exc:
        return _error_response(str(exc), status=500)
    except Exception as exc:
        return _error_response(f"Failed to regenerate summary: {str(exc)}", status=500)
