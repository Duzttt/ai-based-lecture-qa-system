"""Tests for runtime LLM settings resolution."""

import json

import pytest


def test_load_runtime_llm_replaces_non_gemini_model_when_provider_gemini(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.config import settings
    from app.services import runtime_llm

    fake_file = tmp_path / "settings.json"
    fake_file.write_text(
        json.dumps({"provider": "gemini", "model": "qwen2.5:3b"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_llm, "SETTINGS_FILE", fake_file)

    resolved = runtime_llm.load_runtime_llm_settings()

    assert resolved["provider"] == "gemini"
    assert "gemini" in str(resolved["model"]).lower()
    assert resolved["model"] == settings.GEMINI_MODEL


def test_load_runtime_llm_keeps_gemini_model_name(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.services import runtime_llm

    fake_file = tmp_path / "settings.json"
    fake_file.write_text(
        json.dumps({"provider": "gemini", "model": "gemini-2.5-flash"}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_llm, "SETTINGS_FILE", fake_file)

    resolved = runtime_llm.load_runtime_llm_settings()

    assert resolved["model"] == "gemini-2.5-flash"


def test_resolve_gemini_api_model_picks_first_gemini_named_candidate() -> None:
    from app.services.runtime_llm import resolve_gemini_api_model

    assert (
        resolve_gemini_api_model("qwen2.5:3b", "gemini-2.5-flash") == "gemini-2.5-flash"
    )
    assert resolve_gemini_api_model("gemini-pro", "gemini-2.5-flash") == "gemini-pro"
