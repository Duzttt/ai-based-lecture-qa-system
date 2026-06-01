"""Standalone QA-generation and evaluation pipeline.

This module is intentionally Django-free at import time so the CLI scripts
under ``scripts/`` can run without ``manage.py``.
"""
from __future__ import annotations

import logging
from typing import Optional, Tuple

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
