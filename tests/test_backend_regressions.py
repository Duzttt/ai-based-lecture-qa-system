import os
from pathlib import Path
from unittest.mock import Mock

import django
import pytest
import requests
from django.http import JsonResponse
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from app.config import settings  # noqa: E402
from app.services.conversation_service import _call_llm_for_rewrite  # noqa: E402
from app.services.vector_store import VectorStore  # noqa: E402
from django_app.models import QueryLog  # noqa: E402
from django_app.views import helpers  # noqa: E402


@pytest.fixture
def client() -> Client:
    return Client()


@pytest.mark.parametrize(
    ("runtime_settings", "expected_kwargs"),
    [
        (
            {
                "provider": "local_llm",
                "model": "qwen2.5-3b",
                "api_key": None,
                "base_url": "http://localhost:8080",
            },
            {
                "provider": "local_llm",
                "model": "qwen2.5-3b",
                "base_url": "http://localhost:8080",
            },
        ),
        (
            {
                "provider": "openrouter",
                "model": "openrouter/free",
                "api_key": "test-key",
                "base_url": "https://openrouter.ai/api/v1",
            },
            {
                "provider": "openrouter",
                "model": "openrouter/free",
                "api_key": "test-key",
                "base_url": "https://openrouter.ai/api/v1",
            },
        ),
    ],
)
def test_call_llm_for_rewrite_uses_runtime_provider_settings(
    monkeypatch: pytest.MonkeyPatch,
    runtime_settings: dict,
    expected_kwargs: dict,
):
    call_llm_mock = Mock(return_value="rewritten question")
    monkeypatch.setattr(
        "app.services.conversation_service.load_runtime_llm_settings",
        lambda: runtime_settings,
    )
    monkeypatch.setattr("app.services.llm_client.call_llm", call_llm_mock)

    result = _call_llm_for_rewrite("Rewrite this follow-up")

    assert result == "rewritten question"
    call_kwargs = call_llm_mock.call_args.kwargs
    assert call_kwargs["provider"] == expected_kwargs["provider"]
    assert call_kwargs["model"] == expected_kwargs["model"]
    assert call_kwargs["call_type"] == "rewrite"
    assert call_kwargs["temperature"] == 0.0
    assert call_kwargs["timeout"] == 15
    assert call_kwargs["messages"] == [
        {"role": "user", "content": "Rewrite this follow-up"}
    ]
    assert call_kwargs["base_url"] == expected_kwargs["base_url"]
    if "api_key" in expected_kwargs:
        assert call_kwargs["api_key"] == expected_kwargs["api_key"]
    else:
        assert "api_key" not in call_kwargs


def test_load_rag_config_defaults_to_runtime_model(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
):
    monkeypatch.setattr(helpers, "RAG_CONFIG_FILE", tmp_path / "rag_config.json")
    monkeypatch.setattr(
        helpers,
        "load_runtime_llm_settings",
        lambda: {
            "provider": "openrouter",
            "model": "openrouter/free",
            "api_key": "test-key",
            "base_url": "https://openrouter.ai/api/v1",
        },
    )

    config = helpers._load_rag_config()

    assert config["llm_model"] == "openrouter/free"
    assert config["top_k"] == 3
    assert config["temperature"] == 0.7


def test_invalidate_index_dependent_caches_clears_vector_and_document_caches(
    monkeypatch: pytest.MonkeyPatch,
):
    cleared = {"vector": None, "documents": False}

    monkeypatch.setattr(
        VectorStore,
        "invalidate_cached",
        lambda index_path=None, embedding_dim=None: cleared.__setitem__(
            "vector", (index_path, embedding_dim)
        ),
    )
    monkeypatch.setattr(
        "django_app.views.suggestions._clear_document_cache",
        lambda: cleared.__setitem__("documents", True),
    )

    helpers._invalidate_index_dependent_caches()

    assert cleared["vector"] == (settings.FAISS_INDEX_PATH, None)
    assert cleared["documents"] is True


def test_ask_updates_existing_query_log(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    starting_count = QueryLog.objects.count()
    existing_log = QueryLog.objects.create(
        query="seed",
        latency_ms=1,
        llm_model="__test_model__",
        llm_provider="local_llm",
        call_type="qa",
    )

    monkeypatch.setattr(
        "django_app.views.rag._load_rag_config",
        lambda: {
            "llm_model": "__test_model__",
            "top_k": 3,
            "temperature": 0.7,
            "similarity_threshold": 0.6,
        },
    )
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "chunk text", "source": "lecture.pdf", "page": 1, "distance": 0.1}
        ],
    )
    monkeypatch.setattr(
        "django_app.views.rag.build_context_from_sources",
        lambda sources: "mock context",
    )
    monkeypatch.setattr(
        "django_app.views.rag.generate",
        lambda query, context, model=None, temperature=0.7, timeout_seconds=60, return_log=False, return_thinking=False: (
            "Final answer",
            existing_log.id,
        ),
    )

    response = client.post(
        "/api/chat",
        data='{"query": "[TEST_ONLY] What is covered?"}',
        content_type="application/json",
    )

    assert response.status_code == 200
    assert QueryLog.objects.count() == starting_count + 1

    existing_log.refresh_from_db()
    assert existing_log.query == "[TEST_ONLY] What is covered?"
    assert existing_log.results_count == 1
    assert existing_log.top_k == 3
    assert existing_log.answer_length == len("Final answer")


def test_ask_updates_existing_query_log_with_reasoning_and_log_id(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    starting_count = QueryLog.objects.count()
    existing_log = QueryLog.objects.create(
        query="seed",
        latency_ms=1,
        llm_model="__test_model__",
        llm_provider="local_llm",
        call_type="qa",
    )

    monkeypatch.setattr(
        "django_app.views.rag._load_rag_config",
        lambda: {
            "llm_model": "__test_model__",
            "top_k": 3,
            "temperature": 0.7,
            "similarity_threshold": 0.6,
        },
    )
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "chunk text", "source": "lecture.pdf", "page": 1, "distance": 0.1}
        ],
    )
    monkeypatch.setattr(
        "django_app.views.rag.build_context_from_sources",
        lambda sources: "mock context",
    )
    monkeypatch.setattr(
        "django_app.views.rag.generate",
        lambda query, context, model=None, temperature=0.7, timeout_seconds=60, return_log=False, return_thinking=False: (
            "Final answer",
            "internal reasoning",
            existing_log.id,
        ),
    )

    response = client.post(
        "/api/chat",
        data='{"query": "[TEST_ONLY] Explain this answer"}',
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["reasoning"] == "internal reasoning"
    assert QueryLog.objects.count() == starting_count + 1

    existing_log.refresh_from_db()
    assert existing_log.query == "[TEST_ONLY] Explain this answer"
    assert existing_log.results_count == 1
    assert existing_log.top_k == 3
    assert existing_log.answer_length == len("Final answer")


def test_providers_handler_loads_local_models_from_llamacpp(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "qwen2.5-3b",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )
    monkeypatch.setattr("django_app.views.rag._load_persisted_settings", lambda: {})

    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "data": [{"id": "qwen2.5-3b"}, {"id": "qwen3.5-4b"}]
    }
    monkeypatch.setattr(
        "django_app.views.rag.requests.get", lambda *args, **kwargs: mock_response
    )

    response = client.get("/api/settings/providers")

    assert response.status_code == 200
    payload = response.json()
    local_provider = next(p for p in payload["providers"] if p["id"] == "local_llm")
    assert local_provider["models"] == ["qwen2.5-3b", "qwen3.5-4b"]


def test_providers_handler_uses_local_base_url_when_current_provider_not_local(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "x",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        },
    )
    monkeypatch.setattr("django_app.views.rag._load_persisted_settings", lambda: {})

    called = {"url": ""}
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"data": [{"id": "qwen2.5-3b"}]}

    def fake_get(url, timeout=5):
        called["url"] = url
        return mock_response

    monkeypatch.setattr("django_app.views.rag.requests.get", fake_get)
    monkeypatch.setattr(
        "django_app.views.rag.settings.LOCAL_LLM_BASE_URL", "http://localhost:8080"
    )

    response = client.get("/api/settings/providers")

    assert response.status_code == 200
    assert called["url"] == "http://localhost:8080/v1/models"


def test_providers_handler_falls_back_to_default_local_model_when_llamacpp_down(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "x",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        },
    )
    monkeypatch.setattr("django_app.views.rag._load_persisted_settings", lambda: {})
    monkeypatch.setattr(
        "django_app.views.rag.settings.LOCAL_LLM_MODEL",
        "qwen2.5:3b",
    )

    def raise_connect_error(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("django_app.views.rag.requests.get", raise_connect_error)

    response = client.get("/api/settings/providers")

    assert response.status_code == 200
    payload = response.json()
    local_provider = next(p for p in payload["providers"] if p["id"] == "local_llm")
    assert local_provider["models"] == ["qwen2.5:3b"]


def test_chat_citations_endpoint_degrades_to_plain_chat(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag.ask",
        lambda request: JsonResponse(
            {
                "answer": "Plain answer",
                "retrieved_chunks": [
                    {
                        "text": "chunk text",
                        "source": "lecture.pdf",
                        "page": 2,
                    }
                ],
            }
        ),
    )

    response = client.post(
        "/api/chat/citations",
        data='{"query":"test"}',
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["sentences"][0]["text"] == "Plain answer"
    assert data["sentences"][0]["citations"] == []
    assert data["sources"]["1"]["file"] == "lecture.pdf"


def test_llm_health_handler_reports_disconnected(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "qwen2.5-3b",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )

    def raise_connect_error(*args, **kwargs):
        raise requests.ConnectionError("connection refused")

    monkeypatch.setattr("django_app.views.rag.requests.get", raise_connect_error)

    response = client.get("/api/health/llm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "disconnected"


def test_llm_health_handler_uses_requested_local_model(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "gemini",
            "model": "gemini-2.5-flash",
            "api_key": "x",
            "base_url": "https://generativelanguage.googleapis.com/v1beta",
        },
    )

    get_response = Mock()
    get_response.raise_for_status.return_value = None
    get_response.json.side_effect = [{"status": "ok"}, {"data": [{"id": "qwen-local"}]}]

    post_payload = {}
    post_response = Mock()
    post_response.raise_for_status.return_value = None
    post_response.json.return_value = {
        "choices": [{"message": {"content": "OK"}}]
    }

    def fake_post(url, json=None, timeout=20):
        post_payload.update(json or {})
        return post_response

    monkeypatch.setattr(
        "django_app.views.rag.requests.get", lambda *args, **kwargs: get_response
    )
    monkeypatch.setattr("django_app.views.rag.requests.post", fake_post)

    response = client.get("/api/health/llm?provider=local_llm&model=qwen-local")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
    assert payload["provider"] == "local_llm"
    assert payload["model"] == "qwen-local"
    assert post_payload["model"] == "qwen-local"


def test_llm_health_handler_reports_stalled_on_generation_timeout(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "qwen2.5-3b",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )

    ok_response = Mock()
    ok_response.raise_for_status.return_value = None
    ok_response.json.return_value = {"version": "0.20.3"}

    def fake_get(*args, **kwargs):
        return ok_response

    def timeout_post(*args, **kwargs):
        raise requests.Timeout("timed out")

    monkeypatch.setattr("django_app.views.rag.requests.get", fake_get)
    monkeypatch.setattr("django_app.views.rag.requests.post", timeout_post)

    response = client.get("/api/health/llm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "stalled"


def test_llm_health_handler_reports_healthy(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(
        "django_app.views.rag._build_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "qwen2.5-3b",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )

    get_response = Mock()
    get_response.raise_for_status.return_value = None
    get_response.json.side_effect = [{"status": "ok"}, {"data": [{"id": "qwen2.5-3b"}]}]

    post_response = Mock()
    post_response.raise_for_status.return_value = None
    post_response.json.return_value = {
        "choices": [{"message": {"content": "OK"}}]
    }

    monkeypatch.setattr(
        "django_app.views.rag.requests.get", lambda *args, **kwargs: get_response
    )
    monkeypatch.setattr(
        "django_app.views.rag.requests.post", lambda *args, **kwargs: post_response
    )

    response = client.get("/api/health/llm")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "healthy"
