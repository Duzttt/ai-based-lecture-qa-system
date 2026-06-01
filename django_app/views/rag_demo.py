from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.services.rag_demo_trace import LocalRAGError, build_rag_demo_trace

from django_app.views.helpers import _error_response, _get_json_body


@csrf_exempt
@require_http_methods(["POST"])
def rag_demo_trace(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or payload.get("question") or "").strip()
    if not query:
        return _error_response("Query cannot be empty", status=400)

    source_filter = payload.get("sources")
    if isinstance(source_filter, str):
        source_filter = [source_filter]

    try:
        top_k = int(payload.get("top_k", 5))
    except (TypeError, ValueError):
        top_k = 5
    top_k = min(max(top_k, 1), 10)

    include_answer = bool(payload.get("include_answer", True))

    try:
        trace = build_rag_demo_trace(
            query=query,
            source_filter=source_filter,
            top_k=top_k,
            include_answer=include_answer,
        )
    except LocalRAGError as exc:
        return _error_response(str(exc), status=503)
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Failed to build RAG demo trace: {str(exc)}", status=500)

    return JsonResponse(trace)


__all__ = ["rag_demo_trace"]
