"""Centralized LLM call wrapper with logging."""

import time
from typing import Any, Dict, List

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
