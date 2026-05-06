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
def test_call_llm_returns_log_id_with_thinking_when_both_flags_enabled():
    from app.services.llm_client import call_llm

    mock_response = MagicMock()
    mock_response.json.return_value = {
        "message": {
            "content": "Local LLM response",
            "thinking": "internal reasoning",
        }
    }
    mock_response.raise_for_status.return_value = None

    with patch("app.services.llm_client.requests.post", return_value=mock_response):
        result = call_llm(
            provider="local_llm",
            model="qwen3:8b",
            call_type="qa",
            messages=[{"role": "user", "content": "Explain this"}],
            query_text="Explain this",
            base_url="http://localhost:11434",
            return_log=True,
            return_thinking=True,
        )

    assert isinstance(result, tuple)
    assert len(result) == 3
    answer, thinking, log_id = result
    assert answer == "Local LLM response"
    assert thinking == "internal reasoning"
    assert isinstance(log_id, int)

    log = QueryLog.objects.get(id=log_id)
    assert log.query == "Explain this"
    assert log.llm_provider == "local_llm"
    assert log.llm_status == "success"


@pytest.mark.django_db
def test_call_llm_local_llm_falls_back_to_generate_on_chat_value_error():
    from app.services.llm_client import call_llm

    chat_response = MagicMock()
    chat_response.raise_for_status.return_value = None
    chat_response.json.return_value = {"message": {"role": "assistant", "content": ""}}

    generate_response = MagicMock()
    generate_response.raise_for_status.return_value = None
    generate_response.json.return_value = {"response": "Fallback local response"}

    with patch(
        "app.services.llm_client.requests.post",
        side_effect=[chat_response, generate_response],
    ) as mocked_post:
        result = call_llm(
            provider="local_llm",
            model="gemma4:latest",
            call_type="citation",
            messages=[
                {"role": "system", "content": "You are helpful"},
                {"role": "user", "content": "test question"},
            ],
            base_url="http://localhost:11434",
        )

    assert result == "Fallback local response"
    assert mocked_post.call_count == 2
    first_url = mocked_post.call_args_list[0].args[0]
    second_url = mocked_post.call_args_list[1].args[0]
    assert first_url.endswith("/api/chat")
    assert second_url.endswith("/api/generate")


@pytest.mark.django_db
def test_call_llm_local_llm_falls_back_to_fast_model_on_timeout():
    from app.services.llm_client import call_llm
    import requests

    timeout_error = requests.Timeout("Read timed out")
    fallback_response = MagicMock()
    fallback_response.raise_for_status.return_value = None
    fallback_response.json.return_value = {"message": {"content": "Fast fallback answer"}}

    with patch(
        "app.services.llm_client.requests.post",
        side_effect=[timeout_error, fallback_response],
    ) as mocked_post:
        result = call_llm(
            provider="local_llm",
            model="gemma4:latest",
            call_type="qa",
            messages=[{"role": "user", "content": "Explain this topic"}],
            base_url="http://localhost:11434",
        )

    assert result == "Fast fallback answer"
    assert mocked_post.call_count == 2
    first_payload = mocked_post.call_args_list[0].kwargs["json"]
    second_payload = mocked_post.call_args_list[1].kwargs["json"]
    assert first_payload["model"] == "gemma4:latest"
    assert second_payload["model"] == "qwen3.5:0.8b"


@pytest.mark.django_db
def test_call_llm_local_llm_falls_back_to_generate_when_chat_content_empty():
    from app.services.llm_client import call_llm

    chat_response = MagicMock()
    chat_response.raise_for_status.return_value = None
    chat_response.json.return_value = {"message": {"role": "assistant", "content": ""}}

    generate_response = MagicMock()
    generate_response.raise_for_status.return_value = None
    generate_response.json.return_value = {"response": "Recovered from generate endpoint"}

    with patch(
        "app.services.llm_client.requests.post",
        side_effect=[chat_response, generate_response],
    ) as mocked_post:
        result = call_llm(
            provider="local_llm",
            model="qwen3.5:0.8b",
            call_type="suggestion",
            messages=[{"role": "user", "content": "Give 3 study questions"}],
            base_url="http://localhost:11434",
        )

    assert result == "Recovered from generate endpoint"
    assert mocked_post.call_count == 2
    assert mocked_post.call_args_list[0].args[0].endswith("/api/chat")
    assert mocked_post.call_args_list[1].args[0].endswith("/api/generate")


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


@pytest.mark.django_db
def test_call_llm_local_llm_retries_without_thinking_on_http_400():
    from app.services.llm_client import call_llm
    import requests

    error_response = MagicMock()
    error_response.status_code = 400
    http_error = requests.HTTPError(response=error_response)
    error_response.raise_for_status = MagicMock(side_effect=http_error)

    retry_response = MagicMock()
    retry_response.raise_for_status.return_value = None
    retry_response.json.return_value = {"message": {"content": "Retry success"}}

    with patch(
        "app.services.llm_client.requests.post",
        side_effect=[error_response, retry_response],
    ) as mocked_post:
        result = call_llm(
            provider="local_llm",
            model="qwen3:8b",
            call_type="qa",
            messages=[{"role": "user", "content": "test"}],
            base_url="http://localhost:11434",
            return_thinking=True,
        )

    assert isinstance(result, tuple)
    assert result[0] == "Retry success"
    assert mocked_post.call_count == 2
    first_payload = mocked_post.call_args_list[0].kwargs["json"]
    second_payload = mocked_post.call_args_list[1].kwargs["json"]
    assert first_payload.get("think") is True
    assert "think" not in second_payload


@pytest.mark.django_db
def test_call_llm_local_llm_non_reasoning_model_skips_thinking():
    from app.services.llm_client import call_llm

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "message": {"content": "Non-thinking response"}
    }

    with patch(
        "app.services.llm_client.requests.post", return_value=mock_response
    ) as mocked_post:
        result = call_llm(
            provider="local_llm",
            model="qwen2.5:3b",
            call_type="qa",
            messages=[{"role": "user", "content": "test"}],
            base_url="http://localhost:11434",
            return_thinking=True,
        )

    assert isinstance(result, tuple)
    assert result[0] == "Non-thinking response"
    assert result[1] is None
    payload = mocked_post.call_args.kwargs["json"]
    assert "think" not in payload
