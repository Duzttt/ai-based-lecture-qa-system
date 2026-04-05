"""Helpers for resolving runtime LLM settings."""

import json
from pathlib import Path
from typing import Dict, Optional

from app.config import settings

VALID_PROVIDERS = {"gemini", "openrouter", "local_llm"}
SETTINGS_FILE = Path(__file__).resolve().parents[2] / "data" / "settings.json"


def resolve_gemini_api_model(*candidates: Optional[str]) -> str:
    """First candidate containing 'gemini' wins; else ``settings.GEMINI_MODEL``."""
    for candidate in candidates:
        name = str(candidate or "").strip()
        if name and "gemini" in name.lower():
            return name
    return settings.GEMINI_MODEL


def get_default_model_for_provider(provider: str) -> str:
    """Return the default model for the requested provider."""
    if provider == "gemini":
        return settings.GEMINI_MODEL
    if provider == "openrouter":
        return settings.OPENROUTER_MODEL
    return settings.LOCAL_LLM_MODEL


def get_default_api_key_for_provider(provider: str) -> Optional[str]:
    """Return the default API key for the requested provider, if any."""
    if provider == "gemini":
        return settings.GEMINI_API_KEY
    if provider == "openrouter":
        return settings.OPENROUTER_API_KEY
    return None


def get_base_url_for_provider(provider: str) -> str:
    """Return the base URL for the requested provider."""
    if provider == "gemini":
        return settings.GEMINI_BASE_URL
    if provider == "openrouter":
        return settings.OPENROUTER_BASE_URL
    return settings.LOCAL_LLM_BASE_URL


def load_runtime_llm_settings() -> Dict[str, Optional[str]]:
    """Resolve the active provider/model/api key from persisted runtime settings."""
    persisted: Dict[str, Optional[str]] = {}
    if SETTINGS_FILE.exists():
        try:
            with SETTINGS_FILE.open("r", encoding="utf-8") as settings_file:
                data = json.load(settings_file)
            if isinstance(data, dict):
                persisted = data
        except (OSError, json.JSONDecodeError):
            persisted = {}

    provider = str(persisted.get("provider") or settings.LLM_PROVIDER).strip().lower()
    if provider not in VALID_PROVIDERS:
        provider = settings.LLM_PROVIDER

    default_model = get_default_model_for_provider(provider)
    model = str(persisted.get("model") or default_model).strip() or default_model
    # Ollama-style names (e.g. qwen2.5:3b) in persisted settings after switching
    # from local_llm would otherwise be sent to the Generative Language API (404).
    if provider == "gemini" and "gemini" not in model.lower():
        model = default_model

    raw_api_key = persisted.get("api_key")
    api_key: Optional[str]
    if raw_api_key is None:
        api_key = get_default_api_key_for_provider(provider)
    else:
        normalized = str(raw_api_key).strip()
        api_key = normalized or None

    return {
        "provider": provider,
        "model": model,
        "api_key": api_key,
        "base_url": get_base_url_for_provider(provider),
    }


__all__ = [
    "SETTINGS_FILE",
    "VALID_PROVIDERS",
    "get_base_url_for_provider",
    "get_default_api_key_for_provider",
    "get_default_model_for_provider",
    "load_runtime_llm_settings",
    "resolve_gemini_api_model",
]
