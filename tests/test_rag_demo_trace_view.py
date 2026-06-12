import os

import django
import pytest
from django.test import Client

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


@pytest.fixture
def client() -> Client:
    return Client()


def test_rag_demo_trace_rejects_empty_query(client: Client):
    response = client.post(
        "/api/rag-demo/trace",
        data='{"query": "   "}',
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Query cannot be empty"


def test_rag_demo_trace_returns_service_payload(
    client: Client,
    monkeypatch: pytest.MonkeyPatch,
):
    captured = {}

    def fake_build_rag_demo_trace(query, source_filter=None, top_k=5, include_answer=True):
        captured["query"] = query
        captured["source_filter"] = source_filter
        captured["top_k"] = top_k
        captured["include_answer"] = include_answer
        return {
            "trace_id": "trace_test",
            "query": query,
            "stages": [
                {
                    "id": "user_question",
                    "title": "User Question",
                    "status": "completed",
                    "duration_ms": 0,
                    "summary": "The demo starts from the user question.",
                }
            ],
            "retrieved_chunks": [],
            "context_preview": "",
            "answer": "",
            "total_duration_ms": 1,
        }

    monkeypatch.setattr(
        "django_app.views.rag_demo.build_rag_demo_trace",
        fake_build_rag_demo_trace,
    )

    response = client.post(
        "/api/rag-demo/trace",
        data='{"query": "Explain RAG", "sources": ["lecture.pdf"], "top_k": 4, "include_answer": false}',
        content_type="application/json",
    )

    assert response.status_code == 200
    assert response.json()["trace_id"] == "trace_test"
    assert captured == {
        "query": "Explain RAG",
        "source_filter": ["lecture.pdf"],
        "top_k": 4,
        "include_answer": False,
    }
