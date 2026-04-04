import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

import django

django.setup()

import pytest
from unittest.mock import patch, MagicMock

from django_app.models import QueryLog


@pytest.mark.django_db
def test_call_llm_success_openrouter():
    from app.services.llm_client import call_llm

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Hello world"}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.services.llm_client.requests.post", return_value=mock_response):
        result = call_llm(
            provider="openrouter",
            model="test-model",
            call_type="qa",
            messages=[{"role": "user", "content": "hi"}],
            api_key="fake-key",
            base_url="https://fake.api",
        )

    assert result == "Hello world"
    log = QueryLog.objects.latest("created_at")
    assert log.llm_provider == "openrouter"
    assert log.llm_status == "success"
    assert log.call_type == "qa"
    assert log.llm_model == "test-model"
    assert log.latency_ms >= 0
    assert log.error_message == ""


@pytest.mark.django_db
def test_call_llm_success_gemini():
    from app.services.llm_client import call_llm

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}]
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.services.llm_client.requests.post", return_value=mock_response):
        result = call_llm(
            provider="gemini",
            model="gemini-2.5-flash",
            call_type="summary",
            messages=[{"role": "user", "content": "summarize"}],
            api_key="fake-key",
            base_url="https://fake.api",
        )

    assert result == "Gemini response"
    log = QueryLog.objects.latest("created_at")
    assert log.llm_provider == "gemini"
    assert log.llm_status == "success"


@pytest.mark.django_db
def test_call_llm_success_local_llm():
    from app.services.llm_client import call_llm

    mock_response = MagicMock()
    mock_response.json.return_value = {"message": {"content": "Local LLM response"}}
    mock_response.raise_for_status.return_value = None

    with patch("app.services.llm_client.requests.post", return_value=mock_response):
        result = call_llm(
            provider="local_llm",
            model="qwen2.5:3b",
            call_type="citation",
            messages=[{"role": "user", "content": "cite"}],
            base_url="http://localhost:11434",
        )

    assert result == "Local LLM response"
    log = QueryLog.objects.latest("created_at")
    assert log.llm_provider == "local_llm"
    assert log.call_type == "citation"


@pytest.mark.django_db
def test_call_llm_error_logs_and_reraises():
    from app.services.llm_client import call_llm

    with patch(
        "app.services.llm_client.requests.post",
        side_effect=Exception("Connection refused"),
    ):
        with pytest.raises(Exception, match="Connection refused"):
            call_llm(
                provider="gemini",
                model="gemini-2.5-flash",
                call_type="summary",
                messages=[{"role": "user", "content": "summarize"}],
                api_key="fake-key",
                base_url="https://fake.api",
            )

    log = QueryLog.objects.latest("created_at")
    assert log.llm_provider == "gemini"
    assert log.llm_status == "error"
    assert "Connection refused" in log.error_message


@pytest.mark.django_db
def test_call_llm_unsupported_provider():
    from app.services.llm_client import call_llm

    with pytest.raises(ValueError, match="Unsupported provider"):
        call_llm(
            provider="unknown",
            model="test",
            call_type="qa",
            messages=[{"role": "user", "content": "hi"}],
        )
