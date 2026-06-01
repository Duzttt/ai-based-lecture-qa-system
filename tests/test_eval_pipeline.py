"""Tests for app.services.eval_pipeline."""
import pytest

from app.config import Settings
from app.services.eval_pipeline import resolve_endpoint, EvalPipelineError


def _make_settings(monkeypatch, **overrides) -> Settings:
    """Create a Settings instance with relevant env vars cleared, then apply overrides.

    We mutate the instance directly (via monkeypatch.setattr) because pydantic-settings
    reads env at construction time and ``LOCAL_LLM_*`` have non-None defaults, so
    setenv/delenv alone cannot produce a "fully unset" Settings.
    """
    for key in (
        "QA_GEN_BASE_URL", "QA_GEN_MODEL", "QA_GEN_TIMEOUT_SECONDS",
        "EVAL_BASE_URL", "EVAL_MODEL", "EVAL_TIMEOUT_SECONDS",
        "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    for k, v in overrides.items():
        monkeypatch.setattr(settings, k, v)
    return settings


def test_resolve_endpoint_cli_flag_wins(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        QA_GEN_BASE_URL="http://env:8080",
        QA_GEN_MODEL="env-model",
    )
    base_url, model = resolve_endpoint(
        phase="qa_gen", settings=settings,
        cli_base_url="http://cli:9090", cli_model="cli-model",
    )
    assert base_url == "http://cli:9090/v1"
    assert model == "cli-model"


def test_resolve_endpoint_env_var_falls_back(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        QA_GEN_BASE_URL="http://env:8080",
        QA_GEN_MODEL="env-model",
        LOCAL_LLM_BASE_URL="http://local:8080",
        LOCAL_LLM_MODEL="local-model",
    )
    base_url, model = resolve_endpoint(phase="qa_gen", settings=settings)
    assert base_url == "http://env:8080/v1"
    assert model == "env-model"


def test_resolve_endpoint_uses_local_llm_fallback(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL="http://local:8080",
        LOCAL_LLM_MODEL="local-model",
    )
    base_url, model = resolve_endpoint(phase="eval", settings=settings)
    assert base_url == "http://local:8080/v1"
    assert model == "local-model"


def test_resolve_endpoint_appends_v1(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL="http://local:8080",
        LOCAL_LLM_MODEL="m",
    )
    base_url, _ = resolve_endpoint(phase="qa_gen", settings=settings)
    assert base_url.endswith("/v1")


def test_resolve_endpoint_strips_trailing_v1_then_readds(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL="http://local:8080/v1/",
        LOCAL_LLM_MODEL="m",
    )
    base_url, _ = resolve_endpoint(phase="qa_gen", settings=settings)
    assert base_url == "http://local:8080/v1"


def test_resolve_endpoint_raises_when_unset(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL=None,
        LOCAL_LLM_MODEL=None,
    )
    with pytest.raises(EvalPipelineError):
        resolve_endpoint(phase="eval", settings=settings)
