from functools import lru_cache
from typing import Dict, List, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from django_app.views.helpers import _error_response, _get_json_body

# Cache for document text to avoid repeated vector store lookups
_document_text_cache: Dict[str, str] = {}
_cache_valid: bool = False


def _clear_document_cache():
    """Clear the document text cache."""
    global _document_text_cache, _cache_valid
    _document_text_cache.clear()
    _cache_valid = False


def _get_document_text(filename: str) -> Optional[str]:
    """
    Get document text from vector store with caching.

    Args:
        filename: Name of the document file

    Returns:
        Combined text from all chunks of the document, or None if not found
    """
    global _document_text_cache, _cache_valid

    # Return from cache if available
    if _cache_valid and filename in _document_text_cache:
        return _document_text_cache[filename]

    from app.config import settings
    from app.services.vector_store import VectorStore

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )

        # Build cache for all documents if cache is invalid
        if not _cache_valid:
            doc_chunks_map: Dict[str, List[Dict]] = {}
            for chunk in vector_store.chunks:
                chunk_source = str(chunk.get("source", ""))
                if chunk_source not in doc_chunks_map:
                    doc_chunks_map[chunk_source] = []
                doc_chunks_map[chunk_source].append(chunk)

            # Build text cache for each document
            for doc_name, chunks in doc_chunks_map.items():
                chunks.sort(key=lambda c: c.get("page", 0) or 0)
                full_text = " ".join([str(c.get("text", "")) for c in chunks])
                _document_text_cache[doc_name] = full_text

            _cache_valid = True

        # Try exact match first, then partial match
        if filename in _document_text_cache:
            return _document_text_cache[filename]

        # Fallback: partial filename matching
        for cached_name, text in _document_text_cache.items():
            if filename in cached_name or cached_name.endswith(filename):
                return text

        return None

    except Exception:
        return None


@require_http_methods(["GET"])
def get_question_suggestions(request: HttpRequest) -> JsonResponse:
    import time

    from app.services.question_suggestions import (
        generate_question_suggestions,
        QuestionSuggestionError,
    )

    start_time = time.time()

    doc_ids_param = request.GET.get("doc_ids", "")
    num_suggestions = int(request.GET.get("num_suggestions", 3))

    if not doc_ids_param:
        return _error_response("doc_ids query parameter is required", status=400)

    doc_ids = [doc_id.strip() for doc_id in doc_ids_param.split(",") if doc_id.strip()]

    if not doc_ids:
        return _error_response("No valid document IDs provided", status=400)

    num_suggestions = min(max(1, num_suggestions), 5)

    try:
        # Pre-fetch all document texts to avoid repeated lookups
        documents = []
        for doc_id in doc_ids:
            text = _get_document_text(doc_id)
            if text:
                documents.append(
                    {
                        "name": doc_id,
                        "content": text[
                            :5000
                        ],  # Limit content length for faster processing
                    }
                )

        if not documents:
            return _error_response("No valid documents found in index", status=404)

        result = generate_question_suggestions(documents, num_suggestions)

        elapsed_ms = (time.time() - start_time) * 1000

        return JsonResponse(
            {
                "success": True,
                "suggestions": result.get("suggestions", []),
                "generated_from": result.get("generated_from", []),
                "document_count": len(documents),
                "generation_time_ms": round(elapsed_ms, 1),
            }
        )

    except QuestionSuggestionError as exc:
        return _error_response(f"Suggestion generation failed: {str(exc)}", status=500)
    except Exception as exc:
        return _error_response(
            f"Failed to generate suggestions: {str(exc)}", status=500
        )


@csrf_exempt
@require_http_methods(["POST"])
def record_suggestion_click(request: HttpRequest) -> JsonResponse:
    from django_app.models import SuggestedQuestion

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    question_text = payload.get("question", "").strip()
    doc_ids = payload.get("doc_ids", [])
    position = payload.get("position", 0)

    if not question_text:
        return _error_response("question is required", status=400)

    if not doc_ids:
        return _error_response("doc_ids is required", status=400)

    try:
        existing = None
        doc_names_str = ", ".join(sorted([str(d) for d in doc_ids]))

        candidates = SuggestedQuestion.objects.filter(
            question_text=question_text,
            document_names=doc_names_str,
        )

        if candidates.exists():
            existing = candidates.first()
        else:
            candidates = SuggestedQuestion.objects.filter(
                question_text=question_text,
            )
            if candidates.exists():
                existing = candidates.first()

        if existing:
            existing.increment_click_count()
            suggestion_id = existing.id
        else:
            new_suggestion = SuggestedQuestion.objects.create(
                question_text=question_text,
                question_type="concept",
                document_names=doc_names_str,
                click_count=1,
                generation_metadata={
                    "position": position,
                    "doc_ids": doc_ids,
                },
            )
            suggestion_id = new_suggestion.id

        return JsonResponse(
            {
                "success": True,
                "message": "Click recorded",
                "suggestion_id": suggestion_id,
                "click_count": (existing.click_count if existing else 1),
            }
        )

    except Exception as exc:
        print(f"Failed to record suggestion click: {exc}")
        return JsonResponse(
            {
                "success": True,
                "message": "Click recorded (tracking may have failed)",
            }
        )


@require_http_methods(["GET"])
def get_suggestion_history(request: HttpRequest) -> JsonResponse:
    from django_app.models import SuggestedQuestion

    try:
        limit = int(request.GET.get("limit", 20))
        doc_id = request.GET.get("doc_id", "")

        limit = min(limit, 100)

        query = SuggestedQuestion.objects.all()

        if doc_id:
            query = query.filter(document_names__icontains=doc_id)

        suggestions = query.order_by("-created_at")[:limit]

        result = []
        for s in suggestions:
            result.append(
                {
                    "id": s.id,
                    "question_text": s.question_text,
                    "question_type": s.question_type,
                    "document_names": (
                        s.document_names.split(", ") if s.document_names else []
                    ),
                    "click_count": s.click_count,
                    "feedback_score": s.feedback_score,
                    "created_at": s.created_at.isoformat(),
                }
            )

        return JsonResponse(
            {
                "suggestions": result,
                "total": query.count(),
            }
        )

    except Exception:
        return JsonResponse({"suggestions": [], "total": 0})
