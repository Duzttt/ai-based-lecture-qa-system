import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ._helpers import _error_response, _get_json_body

SUMMARY_HISTORY_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "summary_history.json"
)


def _load_summary_history() -> List[Dict[str, Any]]:
    """Load summary history from file."""
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
    """Save summary history to file."""
    SUMMARY_HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SUMMARY_HISTORY_FILE.open("w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def _get_document_text(filename: str) -> Optional[str]:
    """
    Get full text content of a document from FAISS chunks.

    Args:
        filename: Document filename

    Returns:
        Full text content or None if not found
    """
    from app.services.vector_store import VectorStore
    from app.config import settings

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )

        # Find all chunks for this document
        doc_chunks = []
        for chunk in vector_store.chunks:
            chunk_source = str(chunk.get("source", ""))
            # Match by filename (handle UUID prefixes)
            if filename in chunk_source or chunk_source.endswith(filename):
                doc_chunks.append(chunk)

        if not doc_chunks:
            return None

        # Sort by page and join text
        doc_chunks.sort(key=lambda c: c.get("page", 0) or 0)
        full_text = " ".join([str(c.get("text", "")) for c in doc_chunks])

        return full_text
    except Exception:
        return None


@csrf_exempt
@require_http_methods(["POST"])
def generate_summary(request: HttpRequest) -> JsonResponse:
    """
    Generate summary for selected documents.

    Body:
        document_ids: List[str] - List of document filenames
        config: Dict (optional) - Summary configuration:
            - length: "short" | "medium" | "detailed"
            - style: "bullets" | "narrative" | "academic" | "executive"
            - language: "zh" | "en"
            - include_citations: bool
            - include_comparison: bool
    """
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

    # Default configuration
    default_config = {
        "length": "medium",
        "style": "narrative",
        "language": "zh",
        "include_citations": True,
        "include_comparison": len(document_ids) > 1,
    }
    default_config.update(config)

    # Get document texts
    documents = []
    for doc_id in document_ids:
        text = _get_document_text(doc_id)
        if text:
            documents.append(
                {
                    "name": doc_id,
                    "text": text,
                }
            )

    if not documents:
        return _error_response("No valid documents found", status=404)

    try:
        # Generate summary
        summarizer = DocumentSummarizer()
        result = summarizer.generate_summary(documents, default_config)

        # Save to history
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
        history.insert(0, history_entry)  # Add to beginning

        # Keep only last 50 summaries
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
    """
    Get summary generation history.

    Query params:
        limit: int (optional) - Maximum number of histories to return (default: 20)
    """
    try:
        limit = int(request.GET.get("limit", 20))
        limit = min(limit, 50)  # Max 50

        history = _load_summary_history()

        # Return most recent summaries
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
    """
    Delete a summary from history.

    URL parameter:
        summary_id: str - The summary ID to delete
    """
    try:
        history = _load_summary_history()

        # Find and remove the summary
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
    """
    Regenerate summary with different configuration.

    Body:
        history_id: str - The summary history ID to regenerate
        config: Dict - New configuration
    """
    from app.services.summarizer import DocumentSummarizer, SummarizerError

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    history_id = payload.get("history_id")
    new_config = payload.get("config", {})

    if not history_id:
        return _error_response("history_id is required", status=400)

    # Find the original summary
    history = _load_summary_history()
    original = None
    for h in history:
        if h.get("id") == history_id:
            original = h
            break

    if not original:
        return _error_response("Summary not found", status=404)

    # Merge old config with new
    config = {**original.get("config", {}), **new_config}

    # Get document texts
    documents = []
    for doc_name in original.get("documents", []):
        text = _get_document_text(doc_name)
        if text:
            documents.append(
                {
                    "name": doc_name,
                    "text": text,
                }
            )

    if not documents:
        return _error_response("Documents not found", status=404)

    try:
        # Regenerate summary
        summarizer = DocumentSummarizer()
        result = summarizer.generate_summary(documents, config)

        # Update history
        updated_entry = {
            **original,
            "summary": result["text"],
            "citations": result.get("citations", []),
            "comparison": result.get("comparison", []),
            "config": config,
            "regenerated_at": datetime.now(timezone.utc).isoformat(),
        }

        # Replace in history
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
