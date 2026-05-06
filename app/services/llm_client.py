"""Centralized LLM call wrapper with logging."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from django_app.models import QueryLog

logger = logging.getLogger("llm")

LOCAL_LLM_FAST_FALLBACK_MODEL = "qwen3.5:0.8b"

# Models that support the 'think' parameter for reasoning/thinking output
REASONING_MODELS = {
    "deepseek-r1",
    "deepseek-r1:8b",
    "deepseek-r1:14b",
    "deepseek-r1:32b",
    "deepseek-r1:70b",
    "qwen3",
    "qwen3:4b",
    "qwen3:8b",
    "qwen3:14b",
    "qwen3:30b",
    "qwen3:32b",
    "qwen3:72b",
    "qwen3:235b",
}


def _model_supports_thinking(model_name: str) -> bool:
    """Check if a model supports the 'think' parameter."""
    model_lower = model_name.lower().strip()
    # Check exact match
    if model_lower in REASONING_MODELS:
        return True
    # Check if any reasoning model is a prefix (e.g., "qwen3:4b" starts with "qwen3")
    for reasoning_model in REASONING_MODELS:
        if (
            model_lower.startswith(reasoning_model + ":")
            or model_lower == reasoning_model
        ):
            return True
    return False


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
    api_key: str,
    base_url: str,
    timeout: int,
    **kwargs: Any,
) -> str:
    if not api_key or str(api_key).strip().lower() in {"none", "null"}:
        raise ValueError("OPENROUTER_API_KEY is not configured")

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


def _call_local_llm(
    messages: List[Dict[str, str]],
    model: str,
    base_url: str,
    timeout: int,
    **kwargs: Any,
) -> Union[str, Tuple[str, Optional[str]]]:
    options: Dict[str, Any] = {}
    if "temperature" in kwargs:
        options["temperature"] = kwargs["temperature"]
    if "num_predict" in kwargs:
        options["num_predict"] = kwargs["num_predict"]

    return_thinking = kwargs.get("return_thinking", False)
    # Only use thinking if requested AND model supports it
    use_thinking = return_thinking and _model_supports_thinking(model)

    def _call_model_once(
        target_model: str, with_thinking: bool = True
    ) -> Union[str, Tuple[str, Optional[str]]]:
        payload = {
            "model": target_model,
            "messages": messages,
            "stream": False,
            "keep_alive": kwargs.get("keep_alive", "30m"),
        }
        if with_thinking:
            payload["think"] = True
        if options:
            payload["options"] = options

        try:
            response = requests.post(
                f"{base_url.rstrip('/')}/api/chat",
                json=payload,
                timeout=timeout,
            )
            response.raise_for_status()

            data = response.json()
            message_obj = data.get("message", {})
            content = message_obj.get("content")
            thinking = message_obj.get("thinking") if with_thinking else None

            if not content:
                raise ValueError("Empty content from /api/chat")

            if return_thinking:
                return (
                    str(content).strip(),
                    str(thinking).strip() if thinking else None,
                )
            return str(content).strip()
        except requests.HTTPError as exc:
            # If thinking failed with 400, retry without think parameter
            if (
                exc.response is not None
                and exc.response.status_code == 400
                and with_thinking
            ):
                return _call_model_once(target_model, with_thinking=False)
            raise
        except ValueError:
            # Some Ollama models fail on /api/chat but work on /api/generate.
            prompt_parts = [
                f"{msg.get('role', 'user')}: {msg.get('content', '')}"
                for msg in messages
            ]
            generate_payload: Dict[str, Any] = {
                "model": target_model,
                "prompt": "\n".join(prompt_parts).strip(),
                "stream": False,
                "keep_alive": kwargs.get("keep_alive", "30m"),
            }
            if with_thinking:
                generate_payload["think"] = True
            if options:
                generate_payload["options"] = options

            generate_response = requests.post(
                f"{base_url.rstrip('/')}/api/generate",
                json=generate_payload,
                timeout=timeout,
            )
            generate_response.raise_for_status()
            generate_data = generate_response.json()
            text = generate_data.get("response")
            thinking = generate_data.get("thinking") if with_thinking else None

            if not text:
                raise ValueError("Invalid response from local LLM")

            if return_thinking:
                return str(text).strip(), str(thinking).strip() if thinking else None
            return str(text).strip()

    try:
        return _call_model_once(model, with_thinking=use_thinking)
    except requests.Timeout:
        fallback_model = kwargs.get(
            "fallback_model",
            LOCAL_LLM_FAST_FALLBACK_MODEL,
        )
        if fallback_model and str(fallback_model).strip() != str(model).strip():
            return _call_model_once(str(fallback_model).strip())
        raise


_PROVIDER_DISPATCH = {
    "gemini": _call_gemini,
    "openrouter": _call_openrouter,
    "local_llm": _call_local_llm,
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
            return_thinking=return_thinking,
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
