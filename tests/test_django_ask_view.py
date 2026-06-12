import json

import pytest
from django.test import Client


@pytest.fixture
def client() -> Client:
    return Client()


def test_ask_view_success(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.chat.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {
                "text": "趋势包括 ubiquity...",
                "source": "Intelligent_Agent.pdf",
                "page": 7,
            },
            {
                "text": "趋势包括 interconnection...",
                "source": "Intelligent_Agent.pdf",
                "page": 8,
            },
        ],
    )
    monkeypatch.setattr(
        "django_app.views.chat.build_context_from_sources",
        lambda sources: "mock context",
    )
    monkeypatch.setattr(
        "django_app.views.chat.generate_with_local_qwen",
        lambda query, context: "根据《Intelligent_Agent.pdf》第7页，五个趋势是……",
    )

    response = client.post(
        "/api/ask",
        data=json.dumps({"query": "这份文档的五个趋势是什么？"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("根据《Intelligent_Agent.pdf》第7页")
    assert data["sources"] == ["Intelligent_Agent.pdf"]
    assert len(data["source_snippets"]) == 2


def test_ask_view_missing_query(client: Client):
    response = client.post(
        "/api/ask",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"


def test_ask_view_timeout(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.chat.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "chunk", "source": "a.pdf", "page": 1}
        ],
    )
    monkeypatch.setattr(
        "django_app.views.chat.build_context_from_sources",
        lambda sources: "mock context",
    )

    def _raise_timeout(query, context, **kwargs):
        raise httpx.TimeoutException("timeout")

    import httpx
    monkeypatch.setattr("django_app.views.chat.generate_with_local_qwen", _raise_timeout)

    response = client.post(
        "/api/ask",
        data=json.dumps({"query": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
