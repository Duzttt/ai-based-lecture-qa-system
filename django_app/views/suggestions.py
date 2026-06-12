from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from ._helpers import _error_response, _get_json_body


@require_http_methods(["GET"])
def get_question_suggestions(request: HttpRequest) -> JsonResponse:
    """
    Generate question suggestions based on selected documents.

    Query params:
        doc_ids: Comma-separated list of document filenames
        num_suggestions: Number of suggestions to generate (default: 3)
        llm_provider: LLM provider to use (default: "local_qwen")
    """
    from app.services.question_suggestions import (
        generate_question_suggestions,
        QuestionSuggestionError,
    )

    from .summary import _get_document_text

    # Get document IDs from query params
    doc_ids_param = request.GET.get("doc_ids", "")
    num_suggestions = int(request.GET.get("num_suggestions", 3))

    if not doc_ids_param:
        return _error_response("doc_ids query parameter is required", status=400)

    # Parse document IDs
    doc_ids = [doc_id.strip() for doc_id in doc_ids_param.split(",") if doc_id.strip()]

    if not doc_ids:
        return _error_response("No valid document IDs provided", status=400)

    # Limit number of suggestions
    num_suggestions = min(max(1, num_suggestions), 5)

    try:
        # Get document content from FAISS
        documents = []
        for doc_id in doc_ids:
            text = _get_document_text(doc_id)
            if text:
                documents.append(
                    {
                        "name": doc_id,
                        "content": text,
                    }
                )

        if not documents:
            return _error_response("No valid documents found in index", status=404)

        # Generate suggestions
        result = generate_question_suggestions(documents, num_suggestions)

        return JsonResponse(
            {
                "success": True,
                "suggestions": result.get("suggestions", []),
                "generated_from": result.get("generated_from", []),
                "document_count": len(documents),
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
    """
    Record when a user clicks on a suggested question.

    Body:
        question: str - The question text that was clicked
        doc_ids: List[str] - Document IDs the suggestion was based on
        position: int - Position of the clicked suggestion (0-indexed)
    """
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
        # Try to find existing suggestion
        existing = None
        doc_names_str = ", ".join(sorted([str(d) for d in doc_ids]))

        # Search for similar suggestions
        candidates = SuggestedQuestion.objects.filter(
            question_text=question_text,
            document_names=doc_names_str,
        )

        if candidates.exists():
            existing = candidates.first()
        else:
            # Try to find by question text only (more lenient)
            candidates = SuggestedQuestion.objects.filter(
                question_text=question_text,
            )
            if candidates.exists():
                existing = candidates.first()

        if existing:
            # Increment click count
            existing.increment_click_count()
            suggestion_id = existing.id
        else:
            # Create new suggestion record
            new_suggestion = SuggestedQuestion.objects.create(
                question_text=question_text,
                question_type="concept",  # Default type
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
        # Don't fail the request if tracking fails
        print(f"Failed to record suggestion click: {exc}")
        return JsonResponse(
            {
                "success": True,
                "message": "Click recorded (tracking may have failed)",
            }
        )


@require_http_methods(["GET"])
def get_suggestion_history(request: HttpRequest) -> JsonResponse:
    """
    Get history of generated suggestions.

    Query params:
        limit: int (optional) - Maximum number of suggestions to return (default: 20)
        doc_id: str (optional) - Filter by document ID
    """
    from django_app.models import SuggestedQuestion

    try:
        limit = int(request.GET.get("limit", 20))
        doc_id = request.GET.get("doc_id", "")

        limit = min(limit, 100)  # Max 100

        # Build query
        query = SuggestedQuestion.objects.all()

        if doc_id:
            query = query.filter(document_names__icontains=doc_id)

        # Get recent suggestions
        suggestions = query.order_by("-created_at")[:limit]

        # Serialize
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
