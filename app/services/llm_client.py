"""Centralized LLM call wrapper with logging."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from django_app.models import QueryLog

logger = logging.getLogger("llm")


def _call_gemini(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str,
    base_url: str,
    timeout: int,
    **kwargs: Any,
) -> str:
    if not api_key or str(api_key).strip().lower() in {"none", "null"}:
        raise ValueError("GEMINI_API_KEY is not configured")

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
    api_key: str = "",
    base_url: str = "",
    timeout: int = 60,
    **kwargs: Any,
) -> str:
    provider = kwargs.get("provider", "")
    if provider != "local_llm":
        if not api_key or str(api_key).strip().lower() in {"none", "null"}:
            raise ValueError("OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {api_key or 'none'}",
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
    if kwargs.get("keep_alive"):
        payload["keep_alive"] = kwargs["keep_alive"]

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


_PROVIDER_DISPATCH = {
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
    "local_llm": _call_openrouter,
}


def call_llm(
    provider: str,
    model: str,
    call_type: str,
    messages: List[Dict[str, str]],
    timeout: int = 60,
    query_text: str = "",
    return_log: bool = False,
    return_thinking: bool = False,
    **kwargs: Any,
) -> Union[
    str,
    Tuple[str, int],
    Tuple[str, Optional[str]],
    Tuple[str, Optional[str], int],
]:
    if provider not in _PROVIDER_DISPATCH:
        raise ValueError(f"Unsupported provider: {provider}")

    dispatch_fn = _PROVIDER_DISPATCH[provider]
    start_time = time.monotonic()
    effective_query = query_text or (messages[-1].get("content", "") if messages else "")
    logger.info(
        "LLM call | provider=%s model=%s type=%s query=%s",
        provider, model, call_type, effective_query[:120],
    )

    try:
        result = dispatch_fn(
            messages=messages,
            model=model,
            timeout=timeout,
            provider=provider,
            **kwargs,
        )
        elapsed_ms = int((time.monotonic() - start_time) * 1000)

        # Extract content for logging
        content_for_log = result[0] if isinstance(result, tuple) else result
        logger.info(
            "LLM success | provider=%s model=%s latency=%dms answer_len=%d",
            provider, model, elapsed_ms, len(content_for_log),
        )

        log_entry = QueryLog.objects.create(
            query=query_text or (messages[-1].get("content", "") if messages else ""),
            latency_ms=elapsed_ms,
            llm_model=model,
            llm_provider=provider,
            llm_status="success",
            call_type=call_type,
            answer_length=len(content_for_log),
        )

        if return_thinking and return_log:
            # Return (content, thinking, log_id) tuple when both are requested.
            if isinstance(result, tuple):
                return result[0], result[1], int(log_entry.id)
            return result, None, int(log_entry.id)
        if return_thinking:
            # Return (content, thinking) tuple.
            if isinstance(result, tuple):
                return result
            return result, None
        if return_log:
            if isinstance(result, tuple):
                return result[0], int(log_entry.id)
            return result, int(log_entry.id)
        return result

    except Exception as exc:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.error(
            "LLM error | provider=%s model=%s latency=%dms error=%s",
            provider, model, elapsed_ms, exc,
        )

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
