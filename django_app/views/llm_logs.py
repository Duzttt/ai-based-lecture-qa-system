"""LLM call monitoring views."""

from django.http import HttpRequest, JsonResponse
from django.shortcuts import render
from django.db.models import Avg, Count
from django.views.decorators.http import require_http_methods

from django_app.models import QueryLog


@require_http_methods(["GET"])
def llm_logs_list(request: HttpRequest) -> JsonResponse:
    provider = request.GET.get("provider", "")
    call_type = request.GET.get("call_type", "")
    page = int(request.GET.get("page", 1))
    page_size = min(int(request.GET.get("page_size", 50)), 200)

    queryset = QueryLog.objects.exclude(llm_provider="")

    if provider:
        queryset = queryset.filter(llm_provider=provider)
    if call_type:
        queryset = queryset.filter(call_type=call_type)

    total = queryset.count()
    offset = (page - 1) * page_size
    records = queryset[offset : offset + page_size]

    return JsonResponse(
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": [
                {
                    "id": r.id,
                    "query": r.query[:200],
                    "llm_provider": r.llm_provider,
                    "llm_model": r.llm_model,
                    "llm_status": r.llm_status,
                    "error_message": r.error_message,
                    "call_type": r.call_type,
                    "latency_ms": r.latency_ms,
                    "answer_length": r.answer_length,
                    "created_at": r.created_at.isoformat(),
                }
                for r in records
            ],
        }
    )


@require_http_methods(["GET"])
def llm_logs_stats(request: HttpRequest) -> JsonResponse:
    base_qs = QueryLog.objects.exclude(llm_provider="")

    provider_counts = dict(
        base_qs.values_list("llm_provider")
        .annotate(count=Count("id"))
        .values_list("llm_provider", "count")
    )

    total = base_qs.count()
    error_count = base_qs.filter(llm_status="error").count()
    avg_latency = base_qs.aggregate(avg=Avg("latency_ms"))["avg"] or 0

    return JsonResponse(
        {
            "total_calls": total,
            "error_count": error_count,
            "error_rate": round(error_count / total * 100, 1) if total > 0 else 0,
            "avg_latency_ms": round(avg_latency),
            "by_provider": provider_counts,
        }
    )


def llm_logs_page(request: HttpRequest):
    return render(request, "llm_logs.html")
