import json
import os

import django
import pytest
from unittest.mock import Mock
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_ask_success(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "trend one", "source": "Intelligent_Agent.pdf", "page": 7},
            {"text": "trend two", "source": "Intelligent_Agent.pdf", "page": 8},
        ],
    )

    def fake_call_llm(*args, **kwargs):
        return "According to the materials, these five trends are ..."

    monkeypatch.setattr("app.services.local_rag.call_llm", fake_call_llm)

    response = client.post(
        "/api/chat",
        data=json.dumps({"query": "What are the five trends?"}),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"].startswith("According to the materials")
    assert data["sources"] == ["Intelligent_Agent.pdf"]
    assert len(data["source_snippets"]) == 2


def test_ask_timeout(client: Client, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        "django_app.views.rag.retrieve_with_faiss",
        lambda query, top_k=3, source_filter=None: [
            {"text": "trend one", "source": "Intelligent_Agent.pdf", "page": 7}
        ],
    )

    import requests

    def fake_call_llm(*args, **kwargs):
        raise requests.Timeout("timeout")

    monkeypatch.setattr("app.services.local_rag.call_llm", fake_call_llm)

    response = client.post(
        "/api/chat",
        data=json.dumps({"query": "test"}),
        content_type="application/json",
    )

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"].lower()


def test_ask_missing_query(client: Client):
    response = client.post(
        "/api/chat",
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"
