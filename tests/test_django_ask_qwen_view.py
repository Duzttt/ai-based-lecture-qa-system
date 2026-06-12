import json

import httpx
import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    return Client()


def test_ask_qwen_success(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.chat.retrieve_with_faiss",
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
            return {"message": {"content": "根据资料，这五个趋势是 ..."}}

    monkeypatch.setattr("django_app.views.chat.OllamaClient", FakeOllamaClient)

    response = client.post(
        "/api/ask_qwen",
        data=json.dumps({"query": "What are the five trends?"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("根据资料")
    assert data["sources"] == ["Intelligent_Agent.pdf"]
    assert len(data["source_snippets"]) == 2


def test_ask_qwen_timeout(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.chat.retrieve_with_faiss",
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

    monkeypatch.setattr("django_app.views.chat.OllamaClient", FakeOllamaClient)

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
