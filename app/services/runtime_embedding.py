"""Helpers for resolving the active embedding model at runtime.

Reads persisted settings from ``data/embedding_model_settings.json`` and
looks up the corresponding dimension from the model registry in
:class:`~app.services.embedding_manager.EmbeddingModelManager`.
Falls back to the static ``settings.EMBEDDING_MODEL`` / ``EMBEDDING_DIM``
when the file is missing or contains an unknown model.
"""

import json
from pathlib import Path
from typing import Any, Dict

from app.config import settings

EMBEDDING_MODEL_SETTINGS_FILE = (
    Path(__file__).resolve().parents[2] / "data" / "embedding_model_settings.json"
)


def _load_embedding_model_settings_raw() -> Dict[str, Any]:
    """Read the persisted JSON file and return it as a dict (or empty)."""
    if not EMBEDDING_MODEL_SETTINGS_FILE.exists():
        return {}
    try:
        with EMBEDDING_MODEL_SETTINGS_FILE.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {}


def save_embedding_model_settings(data: Dict[str, Any]) -> None:
    EMBEDDING_MODEL_SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with EMBEDDING_MODEL_SETTINGS_FILE.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)


def _get_available_models_registry() -> Dict[str, Dict[str, Any]]:
    """Return the AVAILABLE_MODELS registry without importing SentenceTransformer."""
    from app.services.embedding_manager import EmbeddingModelManager

    return EmbeddingModelManager.AVAILABLE_MODELS


def load_runtime_embedding_settings() -> Dict[str, Any]:
    """Resolve the active embedding model id and dimension.

    Returns a dict with keys ``model_id`` and ``embedding_dim``.
    """
    persisted = _load_embedding_model_settings_raw()
    registry = _get_available_models_registry()

    model_id = str(persisted.get("current_model") or "").strip()
    if model_id and model_id in registry:
        embedding_dim = registry[model_id]["dimension"]
    else:
        model_id = settings.EMBEDDING_MODEL
        meta = registry.get(model_id)
        embedding_dim = meta["dimension"] if meta else settings.EMBEDDING_DIM

    return {
        "model_id": model_id,
        "embedding_dim": embedding_dim,
    }


__all__ = [
    "EMBEDDING_MODEL_SETTINGS_FILE",
    "load_runtime_embedding_settings",
    "save_embedding_model_settings",
]
