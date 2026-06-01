"""Standalone QA-generation and evaluation pipeline.

This module is intentionally Django-free at import time so the CLI scripts
under ``scripts/`` can run without ``manage.py``.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


_QA_PROMPT_TEMPLATE = """Based on the following text, generate {num} question-answer pairs for evaluation.

{lang_instruction}

Return ONLY a JSON array with no additional text:
[
    {{"question": "...", "ground_truth": "..."}},
    ...
]

Text:
{text}
"""


def _build_qa_prompt(text: str, num: int, language: str) -> str:
    lang_instruction = (
        "Generate questions and answers in Chinese."
        if language == "zh"
        else "Generate questions and answers in English."
    )
    return _QA_PROMPT_TEMPLATE.format(
        num=num, lang_instruction=lang_instruction, text=text
    )


def _qa_with_retries(
    *, base_url: str, model: str, prompt: str, timeout: int
) -> List[Dict[str, str]]:
    """Call LLM once; on parse failure, retry once with stricter suffix."""
    suffixes = ["", "\n\nReturn ONLY a valid JSON array. No prose."]
    last_err: Optional[Exception] = None
    for suffix in suffixes:
        try:
            content = _call_chat(
                base_url=base_url,
                model=model,
                messages=[{"role": "user", "content": prompt + suffix}],
                timeout=timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise exc
        try:
            return _parse_qa_json(content)
        except ValueError as exc:
            last_err = exc
            continue
    raise last_err or ValueError("Unknown parse failure")


def generate_qa_dataset(
    *,
    pdf_paths: Iterable[str],
    out_path: str,
    base_url: str,
    model: str,
    num_questions_per_pdf: int = 5,
    language: str = "en",
    timeout: int = 120,
) -> int:
    """Generate Q-A pairs from PDFs, write JSONL. Returns total question count."""
    from app.services.pdf_loader import PDFLoader

    loader = PDFLoader(documents_path=str(os.path.dirname(out_path) or "."))
    total = 0
    tmp_path = out_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        for pdf_path in pdf_paths:
            if not os.path.exists(pdf_path):
                logger.warning("PDF not found, skipping: %s", pdf_path)
                continue
            try:
                text = loader.extract_text(pdf_path)
            except Exception as exc:
                logger.warning("Failed to extract %s: %s", pdf_path, exc)
                continue
            if not (text or "").strip():
                logger.warning("No text extracted from %s, skipping", pdf_path)
                continue

            prompt = _build_qa_prompt(text, num_questions_per_pdf, language)
            try:
                qa_pairs = _qa_with_retries(
                    base_url=base_url,
                    model=model,
                    prompt=prompt,
                    timeout=timeout,
                )
            except requests.exceptions.Timeout:
                logger.warning("Timeout on first try, retrying with truncated text")
                prompt = _build_qa_prompt(
                    text[:2000], num_questions_per_pdf, language
                )
                try:
                    qa_pairs = _qa_with_retries(
                        base_url=base_url,
                        model=model,
                        prompt=prompt,
                        timeout=timeout,
                    )
                except Exception as exc:
                    logger.error("Skipping %s after retry: %s", pdf_path, exc)
                    continue
            except Exception as exc:
                logger.error("Skipping %s: %s", pdf_path, exc)
                continue

            for qa in qa_pairs:
                fh.write(
                    json.dumps(
                        {"question": qa["question"], "ground_truth": qa["ground_truth"]},
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                total += 1
            logger.info("Wrote %d Q-A from %s", len(qa_pairs), pdf_path)
    os.replace(tmp_path, out_path)
    return total
