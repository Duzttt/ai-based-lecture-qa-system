import json
from pathlib import Path
from typing import Dict, Optional

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from ._helpers import (
    SETTINGS_FILE,
    VALID_PROVIDERS,
    _error_response,
    _get_json_body,
    _load_persisted_settings,
    _load_rag_config,
    _save_rag_config,
)


@csrf_exempt
@require_http_methods(["GET", "POST"])
def settings_handler(request: HttpRequest) -> JsonResponse:
    if request.method == "GET":
        stored_settings = _load_persisted_settings()
        provider = stored_settings.get("provider") or settings.LLM_PROVIDER
        if provider not in VALID_PROVIDERS:
            provider = settings.LLM_PROVIDER

        if provider == "gemini":
            default_model = settings.GEMINI_MODEL
            default_key = settings.GEMINI_API_KEY
        else:
            default_model = "anthropic/claude-3-haiku"
            default_key = settings.OPENROUTER_API_KEY

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
    api_key: Optional[str]
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

    data_to_store: Dict[str, Optional[str]] = {
        "provider": provider,
        "model": model,
        "api_key": api_key,
    }

    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with SETTINGS_FILE.open("w", encoding="utf-8") as settings_file:
            json.dump(data_to_store, settings_file)
    except OSError as exc:
        return _error_response(f"Failed to save settings: {str(exc)}", status=500)

    return JsonResponse({"success": True, "message": "Settings updated"})


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
