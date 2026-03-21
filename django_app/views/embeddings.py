import json
from pathlib import Path
from typing import Any, Dict

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import (
    INDEXING_STATUS_RUNNING,
    _enqueue_full_rebuild,
    _error_response,
    _get_json_body,
    _get_upload_indexing_state,
)

EMBEDDING_MODEL_SETTINGS_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "embedding_model_settings.json"
)


def _load_embedding_model_settings() -> Dict[str, Any]:
    default_settings = {
        "current_model": settings.EMBEDDING_MODEL,
        "model_cache": [],
    }

    if not EMBEDDING_MODEL_SETTINGS_FILE.exists():
        return default_settings

    try:
        with EMBEDDING_MODEL_SETTINGS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {**default_settings, **data}
    except (OSError, json.JSONDecodeError):
        pass

    return default_settings


def _save_embedding_model_settings(data: Dict[str, Any]) -> None:
    EMBEDDING_MODEL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EMBEDDING_MODEL_SETTINGS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@require_http_methods(["GET"])
def list_embedding_models(request: HttpRequest) -> JsonResponse:
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()
        models = manager.get_available_models()
        cache_stats = manager.get_cache_stats()

        return JsonResponse(
            {
                "models": models,
                "cache_stats": cache_stats,
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to load models: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_current_embedding_model(request: HttpRequest) -> JsonResponse:
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()
        current_id = manager.get_current_model_id()
        model_info = manager.AVAILABLE_MODELS.get(current_id, {})

        cache_stats = manager.get_cache_stats()
        is_loaded = current_id in cache_stats.get("cached_models", [])

        return JsonResponse(
            {
                "model_id": current_id,
                "model_name": model_info.get("name", current_id),
                "dimension": model_info.get("dimension", 384),
                "speed": model_info.get("speed", "Unknown"),
                "memory": model_info.get("memory", "Unknown"),
                "is_loaded": is_loaded,
                "recommended": model_info.get("recommended", False),
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to get current model: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def switch_embedding_model(request: HttpRequest) -> JsonResponse:
    from app.services.embedding_manager import get_embedding_manager

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    model_id = str(payload.get("model_id", "")).strip()
    reindex = bool(payload.get("reindex", False))

    if not model_id:
        return _error_response("model_id is required", status=400)

    try:
        manager = get_embedding_manager()

        if model_id not in manager.AVAILABLE_MODELS:
            return _error_response(f"Unknown model: {model_id}", status=400)

        result = manager.set_current_model(model_id)

        saved_settings = _load_embedding_model_settings()
        saved_settings["current_model"] = model_id
        _save_embedding_model_settings(saved_settings)

        if reindex:
            current_state = _get_upload_indexing_state()
            if current_state["status"] != INDEXING_STATUS_RUNNING:
                _enqueue_full_rebuild(uploaded_filename="model_switch_reindex")
                result["reindex_status"] = "started"
            else:
                result["reindex_status"] = "already_running"
        else:
            result["reindex_status"] = "not_requested"

        return JsonResponse(
            {
                "success": True,
                **result,
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to switch model: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def test_embedding_model(request: HttpRequest) -> JsonResponse:
    from app.services.embedding_manager import get_embedding_manager

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    model_id = str(payload.get("model_id", "")).strip()
    query = str(payload.get("query", "test query")).strip()
    top_k = int(payload.get("top_k", 3))

    if not model_id:
        return _error_response("model_id is required", status=400)

    if not query:
        return _error_response("query cannot be empty", status=400)

    try:
        manager = get_embedding_manager()

        if model_id not in manager.AVAILABLE_MODELS:
            return _error_response(f"Unknown model: {model_id}", status=400)

        result = manager.test_model(model_id, query, top_k=top_k)

        return JsonResponse(
            {
                "success": True,
                **result,
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to test model: {str(exc)}", status=500)


@require_http_methods(["GET"])
def get_embedding_model_metrics(request: HttpRequest) -> JsonResponse:
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()

        metrics = manager.get_performance_metrics(limit=50)

        model_stats: Dict[str, Dict[str, Any]] = {}
        for metric in metrics:
            model_id = metric["model_id"]
            if model_id not in model_stats:
                model_stats[model_id] = {
                    "count": 0,
                    "total_time_ms": 0,
                    "actions": {},
                }

            model_stats[model_id]["count"] += 1
            model_stats[model_id]["total_time_ms"] += metric["time_ms"]

            action = metric["action"]
            if action not in model_stats[model_id]["actions"]:
                model_stats[model_id]["actions"][action] = {
                    "count": 0,
                    "total_time_ms": 0,
                }
            model_stats[model_id]["actions"][action]["count"] += 1
            model_stats[model_id]["actions"][action]["total_time_ms"] += metric[
                "time_ms"
            ]

        for model_id, stats in model_stats.items():
            stats["avg_time_ms"] = (
                round(stats["total_time_ms"] / stats["count"], 2)
                if stats["count"] > 0
                else 0
            )

            for action, action_stats in stats["actions"].items():
                action_stats["avg_time_ms"] = (
                    round(action_stats["total_time_ms"] / action_stats["count"], 2)
                    if action_stats["count"] > 0
                    else 0
                )

        return JsonResponse(
            {
                "metrics": metrics,
                "model_stats": model_stats,
                "cache_stats": manager.get_cache_stats(),
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to get metrics: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def clear_embedding_model_cache(request: HttpRequest) -> JsonResponse:
    from app.services.embedding_manager import get_embedding_manager

    try:
        manager = get_embedding_manager()
        manager.clear_cache()

        return JsonResponse(
            {
                "success": True,
                "message": "Model cache cleared",
            }
        )
    except Exception as exc:
        return _error_response(f"Failed to clear cache: {str(exc)}", status=500)
