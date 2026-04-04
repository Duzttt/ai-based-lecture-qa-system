import os
from pathlib import Path
from unittest.mock import Mock

import django
import pytest
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
                "model": "qwen2.5:3b",
                "api_key": None,
                "base_url": "http://localhost:11434",
            },
            {
                "provider": "local_llm",
                "model": "qwen2.5:3b",
                "base_url": "http://localhost:11434",
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

    assert cleared["vector"] == (settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM)
    assert cleared["documents"] is True


def test_ask_qwen_updates_existing_query_log(
    client: Client, monkeypatch: pytest.MonkeyPatch
):
    starting_count = QueryLog.objects.count()
    existing_log = QueryLog.objects.create(
        query="seed",
        latency_ms=1,
        llm_model="openrouter/free",
        llm_provider="openrouter",
        call_type="qa",
    )

    monkeypatch.setattr(
        "django_app.views.rag._load_rag_config",
        lambda: {
            "llm_model": "openrouter/free",
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
        lambda query,
        context,
        model=None,
        temperature=0.7,
        timeout_seconds=60,
        return_log=False: ("Final answer", existing_log.id),
    )

    response = client.post(
        "/api/ask_qwen",
        data='{"query": "What is covered?"}',
        content_type="application/json",
    )

    assert response.status_code == 200
    assert QueryLog.objects.count() == starting_count + 1

    existing_log.refresh_from_db()
    assert existing_log.query == "What is covered?"
    assert existing_log.results_count == 1
    assert existing_log.top_k == 3
    assert existing_log.answer_length == len("Final answer")
