import os

import django
import pytest

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

from django_app.models import QueryLog


@pytest.mark.django_db
def test_querylog_has_llm_provider_field():
    log = QueryLog.objects.create(
        query="test",
        latency_ms=100,
        llm_provider="gemini",
        llm_status="success",
        call_type="qa",
    )
    assert log.llm_provider == "gemini"
    assert log.llm_status == "success"
    assert log.call_type == "qa"
    assert log.error_message == ""


@pytest.mark.django_db
def test_querylog_defaults():
    log = QueryLog.objects.create(
        query="test",
        latency_ms=100,
    )
    assert log.llm_provider == ""
    assert log.llm_status == "success"
    assert log.error_message == ""
    assert log.call_type == "qa"


@pytest.mark.django_db
def test_querylog_error_status():
    log = QueryLog.objects.create(
        query="test",
        latency_ms=200,
        llm_provider="openrouter",
        llm_status="error",
        error_message="API key invalid",
        call_type="summary",
    )
    assert log.llm_status == "error"
    assert log.error_message == "API key invalid"
