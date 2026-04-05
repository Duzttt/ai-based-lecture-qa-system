"""Tests for the runtime embedding settings resolver."""

import json
import os
from pathlib import Path

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from app.config import settings  # noqa: E402
from app.services import runtime_embedding  # noqa: E402
from app.services.runtime_embedding import (  # noqa: E402
    load_runtime_embedding_settings,
    save_embedding_model_settings,
)


@pytest.fixture()
def tmp_settings_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Redirect the settings file to a temp directory."""
    file = tmp_path / "embedding_model_settings.json"
    monkeypatch.setattr(runtime_embedding, "EMBEDDING_MODEL_SETTINGS_FILE", file)
    return file


class TestLoadRuntimeEmbeddingSettings:
    def test_defaults_when_no_file(self, tmp_settings_file: Path):
        result = load_runtime_embedding_settings()
        assert result["model_id"] == settings.EMBEDDING_MODEL
        assert result["embedding_dim"] == settings.EMBEDDING_DIM

    def test_reads_persisted_model(self, tmp_settings_file: Path):
        tmp_settings_file.write_text(
            json.dumps({"current_model": "BAAI/bge-large-en-v1.5"})
        )
        result = load_runtime_embedding_settings()
        assert result["model_id"] == "BAAI/bge-large-en-v1.5"
        assert result["embedding_dim"] == 1024

    def test_falls_back_on_unknown_model(self, tmp_settings_file: Path):
        tmp_settings_file.write_text(
            json.dumps({"current_model": "unknown/model-xyz"})
        )
        result = load_runtime_embedding_settings()
        assert result["model_id"] == settings.EMBEDDING_MODEL
        assert result["embedding_dim"] == settings.EMBEDDING_DIM

    def test_falls_back_on_corrupt_json(self, tmp_settings_file: Path):
        tmp_settings_file.write_text("{bad json")
        result = load_runtime_embedding_settings()
        assert result["model_id"] == settings.EMBEDDING_MODEL

    def test_falls_back_on_empty_current_model(self, tmp_settings_file: Path):
        tmp_settings_file.write_text(json.dumps({"current_model": ""}))
        result = load_runtime_embedding_settings()
        assert result["model_id"] == settings.EMBEDDING_MODEL

    def test_all_registered_models_resolve(self, tmp_settings_file: Path):
        from app.services.embedding_manager import EmbeddingModelManager

        for model_id, meta in EmbeddingModelManager.AVAILABLE_MODELS.items():
            tmp_settings_file.write_text(
                json.dumps({"current_model": model_id})
            )
            result = load_runtime_embedding_settings()
            assert result["model_id"] == model_id
            assert result["embedding_dim"] == meta["dimension"]


class TestSaveEmbeddingModelSettings:
    def test_creates_file(self, tmp_settings_file: Path):
        save_embedding_model_settings({"current_model": "test/model"})
        assert tmp_settings_file.exists()
        data = json.loads(tmp_settings_file.read_text())
        assert data["current_model"] == "test/model"

    def test_round_trip(self, tmp_settings_file: Path):
        payload = {"current_model": "BAAI/bge-small-en-v1.5", "model_cache": []}
        save_embedding_model_settings(payload)
        result = load_runtime_embedding_settings()
        assert result["model_id"] == "BAAI/bge-small-en-v1.5"
        assert result["embedding_dim"] == 384
