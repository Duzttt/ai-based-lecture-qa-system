import json
import os

import django
import httpx
import pytest
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_ask_qwen_success(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "trend one", "source": "Intelligent_Agent.pdf", "page": 7},
            {"text": "trend two", "source": "Intelligent_Agent.pdf", "page": 8},
        ],
    )

    class FakeOllamaClient:
        def __init__(self, host: str, timeout: int):
            self.host = host
            self.timeout = timeout

        def chat(self, model, messages, stream, keep_alive, options=None):
            return {
                "message": {
                    "content": "According to the materials, these five trends are ..."
                }
            }

    monkeypatch.setattr("django_app.views.OllamaClient", FakeOllamaClient)

    response = client.post(
        "/api/ask_qwen",
        data=json.dumps({"query": "What are the five trends?"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("According to the materials")
    assert data["sources"] == ["Intelligent_Agent.pdf"]
    assert len(data["source_snippets"]) == 2


def test_ask_qwen_timeout(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "trend one", "source": "Intelligent_Agent.pdf", "page": 7}
        ],
    )

    class FakeOllamaClient:
        def __init__(self, host: str, timeout: int):
            self.host = host
            self.timeout = timeout

        def chat(self, model, messages, stream, keep_alive, options=None):
            raise httpx.TimeoutException("timeout")

    monkeypatch.setattr("django_app.views.OllamaClient", FakeOllamaClient)

    response = client.post(
        "/api/ask_qwen",
        data=json.dumps({"query": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_ask_qwen_missing_query(client: Client):
    response = client.post(
        "/api/ask_qwen",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"
