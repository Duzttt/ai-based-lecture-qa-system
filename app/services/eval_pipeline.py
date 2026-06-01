"""Standalone QA-generation and evaluation pipeline.

This module is intentionally Django-free at import time so the CLI scripts
under ``scripts/`` can run without ``manage.py``.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.config import Settings

logger = logging.getLogger(__name__)


class EvalPipelineError(Exception):
    """Base error for the eval pipeline."""


def _normalize_url(raw: str) -> str:
    """Strip trailing slash and ensure ``/v1`` suffix."""
    normalized = str(raw).rstrip("/")
    if not normalized.endswith("/v1"):
        normalized = f"{normalized}/v1"
    return normalized


def resolve_endpoint(
    *,
    phase: str,
    settings: Settings,
    cli_base_url: Optional[str] = None,
    cli_model: Optional[str] = None,
) -> Tuple[str, str]:
    """Resolve (base_url, model) for a pipeline phase.

    Precedence: CLI flag > phase env var > ``LOCAL_LLM_*`` fallback.
    Raises ``EvalPipelineError`` when no base URL or model can be resolved.
    """
    if phase == "qa_gen":
        env_base, env_model = settings.QA_GEN_BASE_URL, settings.QA_GEN_MODEL
    elif phase == "eval":
        env_base, env_model = settings.EVAL_BASE_URL, settings.EVAL_MODEL
    else:
        raise EvalPipelineError(f"Unknown phase: {phase!r}")

    base_url = cli_base_url or env_base or settings.LOCAL_LLM_BASE_URL
    model = cli_model or env_model or settings.LOCAL_LLM_MODEL

    if not base_url:
        raise EvalPipelineError(
            f"No base URL resolved for phase={phase!r}. "
            "Set --base-url, QA_GEN_BASE_URL/EVAL_BASE_URL, or LOCAL_LLM_BASE_URL."
        )
    if not model:
        raise EvalPipelineError(
            f"No model resolved for phase={phase!r}. "
            "Set --model, QA_GEN_MODEL/EVAL_MODEL, or LOCAL_LLM_MODEL."
        )

    return _normalize_url(base_url), str(model).strip()


def _parse_qa_json(content: str) -> List[Dict[str, str]]:
    """Parse a JSON array of ``{question, ground_truth}`` dicts, tolerating fluff."""
    content = (content or "").strip()

    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

    try:
        result = json.loads(content)
        if isinstance(result, list):
            return result
    except json.JSONDecodeError:
        pass

    start = content.find("[")
    end = content.rfind("]")
    if start != -1 and end > start:
        try:
            result = json.loads(content[start : end + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass

    if start != -1:
        fragment = content[start:]
        last_brace = fragment.rfind("}")
        if last_brace > 0:
            repaired = fragment[: last_brace + 1] + "]"
            try:
                result = json.loads(repaired)
                if isinstance(result, list):
                    return result
            except json.JSONDecodeError:
                pass

    raise ValueError(f"No valid JSON array found in LLM response: {content[:200]}")


def _call_chat(
    *,
    base_url: str,
    model: str,
    messages: List[Dict[str, str]],
    timeout: int,
    num_predict: Optional[int] = 4096,
) -> str:
    """POST to ``{base_url}/v1/chat/completions`` and return the message content."""
    payload: Dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
    }
    if num_predict is not None:
        payload["max_tokens"] = num_predict

    response = requests.post(
        f"{base_url.rstrip('/')}/v1/chat/completions",
        json=payload,
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("Empty response from /v1/chat/completions")
    content = choices[0].get("message", {}).get("content")
    if not content:
        raise ValueError("Empty content from /v1/chat/completions")
    return str(content).strip()
