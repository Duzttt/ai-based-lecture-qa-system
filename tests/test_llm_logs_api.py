import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import uuid

import pytest
from django.test import Client

from django_app.models import QueryLog


@pytest.fixture
def client() -> Client:
    return Client()


def _make_unique_query() -> str:
    return f"test_llm_logs_{uuid.uuid4().hex[:12]}"


def test_llm_logs_list_returns_records(client: Client):
    query = _make_unique_query()
    QueryLog.objects.create(
        query=query,
        latency_ms=100,
        llm_provider="gemini",
        llm_status="success",
        call_type="qa",
    )
    QueryLog.objects.create(
        query=query,
        latency_ms=200,
        llm_provider="openrouter",
        llm_status="error",
        call_type="summary",
    )

    response = client.get("/api/llm-logs/")
    assert response.status_code == 200
    data = response.json()
    records = [r for r in data["records"] if r["query"] == query]
    assert len(records) == 2


def test_llm_logs_filter_by_provider(client: Client):
    query = _make_unique_query()
    QueryLog.objects.create(
        query=query, latency_ms=100, llm_provider="gemini", call_type="qa"
    )
    QueryLog.objects.create(
        query=query, latency_ms=200, llm_provider="openrouter", call_type="qa"
    )

    response = client.get("/api/llm-logs/?provider=gemini")
    data = response.json()
    records = [r for r in data["records"] if r["query"] == query]
    assert len(records) == 1
    assert records[0]["llm_provider"] == "gemini"


def test_llm_logs_filter_by_call_type(client: Client):
    query = _make_unique_query()
    QueryLog.objects.create(
        query=query, latency_ms=100, llm_provider="gemini", call_type="qa"
    )
    QueryLog.objects.create(
        query=query, latency_ms=200, llm_provider="gemini", call_type="summary"
    )

    response = client.get("/api/llm-logs/?call_type=summary")
    data = response.json()
    records = [r for r in data["records"] if r["query"] == query]
    assert len(records) == 1
    assert records[0]["call_type"] == "summary"


def test_llm_logs_pagination(client: Client):
    query = _make_unique_query()
    for i in range(5):
        QueryLog.objects.create(
            query=f"{query}_{i}", latency_ms=100, llm_provider="gemini", call_type="qa"
        )

    response = client.get("/api/llm-logs/?page=1&page_size=2")
    data = response.json()
    records = [r for r in data["records"] if r["query"].startswith(query)]
    assert len(records) == 2
    assert data["page"] == 1


def test_llm_logs_stats(client: Client):
    query = _make_unique_query()
    QueryLog.objects.create(
        query=f"{query}_a",
        latency_ms=100,
        llm_provider="gemini",
        llm_status="success",
        call_type="qa",
    )
    QueryLog.objects.create(
        query=f"{query}_b",
        latency_ms=300,
        llm_provider="gemini",
        llm_status="success",
        call_type="qa",
    )
    QueryLog.objects.create(
        query=f"{query}_c",
        latency_ms=200,
        llm_provider="openrouter",
        llm_status="error",
        call_type="summary",
    )

    response = client.get("/api/llm-logs/stats/")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_calls"] >= 3
    assert stats["error_count"] >= 1
    assert "avg_latency_ms" in stats
    assert "by_provider" in stats
    assert stats["by_provider"].get("gemini", 0) >= 2
    assert stats["by_provider"].get("openrouter", 0) >= 1


def test_llm_logs_page_renders(client: Client):
    response = client.get("/llm-logs")
    assert response.status_code == 200
