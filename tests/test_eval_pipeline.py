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


from app.services.eval_pipeline import _parse_qa_json, _call_chat


def test_parse_qa_json_strips_markdown_fences():
    raw = '```json\n[{"question": "q", "ground_truth": "a"}]\n```'
    assert _parse_qa_json(raw) == [{"question": "q", "ground_truth": "a"}]


def test_parse_qa_json_extracts_array_from_extra_text():
    raw = 'Here you go: [{"question": "q1", "ground_truth": "a1"}] enjoy!'
    assert _parse_qa_json(raw) == [{"question": "q1", "ground_truth": "a1"}]


def test_parse_qa_json_repairs_truncated_array():
    raw = '[{"question": "q1", "ground_truth": "a1"}, {"question": "q2", "ground_trut'
    result = _parse_qa_json(raw)
    assert isinstance(result, list)


def test_parse_qa_json_raises_on_garbage():
    with pytest.raises(ValueError):
        _parse_qa_json("not json at all")


def test_call_chat_posts_to_v1_chat_completions(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return R()

    monkeypatch.setattr("app.services.eval_pipeline.requests.post", fake_post)
    text = _call_chat(
        base_url="http://x:8080",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        timeout=10,
    )
    assert text == "ok"
    assert captured["url"] == "http://x:8080/v1/chat/completions"
    assert captured["json"]["model"] == "m"
    assert captured["timeout"] == 10


def test_call_chat_raises_on_empty_choices(monkeypatch):
    def fake_post(url, json, timeout):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": []}

        return R()

    monkeypatch.setattr("app.services.eval_pipeline.requests.post", fake_post)
    with pytest.raises(ValueError):
        _call_chat(
            base_url="http://x:8080",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            timeout=10,
        )
