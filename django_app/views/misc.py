from pathlib import Path

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from app.config import settings

from ._helpers import CHAT_DEMO_FILE


def root(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "message": "Lecture Note Q&A System API",
            "version": settings.APP_VERSION,
            "status": "running",
        }
    )


@require_http_methods(["GET"])
def index_page(request: HttpRequest) -> HttpResponse:
    """Serve the Vue.js frontend application (SPA)."""
    from django.conf import settings as django_settings

    frontend_index = (
        Path(django_settings.BASE_DIR)
        / "django_app"
        / "static"
        / "frontend"
        / "index.html"
    )

    if frontend_index.exists():
        html = frontend_index.read_text(encoding="utf-8")
        # Fix asset paths to include /static/frontend/ prefix for Django
        html = html.replace('src="/assets/', 'src="/static/frontend/assets/')
        html = html.replace('href="/assets/', 'href="/static/frontend/assets/')
        return HttpResponse(html, content_type="text/html; charset=utf-8")

    # Fallback to template if build doesn't exist
    return render(request, "index.html")


@require_http_methods(["GET"])
def app_page(request: HttpRequest) -> HttpResponse:
    """Serve the Vue.js frontend application."""
    return index_page(request)


@require_http_methods(["GET"])
def chat_demo_page(request: HttpRequest) -> HttpResponse:
    try:
        html = CHAT_DEMO_FILE.read_text(encoding="utf-8")
    except OSError:
        return HttpResponse(
            "Failed to load chat demo page.",
            status=500,
            content_type="text/plain; charset=utf-8",
        )
    return HttpResponse(html, content_type="text/html; charset=utf-8")


def health_check(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"status": "healthy"})
