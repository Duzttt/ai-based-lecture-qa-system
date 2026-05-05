import json
import os

import django
import pytest
import requests
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_ask_view_success(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {
                "text": "Trends include ubiquity...",
                "source": "Intelligent_Agent.pdf",
                "page": 7,
            },
            {
                "text": "Trends include interconnection...",
                "source": "Intelligent_Agent.pdf",
                "page": 8,
            },
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
        timeout_seconds=60: "According to Intelligent_Agent.pdf page 7, the five trends are...",
    )

    response = client.post(
        "/api/ask",
        data=json.dumps({"query": "What are the five trends in this document?"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("According to Intelligent_Agent.pdf page 7")
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
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "chunk", "source": "a.pdf", "page": 1}
        ],
    )
    monkeypatch.setattr(
        "django_app.views.rag.build_context_from_sources",
        lambda sources: "mock context",
    )

    def _raise_timeout(query, context, model=None, temperature=0.7, timeout_seconds=60):
        raise requests.exceptions.Timeout("timeout")

    monkeypatch.setattr("django_app.views.rag.generate", _raise_timeout)

    response = client.post(
        "/api/ask",
        data=json.dumps({"query": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()
