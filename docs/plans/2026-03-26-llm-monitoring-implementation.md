# LLM 调用监控后台 — 实现计划

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 为 RAG 系统添加 LLM 调用监控功能，统一采集所有 LLM 调用并提供独立页面查看。

**Architecture:** 创建集中式 `call_llm()` 包装函数（`app/services/llm_client.py`），所有 5 个服务模块通过它调用 LLM，统一处理计时和日志写入 QueryLog。新增独立页面 `/llm-logs` 展示调用记录。

**Tech Stack:** Django, Python, requests/httpx, Bootstrap (前端页面)

---

### Task 1: 扩展 QueryLog 数据模型

**Files:**
- Modify: `django_app/models.py:165-273`

**Step 1: Write failing tests**

```python
# tests/test_models_llm.py
import pytest
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_models_llm.py -v`
Expected: FAIL with field errors (fields don't exist yet)

**Step 3: Add fields to QueryLog model**

在 `django_app/models.py` 的 `QueryLog` 类中，`llm_model` 字段之后添加：

```python
    # LLM provider tracking
    llm_provider = models.CharField(
        max_length=20,
        blank=True,
        default="",
        help_text="LLM provider: gemini / openrouter / local_qwen",
    )

    llm_status = models.CharField(
        max_length=10,
        default="success",
        help_text="Call status: success / error",
    )

    error_message = models.TextField(
        blank=True,
        default="",
        help_text="Error message if call failed",
    )

    CALL_TYPE_CHOICES = [
        ("qa", "Question Answering"),
        ("summary", "Summarization"),
        ("suggestion", "Question Suggestion"),
        ("citation", "Citation"),
    ]

    call_type = models.CharField(
        max_length=20,
        default="qa",
        help_text="Type of LLM call",
    )
```

在 `Meta.indexes` 中添加：

```python
            models.Index(fields=["llm_provider"]),
            models.Index(fields=["llm_status"]),
```

**Step 4: Run migration and tests**

```bash
python manage.py makemigrations django_app
python manage.py migrate
pytest tests/test_models_llm.py -v
```
Expected: PASS all 3 tests

**Step 5: Commit**

```bash
git add django_app/models.py tests/test_models_llm.py
git commit -m "feat: extend QueryLog with llm_provider, llm_status, error_message, call_type fields"
```

---

### Task 2: 创建集中式 LLM 包装函数

**Files:**
- Create: `app/services/llm_client.py`
- Test: `tests/test_llm_client.py`

**Step 1: Write failing tests**

```python
# tests/test_llm_client.py
import pytest
from unittest.mock import patch, MagicMock


@pytest.mark.django_db
def test_call_llm_success_logs_to_db():
    from app.services.llm_client import call_llm
    from django_app.models import QueryLog

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
def test_call_llm_error_logs_to_db():
    from app.services.llm_client import call_llm
    from django_app.models import QueryLog

    with patch("app.services.llm_client.requests.post", side_effect=Exception("Connection refused")):
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
    assert log.call_type == "summary"
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
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL with "ModuleNotFoundError: No module named 'app.services.llm_client'"

**Step 3: Create `app/services/llm_client.py`**

```python
"""Centralized LLM call wrapper with logging."""

import time
from typing import Any, Dict, List, Optional

import requests

from django_app.models import QueryLog


def _call_gemini(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str,
    base_url: str,
    timeout: int,
    **kwargs: Any,
) -> str:
    """Call Gemini REST API and return response text."""
    prompt_parts = []
    for msg in messages:
        prompt_parts.append(f"[{msg['role']}]: {msg['content']}")
    prompt = "\n".join(prompt_parts)

    payload: Dict[str, Any] = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": kwargs.get("temperature", 0.7),
            "maxOutputTokens": kwargs.get("max_tokens", 500),
        },
    }
    if kwargs.get("response_format") == "json":
        payload["generationConfig"]["responseMimeType"] = "application/json"

    response = requests.post(
        f"{base_url}/models/{model}:generateContent?key={api_key}",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])
    if not candidates:
        raise ValueError("No response from Gemini")

    return candidates[0]["content"]["parts"][0]["text"]


def _call_openrouter(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str,
    base_url: str,
    timeout: int,
    **kwargs: Any,
) -> str:
    """Call OpenRouter chat completions API and return response text."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": kwargs.get("temperature", 0.7),
        "stream": False,
    }
    if kwargs.get("max_tokens"):
        payload["max_tokens"] = kwargs["max_tokens"]

    response = requests.post(
        f"{base_url}/chat/completions",
        headers=headers,
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    choices = data.get("choices", [])
    if not choices:
        raise ValueError("No response from OpenRouter")

    return choices[0]["message"]["content"]


def _call_local_qwen(
    messages: List[Dict[str, str]],
    model: str,
    base_url: str,
    timeout: int,
    **kwargs: Any,
) -> str:
    """Call local Ollama API and return response text."""
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "keep_alive": kwargs.get("keep_alive", "30m"),
    }
    if "temperature" in kwargs:
        payload["options"] = {"temperature": kwargs["temperature"]}

    response = requests.post(
        f"{base_url.rstrip('/')}/api/chat",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()

    data = response.json()
    message = data.get("message", {}).get("content")
    if not message:
        raise ValueError("Invalid response from local Qwen model")

    return str(message).strip()


_PROVIDER_DISPATCH = {
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
    "local_qwen": _call_local_qwen,
}


def call_llm(
    provider: str,
    model: str,
    call_type: str,
    messages: List[Dict[str, str]],
    timeout: int = 60,
    query_text: str = "",
    **kwargs: Any,
) -> str:
    """
    Centralized LLM call with timing and database logging.

    Args:
        provider: "gemini" / "openrouter" / "local_qwen"
        model: Model name
        call_type: "qa" / "summary" / "suggestion" / "citation"
        messages: Standard message format [{"role": "system", "content": ...}, ...]
        timeout: Request timeout in seconds
        query_text: Original query text for logging
        **kwargs: Provider-specific params (api_key, base_url, temperature, etc.)

    Returns:
        LLM response text

    Raises:
        ValueError: If provider is unsupported
        Exception: Original exception on failure (after logging)
    """
    if provider not in _PROVIDER_DISPATCH:
        raise ValueError(f"Unsupported provider: {provider}")

    dispatch_fn = _PROVIDER_DISPATCH[provider]
    start_time = time.monotonic()

    try:
        result = dispatch_fn(
            messages=messages,
            model=model,
            timeout=timeout,
            **kwargs,
        )
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        QueryLog.objects.create(
            query=query_text or (messages[-1].get("content", "") if messages else ""),
            latency_ms=elapsed_ms,
            llm_model=model,
            llm_provider=provider,
            llm_status="success",
            call_type=call_type,
            answer_length=len(result),
        )
        return result

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        QueryLog.objects.create(
            query=query_text or (messages[-1].get("content", "") if messages else ""),
            latency_ms=elapsed_ms,
            llm_model=model,
            llm_provider=provider,
            llm_status="error",
            error_message=str(exc),
            call_type=call_type,
        )
        raise
```

**Step 4: Run tests to verify they pass**

```bash
pytest tests/test_llm_client.py -v
```
Expected: PASS all 3 tests

**Step 5: Commit**

```bash
git add app/services/llm_client.py tests/test_llm_client.py
git commit -m "feat: add centralized call_llm() wrapper with logging"
```

---

### Task 3: 改造 local_rag.py 使用 call_llm()

**Files:**
- Modify: `app/services/local_rag.py:88-172`
- Test: `tests/test_llm_client.py` (add integration tests)

**Step 1: Read existing file**

Review `app/services/local_rag.py` lines 88-210 to understand current patterns.

**Step 2: Replace `generate_with_local_qwen()`**

将 `generate_with_local_qwen()` 函数改为调用 `call_llm()`：

```python
def generate_with_local_qwen(
    query: str,
    context: str,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    timeout_seconds: Optional[int] = 30,
) -> str:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    resolved_model = model or settings.LOCAL_QWEN_MODEL
    resolved_base_url = base_url or settings.LOCAL_QWEN_BASE_URL
    resolved_timeout = timeout_seconds or settings.LOCAL_QWEN_TIMEOUT_SECONDS

    from app.services.llm_client import call_llm

    return call_llm(
        provider="local_qwen",
        model=resolved_model,
        call_type="qa",
        messages=build_rag_messages(query, context),
        timeout=resolved_timeout,
        query_text=query,
        base_url=resolved_base_url,
        keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
    )
```

**Step 3: Replace `generate_with_openrouter()`**

将 `generate_with_openrouter()` 函数改为调用 `call_llm()`：

```python
def generate_with_openrouter(
    query: str,
    context: str,
    model: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.7,
    timeout_seconds: int = 60,
) -> str:
    if not context.strip():
        return "No usable reference material was retrieved, so I cannot answer based on evidence."

    resolved_model = model or settings.OPENROUTER_MODEL
    resolved_key = api_key or settings.OPENROUTER_API_KEY

    if not resolved_key:
        raise LocalRAGError("OPENROUTER_API_KEY is not configured")

    from app.services.llm_client import call_llm

    return call_llm(
        provider="openrouter",
        model=resolved_model,
        call_type="qa",
        messages=build_rag_messages(query, context),
        timeout=timeout_seconds,
        query_text=query,
        api_key=resolved_key,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=temperature,
    )
```

**Step 4: Run tests**

```bash
pytest tests/test_llm_client.py -v
```
Expected: PASS

**Step 5: Commit**

```bash
git add app/services/local_rag.py
git commit -m "refactor: use call_llm() in local_rag.py"
```

---

### Task 4: 改造 rag_pipeline.py 使用 call_llm()

**Files:**
- Modify: `app/services/rag_pipeline.py:70-155`

**Step 1: Replace `_generate_gemini()`**

```python
def _generate_gemini(self, prompt: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="gemini",
        model=settings.GEMINI_MODEL,
        call_type="qa",
        messages=[{"role": "user", "content": prompt}],
        query_text=prompt,
        api_key=settings.GEMINI_API_KEY,
        base_url=settings.GEMINI_BASE_URL,
        temperature=0.7,
        max_tokens=500,
    )
```

**Step 2: Replace `_generate_openrouter()`**

```python
def _generate_openrouter(self, prompt: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="openrouter",
        model=settings.OPENROUTER_MODEL,
        call_type="qa",
        messages=[{"role": "user", "content": prompt}],
        query_text=prompt,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0.7,
        max_tokens=500,
    )
```

**Step 3: Run tests**

```bash
pytest tests/ -v -k "llm"  # or broader test suite
```

**Step 4: Commit**

```bash
git add app/services/rag_pipeline.py
git commit -m "refactor: use call_llm() in rag_pipeline.py"
```

---

### Task 5: 改造 citation_rag.py 使用 call_llm()

**Files:**
- Modify: `app/services/citation_rag.py:148-280`

**Step 1: Replace `_generate_with_qwen()`**

```python
def _generate_with_qwen(self, prompt: str, model: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="local_qwen",
        model=model or settings.LOCAL_QWEN_MODEL,
        call_type="citation",
        messages=[{"role": "user", "content": prompt}],
        query_text=prompt,
        base_url=self.base_url,
        temperature=0.3,
    )
```

**Step 2: Replace `_generate_with_openrouter()`**

```python
def _generate_with_openrouter(self, prompt: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="openrouter",
        model=settings.OPENROUTER_MODEL,
        call_type="citation",
        messages=[{"role": "user", "content": prompt}],
        query_text=prompt,
        api_key=self.api_key,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0.3,
    )
```

**Step 3: Commit**

```bash
git add app/services/citation_rag.py
git commit -m "refactor: use call_llm() in citation_rag.py"
```

---

### Task 6: 改造 summarizer.py 使用 call_llm()

**Files:**
- Modify: `app/services/summarizer.py:143-290`

**Step 1: Replace `_call_local_qwen()`**

```python
def _call_local_qwen(self, prompt: str, response_format: str = None) -> str:
    from app.services.llm_client import call_llm

    system_prompt = "You are a professional document summarization assistant. Generate clear, accurate summaries."
    if response_format == "json":
        system_prompt += " Output ONLY valid JSON."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    return call_llm(
        provider="local_qwen",
        model=self.model,
        call_type="summary",
        messages=messages,
        query_text=prompt,
        base_url=self.base_url,
        timeout=self.timeout,
        keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
    )
```

**Step 2: Replace `_call_gemini()`**

```python
def _call_gemini(self, prompt: str, response_format: str = None) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="gemini",
        model=settings.GEMINI_MODEL,
        call_type="summary",
        messages=[{"role": "user", "content": prompt}],
        query_text=prompt,
        api_key=settings.GEMINI_API_KEY,
        base_url=settings.GEMINI_BASE_URL,
        timeout=60,
        temperature=0.3,
        max_tokens=2048,
        response_format=response_format,
    )
```

**Step 3: Replace `_call_openrouter()`**

```python
def _call_openrouter(self, prompt: str, response_format: str = None) -> str:
    from app.services.llm_client import call_llm

    system_prompt = "You are a professional document summarization assistant. Generate clear, accurate summaries."
    if response_format == "json":
        system_prompt += " Output ONLY valid JSON."

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]

    return call_llm(
        provider="openrouter",
        model=settings.OPENROUTER_MODEL,
        call_type="summary",
        messages=messages,
        query_text=prompt,
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0.3,
        max_tokens=2048,
    )
```

**Step 4: Commit**

```bash
git add app/services/summarizer.py
git commit -m "refactor: use call_llm() in summarizer.py"
```

---

### Task 7: 改造 question_suggestions.py 使用 call_llm()

**Files:**
- Modify: `app/services/question_suggestions.py:390-520`

**Step 1: Replace `_call_local_qwen()`**

```python
def _call_local_qwen(self, prompt: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="local_qwen",
        model=self.model,
        call_type="suggestion",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        query_text=prompt[:200],
        base_url=self.base_url,
        timeout=self.timeout,
        keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
    )
```

**Step 2: Replace `_call_gemini()`**

```python
def _call_gemini(self, prompt: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="gemini",
        model=settings.GEMINI_MODEL,
        call_type="suggestion",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        query_text=prompt[:200],
        api_key=settings.GEMINI_API_KEY,
        base_url=settings.GEMINI_BASE_URL,
        timeout=60,
        temperature=0.7,
        max_tokens=500,
    )
```

**Step 3: Replace `_call_openrouter()`**

```python
def _call_openrouter(self, prompt: str) -> str:
    from app.services.llm_client import call_llm

    return call_llm(
        provider="openrouter",
        model=settings.OPENROUTER_MODEL,
        call_type="suggestion",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        query_text=prompt[:200],
        api_key=settings.OPENROUTER_API_KEY,
        base_url=settings.OPENROUTER_BASE_URL,
        temperature=0.7,
        max_tokens=500,
    )
```

**Step 4: Commit**

```bash
git add app/services/question_suggestions.py
git commit -m "refactor: use call_llm() in question_suggestions.py"
```

---

### Task 8: 创建 LLM 日志 API 视图

**Files:**
- Create: `django_app/views/llm_logs.py`
- Modify: `django_app/views/__init__.py`
- Modify: `django_backend/urls.py`
- Test: `tests/test_llm_logs_api.py`

**Step 1: Write failing tests**

```python
# tests/test_llm_logs_api.py
import pytest
from django.test import Client
from django_app.models import QueryLog


@pytest.mark.django_db
def test_llm_logs_list_returns_records(client: Client):
    QueryLog.objects.create(query="q1", latency_ms=100, llm_provider="gemini", llm_status="success", call_type="qa")
    QueryLog.objects.create(query="q2", latency_ms=200, llm_provider="openrouter", llm_status="error", call_type="summary")

    response = client.get("/api/llm-logs/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["records"]) == 2


@pytest.mark.django_db
def test_llm_logs_filter_by_provider(client: Client):
    QueryLog.objects.create(query="q1", latency_ms=100, llm_provider="gemini", call_type="qa")
    QueryLog.objects.create(query="q2", latency_ms=200, llm_provider="openrouter", call_type="qa")

    response = client.get("/api/llm-logs/?provider=gemini")
    data = response.json()
    assert data["total"] == 1
    assert data["records"][0]["llm_provider"] == "gemini"


@pytest.mark.django_db
def test_llm_logs_stats(client: Client):
    QueryLog.objects.create(query="q1", latency_ms=100, llm_provider="gemini", llm_status="success", call_type="qa")
    QueryLog.objects.create(query="q2", latency_ms=300, llm_provider="gemini", llm_status="success", call_type="qa")
    QueryLog.objects.create(query="q3", latency_ms=200, llm_provider="openrouter", llm_status="error", call_type="summary")

    response = client.get("/api/llm-logs/stats/")
    assert response.status_code == 200
    stats = response.json()
    assert stats["total_calls"] == 3
    assert stats["error_count"] == 1
    assert stats["avg_latency_ms"] == 200
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_llm_logs_api.py -v`
Expected: FAIL with 404 (routes don't exist)

**Step 3: Create `django_app/views/llm_logs.py`**

```python
"""LLM call monitoring views."""

import json
from django.http import JsonResponse, HttpRequest
from django.views.decorators.http import require_http_methods
from django.db.models import Count, Avg, Q

from django_app.models import QueryLog


@require_http_methods(["GET"])
def llm_logs_list(request: HttpRequest) -> JsonResponse:
    """List LLM call logs with optional filtering."""
    provider = request.GET.get("provider", "")
    call_type = request.GET.get("call_type", "")
    page = int(request.GET.get("page", 1))
    page_size = min(int(request.GET.get("page_size", 50)), 200)

    queryset = QueryLog.objects.exclude(llm_provider="")

    if provider:
        queryset = queryset.filter(llm_provider=provider)
    if call_type:
        queryset = queryset.filter(call_type=call_type)

    total = queryset.count()
    offset = (page - 1) * page_size
    records = queryset[offset : offset + page_size]

    return JsonResponse(
        {
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": [
                {
                    "id": r.id,
                    "query": r.query[:200],
                    "llm_provider": r.llm_provider,
                    "llm_model": r.llm_model,
                    "llm_status": r.llm_status,
                    "error_message": r.error_message,
                    "call_type": r.call_type,
                    "latency_ms": r.latency_ms,
                    "answer_length": r.answer_length,
                    "created_at": r.created_at.isoformat(),
                }
                for r in records
            ],
        }
    )


@require_http_methods(["GET"])
def llm_logs_stats(request: HttpRequest) -> JsonResponse:
    """Aggregate stats for LLM call logs."""
    base_qs = QueryLog.objects.exclude(llm_provider="")

    provider_counts = dict(
        base_qs.values_list("llm_provider")
        .annotate(count=Count("id"))
        .values_list("llm_provider", "count")
    )

    total = base_qs.count()
    error_count = base_qs.filter(llm_status="error").count()
    avg_latency = base_qs.aggregate(avg=Avg("latency_ms"))["avg"] or 0

    return JsonResponse(
        {
            "total_calls": total,
            "error_count": error_count,
            "error_rate": round(error_count / total * 100, 1) if total > 0 else 0,
            "avg_latency_ms": round(avg_latency),
            "by_provider": provider_counts,
        }
    )


def llm_logs_page(request: HttpRequest):
    """Render the LLM logs monitoring page."""
    from django.shortcuts import render

    return render(request, "llm_logs.html")
```

**Step 4: Update `django_app/views/__init__.py`**

Add imports:

```python
# LLM Logs
from django_app.views.llm_logs import (
    llm_logs_list,
    llm_logs_stats,
    llm_logs_page,
)
```

Add to `__all__`:

```python
    # LLM Logs
    "llm_logs_list",
    "llm_logs_stats",
    "llm_logs_page",
```

**Step 5: Update `django_backend/urls.py`**

Add imports at top (already imported via `views`):

```python
from django_app.views import (
    # ... existing imports ...
    llm_logs_list,
    llm_logs_stats,
    llm_logs_page,
)
```

Add URL patterns:

```python
    # LLM Monitoring
    path("llm-logs", llm_logs_page, name="llm_logs_page"),
    path("api/llm-logs/", llm_logs_list, name="llm_logs_list"),
    path("api/llm-logs/stats/", llm_logs_stats, name="llm_logs_stats"),
```

**Step 6: Run tests**

```bash
pytest tests/test_llm_logs_api.py -v
```
Expected: PASS all 3 tests

**Step 7: Commit**

```bash
git add django_app/views/llm_logs.py django_app/views/__init__.py django_backend/urls.py tests/test_llm_logs_api.py
git commit -m "feat: add LLM logs API endpoints (/api/llm-logs/, /api/llm-logs/stats/)"
```

---

### Task 9: 创建前端页面

**Files:**
- Create: `django_app/templates/llm_logs.html`

**Step 1: Create the HTML template**

```html
<!-- django_app/templates/llm_logs.html -->
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LLM 调用监控</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: #f5f5f5; color: #333; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        h1 { margin-bottom: 20px; font-size: 24px; }
        .stats-cards { display: flex; gap: 16px; margin-bottom: 24px; flex-wrap: wrap; }
        .stat-card { background: #fff; border-radius: 8px; padding: 16px 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); min-width: 180px; }
        .stat-card .label { font-size: 13px; color: #888; margin-bottom: 4px; }
        .stat-card .value { font-size: 28px; font-weight: 600; }
        .stat-card .value.error { color: #e74c3c; }
        .toolbar { display: flex; gap: 12px; margin-bottom: 16px; align-items: center; flex-wrap: wrap; }
        .toolbar select, .toolbar button { padding: 8px 12px; border: 1px solid #ddd; border-radius: 6px; font-size: 14px; }
        .toolbar button { background: #4a90d9; color: #fff; border: none; cursor: pointer; }
        .toolbar button:hover { background: #357abd; }
        table { width: 100%; background: #fff; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); border-collapse: collapse; }
        th { background: #f8f9fa; text-align: left; padding: 12px; font-size: 13px; color: #666; border-bottom: 2px solid #eee; }
        td { padding: 10px 12px; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
        tr:hover td { background: #fafafa; }
        .status-success { color: #27ae60; font-weight: 500; }
        .status-error { color: #e74c3c; font-weight: 500; }
        .badge { display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 12px; background: #eef2ff; color: #4a5568; }
        .pagination { display: flex; gap: 8px; margin-top: 16px; justify-content: center; }
        .pagination button { padding: 6px 14px; border: 1px solid #ddd; border-radius: 6px; background: #fff; cursor: pointer; }
        .pagination button.active { background: #4a90d9; color: #fff; border-color: #4a90d9; }
        .pagination button:disabled { opacity: 0.5; cursor: not-allowed; }
        .error-msg { color: #999; font-size: 12px; max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .loading { text-align: center; padding: 40px; color: #999; }
    </style>
</head>
<body>
    <div class="container">
        <h1>LLM 调用监控</h1>

        <div class="stats-cards" id="statsCards">
            <div class="stat-card"><div class="label">总调用次数</div><div class="value" id="totalCalls">-</div></div>
            <div class="stat-card"><div class="label">平均延迟</div><div class="value" id="avgLatency">-</div></div>
            <div class="stat-card"><div class="label">错误次数</div><div class="value error" id="errorCount">-</div></div>
            <div class="stat-card"><div class="label">错误率</div><div class="value error" id="errorRate">-</div></div>
        </div>

        <div class="toolbar">
            <select id="providerFilter">
                <option value="">全部 Provider</option>
                <option value="gemini">Gemini</option>
                <option value="openrouter">OpenRouter</option>
                <option value="local_qwen">Local Qwen</option>
            </select>
            <select id="callTypeFilter">
                <option value="">全部类型</option>
                <option value="qa">问答</option>
                <option value="summary">摘要</option>
                <option value="suggestion">问题建议</option>
                <option value="citation">引用</option>
            </select>
            <button onclick="loadData()">刷新</button>
            <label><input type="checkbox" id="autoRefresh" onchange="toggleAutoRefresh()"> 自动刷新 (10s)</label>
        </div>

        <table>
            <thead>
                <tr>
                    <th>时间</th>
                    <th>类型</th>
                    <th>Provider</th>
                    <th>模型</th>
                    <th>延迟(ms)</th>
                    <th>状态</th>
                    <th>错误信息</th>
                </tr>
            </thead>
            <tbody id="logTableBody">
                <tr><td colspan="7" class="loading">加载中...</td></tr>
            </tbody>
        </table>

        <div class="pagination" id="pagination"></div>
    </div>

    <script>
        let currentPage = 1;
        let autoRefreshTimer = null;

        async function loadStats() {
            try {
                const res = await fetch('/api/llm-logs/stats/');
                const data = await res.json();
                document.getElementById('totalCalls').textContent = data.total_calls;
                document.getElementById('avgLatency').textContent = data.avg_latency_ms + 'ms';
                document.getElementById('errorCount').textContent = data.error_count;
                document.getElementById('errorRate').textContent = data.error_rate + '%';
            } catch (e) { console.error('Failed to load stats:', e); }
        }

        async function loadLogs(page = 1) {
            currentPage = page;
            const provider = document.getElementById('providerFilter').value;
            const callType = document.getElementById('callTypeFilter').value;
            const params = new URLSearchParams({ page, page_size: 50 });
            if (provider) params.set('provider', provider);
            if (callType) params.set('call_type', callType);

            try {
                const res = await fetch(`/api/llm-logs/?${params}`);
                const data = await res.json();
                renderTable(data.records);
                renderPagination(data.total, data.page, data.page_size);
            } catch (e) {
                document.getElementById('logTableBody').innerHTML = '<tr><td colspan="7" class="loading">加载失败</td></tr>';
            }
        }

        function renderTable(records) {
            const tbody = document.getElementById('logTableBody');
            if (!records.length) {
                tbody.innerHTML = '<tr><td colspan="7" class="loading">暂无记录</td></tr>';
                return;
            }
            tbody.innerHTML = records.map(r => `
                <tr>
                    <td>${new Date(r.created_at).toLocaleString('zh-CN')}</td>
                    <td><span class="badge">${callTypeLabel(r.call_type)}</span></td>
                    <td>${r.llm_provider}</td>
                    <td>${r.llm_model}</td>
                    <td>${r.latency_ms}</td>
                    <td class="status-${r.llm_status}">${r.llm_status === 'success' ? '成功' : '失败'}</td>
                    <td class="error-msg" title="${escapeHtml(r.error_message)}">${escapeHtml(r.error_message)}</td>
                </tr>
            `).join('');
        }

        function callTypeLabel(t) {
            return { qa: '问答', summary: '摘要', suggestion: '问题建议', citation: '引用' }[t] || t;
        }

        function escapeHtml(s) {
            if (!s) return '';
            return s.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
        }

        function renderPagination(total, page, pageSize) {
            const totalPages = Math.ceil(total / pageSize);
            const div = document.getElementById('pagination');
            if (totalPages <= 1) { div.innerHTML = ''; return; }
            let html = `<button ${page<=1?'disabled':''} onclick="loadLogs(${page-1})">上一页</button>`;
            for (let i = 1; i <= totalPages && i <= 10; i++) {
                html += `<button class="${i===page?'active':''}" onclick="loadLogs(${i})">${i}</button>`;
            }
            html += `<button ${page>=totalPages?'disabled':''} onclick="loadLogs(${page+1})">下一页</button>`;
            div.innerHTML = html;
        }

        function loadData() {
            loadStats();
            loadLogs(currentPage);
        }

        function toggleAutoRefresh() {
            if (document.getElementById('autoRefresh').checked) {
                autoRefreshTimer = setInterval(loadData, 10000);
            } else {
                clearInterval(autoRefreshTimer);
                autoRefreshTimer = null;
            }
        }

        document.getElementById('providerFilter').addEventListener('change', () => loadLogs(1));
        document.getElementById('callTypeFilter').addEventListener('change', () => loadLogs(1));

        loadData();
    </script>
</body>
</html>
```

**Step 2: Verify page loads**

```bash
python manage.py runserver 0.0.0.0:8000
```
Visit `http://localhost:8000/llm-logs` and verify the page loads correctly.

**Step 3: Commit**

```bash
git add django_app/templates/llm_logs.html
git commit -m "feat: add LLM monitoring page with stats and filtering"
```

---

### Task 10: 端到端验证与代码质量检查

**Step 1: Run all tests**

```bash
pytest tests/ -v
```
Expected: All PASS

**Step 2: Run lint and type checks**

```bash
ruff check app/services/llm_client.py django_app/views/llm_logs.py django_app/models.py --fix
black app/services/llm_client.py django_app/views/llm_logs.py django_app/models.py
```

**Step 3: Manual smoke test**

1. Start server: `python manage.py runserver 0.0.0.0:8000`
2. Make a question via `/api/ask` or `/api/chat`
3. Visit `/llm-logs` and verify the call appears
4. Test filtering by provider
5. Test stats page accuracy

**Step 4: Final commit**

```bash
git add -A
git commit -m "feat: complete LLM monitoring backend with centralized logging"
```
