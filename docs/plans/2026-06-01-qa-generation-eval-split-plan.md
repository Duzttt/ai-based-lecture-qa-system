# QA-Generation and Evaluation Split — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Split the QA-generation and RAGAS-evaluation LLM work into two independent CLI scripts that share a JSONL file, allowing the llama.cpp server to be restarted or the model swapped between phases.

**Architecture:** New `app/services/eval_pipeline.py` exposes two pure functions (`generate_qa_dataset`, `evaluate_dataset`). Two thin CLI scripts in `scripts/` wrap them with argparse. Both phases read independent env vars (`QA_GEN_*` / `EVAL_*`) with fallback to `LOCAL_LLM_*` and CLI override. Existing `RAGASEvaluator` and `QuestionSuggestionService` are not touched.

**Tech Stack:** Python 3, pytest, `requests`, RAGAS (existing), sentence-transformers (existing), Django (NOT required at runtime — scripts can run without `manage.py`).

---

## Task 1: Add new config entries to `app/config.py`

**Files:**
- Modify: `app/config.py:49-62`

**Step 1: Add the new fields after the existing `LOCAL_LLM_*` block**

In `app/config.py`, after line 62 (`LOCAL_LLM_TIMEOUT_SECONDS: int = 300`), insert:

```python
    QA_GEN_BASE_URL: Optional[str] = None
    QA_GEN_MODEL: Optional[str] = None
    QA_GEN_TIMEOUT_SECONDS: int = 120

    EVAL_BASE_URL: Optional[str] = None
    EVAL_MODEL: Optional[str] = None
    EVAL_TIMEOUT_SECONDS: int = 300
    EVAL_MAX_WORKERS: int = 4
```

**Step 2: Verify settings still import cleanly**

Run: `python -c "from app.config import settings; print(settings.QA_GEN_BASE_URL, settings.EVAL_MODEL)"`
Expected: `None None` (no traceback).

**Step 3: Commit**

```bash
git add app/config.py
git commit -m "feat(config): add QA_GEN_* and EVAL_* env vars for split eval pipeline"
```

---

## Task 2: TDD — `resolve_endpoint()` helper in `app/services/eval_pipeline.py`

**Files:**
- Create: `app/services/eval_pipeline.py`
- Create: `tests/test_eval_pipeline.py`

**Step 1: Write the failing test**

In `tests/test_eval_pipeline.py`:

```python
"""Tests for app.services.eval_pipeline."""
import pytest

from app.config import Settings
from app.services.eval_pipeline import resolve_endpoint, EvalPipelineError


@pytest.fixture
def clean_settings(monkeypatch):
    """Reset env vars so tests are deterministic."""
    for key in (
        "QA_GEN_BASE_URL", "QA_GEN_MODEL", "QA_GEN_TIMEOUT_SECONDS",
        "EVAL_BASE_URL", "EVAL_MODEL", "EVAL_TIMEOUT_SECONDS",
        "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    return Settings()


def test_resolve_endpoint_cli_flag_wins(monkeypatch, clean_settings):
    monkeypatch.setenv("QA_GEN_BASE_URL", "http://env:8080")
    monkeypatch.setenv("QA_GEN_MODEL", "env-model")
    base_url, model = resolve_endpoint(
        phase="qa_gen", settings=clean_settings,
        cli_base_url="http://cli:9090", cli_model="cli-model",
    )
    assert base_url == "http://cli:9090"
    assert model == "cli-model"


def test_resolve_endpoint_env_var_falls_back(monkeypatch, clean_settings):
    monkeypatch.setenv("QA_GEN_BASE_URL", "http://env:8080")
    monkeypatch.setenv("QA_GEN_MODEL", "env-model")
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://local:8080")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "local-model")
    base_url, model = resolve_endpoint(phase="qa_gen", settings=clean_settings)
    assert base_url == "http://env:8080"
    assert model == "env-model"


def test_resolve_endpoint_uses_local_llm_fallback(monkeypatch, clean_settings):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://local:8080")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "local-model")
    base_url, model = resolve_endpoint(phase="eval", settings=clean_settings)
    assert base_url == "http://local:8080"
    assert model == "local-model"


def test_resolve_endpoint_appends_v1(monkeypatch, clean_settings):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://local:8080")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "m")
    base_url, _ = resolve_endpoint(phase="qa_gen", settings=clean_settings)
    assert base_url.endswith("/v1")


def test_resolve_endpoint_strips_trailing_v1_then_readds(monkeypatch, clean_settings):
    monkeypatch.setenv("LOCAL_LLM_BASE_URL", "http://local:8080/v1/")
    monkeypatch.setenv("LOCAL_LLM_MODEL", "m")
    base_url, _ = resolve_endpoint(phase="qa_gen", settings=clean_settings)
    assert base_url == "http://local:8080/v1"


def test_resolve_endpoint_raises_when_unset(monkeypatch, clean_settings):
    with pytest.raises(EvalPipelineError):
        resolve_endpoint(phase="eval", settings=clean_settings)
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval_pipeline.py -v`
Expected: ImportError or AttributeError (module does not exist yet).

**Step 3: Implement `resolve_endpoint()`**

In `app/services/eval_pipeline.py`:

```python
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
```

Also create an empty `app/services/__init__.py` re-export shim — not needed because
`eval_pipeline.py` is a sibling module.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval_pipeline.py -v`
Expected: 6 tests pass.

**Step 5: Commit**

```bash
git add app/services/eval_pipeline.py tests/test_eval_pipeline.py
git commit -m "feat(eval_pipeline): add resolve_endpoint helper with CLI > env > fallback precedence"
```

---

## Task 3: TDD — `_parse_qa_json()` and `_call_chat()` helpers

**Files:**
- Modify: `app/services/eval_pipeline.py`
- Modify: `tests/test_eval_pipeline.py`

**Step 1: Append failing tests for `_parse_qa_json` and `_call_chat`**

Add to `tests/test_eval_pipeline.py`:

```python
from app.services.eval_pipeline import _parse_qa_json, _call_chat


def test_parse_qa_json_strips_markdown_fences():
    raw = '```json\n[{"question": "q", "ground_truth": "a"}]\n```'
    assert _parse_qa_json(raw) == [{"question": "q", "ground_truth": "a"}]


def test_parse_qa_json_extracts_array_from_extra_text():
    raw = 'Here you go: [{"question": "q1", "ground_truth": "a1"}] enjoy!'
    assert _parse_qa_json(raw) == [{"question": "q1", "ground_truth": "a1"}]


def test_parse_qa_json_repairs_truncated_array():
    raw = '[{"question": "q1", "ground_truth": "a1"}, {"question": "q2", "ground_trut'
    # Should not raise; may return either the partial or empty depending on repair logic.
    result = _parse_qa_json(raw)
    assert isinstance(result, list)


def test_parse_qa_json_raises_on_garbage():
    with pytest.raises(ValueError):
        _parse_qa_json("not json at all")


def test_call_chat_posts_to_v1_chat_completions(monkeypatch):
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["timeout"] = timeout

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        return R()

    monkeypatch.setattr("app.services.eval_pipeline.requests.post", fake_post)
    text = _call_chat(
        base_url="http://x:8080",
        model="m",
        messages=[{"role": "user", "content": "hi"}],
        timeout=10,
    )
    assert text == "ok"
    assert captured["url"] == "http://x:8080/v1/chat/completions"
    assert captured["json"]["model"] == "m"
    assert captured["timeout"] == 10


def test_call_chat_raises_on_empty_choices(monkeypatch):
    def fake_post(url, json, timeout):
        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"choices": []}

        return R()

    monkeypatch.setattr("app.services.eval_pipeline.requests.post", fake_post)
    with pytest.raises(ValueError):
        _call_chat(
            base_url="http://x:8080",
            model="m",
            messages=[{"role": "user", "content": "hi"}],
            timeout=10,
        )
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval_pipeline.py -v -k "parse_qa_json or call_chat"`
Expected: ImportError for `_parse_qa_json` / `_call_chat`.

**Step 3: Implement the helpers**

Append to `app/services/eval_pipeline.py`:

```python
import json
from typing import Any, Dict, List

import requests


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
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval_pipeline.py -v -k "parse_qa_json or call_chat"`
Expected: 6 tests pass.

**Step 5: Commit**

```bash
git add app/services/eval_pipeline.py tests/test_eval_pipeline.py
git commit -m "feat(eval_pipeline): add _parse_qa_json and _call_chat helpers"
```

---

## Task 4: TDD — `generate_qa_dataset()` end-to-end

**Files:**
- Modify: `app/services/eval_pipeline.py`
- Modify: `tests/test_eval_pipeline.py`

**Step 1: Append failing tests**

Add to `tests/test_eval_pipeline.py`:

```python
import os
from app.services.eval_pipeline import generate_qa_dataset, evaluate_dataset


def test_generate_qa_dataset_writes_jsonl(tmp_path, monkeypatch):
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(b"%PDF-stub")  # PDFLoader stub: monkeypatched below
    out_path = tmp_path / "out.jsonl"

    def fake_extract_text(self, path):
        return "Some long lecture text " * 50

    monkeypatch.setattr(
        "app.services.pdf_loader.PDFLoader.extract_text", fake_extract_text
    )

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        return '[{"question": "Q1", "ground_truth": "A1"}, {"question": "Q2", "ground_truth": "A2"}]'

    monkeypatch.setattr("app.services.eval_pipeline._call_chat", fake_call_chat)

    count = generate_qa_dataset(
        pdf_paths=[str(pdf_path)],
        out_path=str(out_path),
        base_url="http://x:8080",
        model="m",
        num_questions_per_pdf=2,
    )
    assert count == 2
    lines = out_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    import json as _json
    record = _json.loads(lines[0])
    assert set(record.keys()) == {"question", "ground_truth"}


def test_generate_qa_dataset_skips_missing_pdf(tmp_path, monkeypatch):
    out_path = tmp_path / "out.jsonl"

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        raise AssertionError("LLM should not be called when PDF is missing")

    monkeypatch.setattr("app.services.eval_pipeline._call_chat", fake_call_chat)

    count = generate_qa_dataset(
        pdf_paths=[str(tmp_path / "nope.pdf")],
        out_path=str(out_path),
        base_url="http://x:8080",
        model="m",
    )
    assert count == 0
    assert not out_path.exists() or out_path.read_text(encoding="utf-8") == ""


def test_generate_qa_dataset_retries_on_bad_json(tmp_path, monkeypatch):
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(b"%PDF-stub")
    out_path = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        "app.services.pdf_loader.PDFLoader.extract_text",
        lambda self, path: "lecture text " * 50,
    )

    call_count = {"n": 0}

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return "not valid json"
        return '[{"question": "Q", "ground_truth": "A"}]'

    monkeypatch.setattr("app.services.eval_pipeline._call_chat", fake_call_chat)

    count = generate_qa_dataset(
        pdf_paths=[str(pdf_path)],
        out_path=str(out_path),
        base_url="http://x:8080",
        model="m",
    )
    assert count == 1
    assert call_count["n"] == 2  # one retry


def test_generate_qa_dataset_falls_back_to_truncated_on_timeout(tmp_path, monkeypatch):
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(b"%PDF-stub")
    out_path = tmp_path / "out.jsonl"

    monkeypatch.setattr(
        "app.services.pdf_loader.PDFLoader.extract_text",
        lambda self, path: "x" * 10_000,
    )

    call_count = {"n": 0}

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise requests.exceptions.Timeout("slow")
        return '[{"question": "Q", "ground_truth": "A"}]'

    monkeypatch.setattr("app.services.eval_pipeline._call_chat", fake_call_chat)

    import requests as _requests
    monkeypatch.setattr("app.services.eval_pipeline.requests", _requests)

    count = generate_qa_dataset(
        pdf_paths=[str(pdf_path)],
        out_path=str(out_path),
        base_url="http://x:8080",
        model="m",
    )
    assert count == 1
    assert call_count["n"] == 2
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval_pipeline.py -v -k "generate_qa_dataset"`
Expected: ImportError for `generate_qa_dataset`.

**Step 3: Implement `generate_qa_dataset()`**

Append to `app/services/eval_pipeline.py`:

```python
import os
from typing import Iterable, Optional

from app.services.pdf_loader import PDFLoader


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
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval_pipeline.py -v -k "generate_qa_dataset"`
Expected: 4 tests pass.

**Step 5: Commit**

```bash
git add app/services/eval_pipeline.py tests/test_eval_pipeline.py
git commit -m "feat(eval_pipeline): add generate_qa_dataset with retries and timeout fallback"
```

---

## Task 5: TDD — `evaluate_dataset()` end-to-end

**Files:**
- Modify: `app/services/eval_pipeline.py`
- Modify: `tests/test_eval_pipeline.py`

**Step 1: Append failing tests**

Add to `tests/test_eval_pipeline.py`:

```python
def test_evaluate_dataset_reads_jsonl_and_writes_csv(tmp_path, monkeypatch):
    ds_path = tmp_path / "eval.jsonl"
    ds_path.write_text(
        '{"question": "Q1", "ground_truth": "A1"}\n'
        '{"question": "Q2", "ground_truth": "A2"}\n',
        encoding="utf-8",
    )
    out_path = tmp_path / "report.csv"

    monkeypatch.setattr(
        "app.services.eval_pipeline.retrieve_with_faiss",
        lambda query, top_k=5, source_filter=None: [
            {"text": f"context for {query}", "source": "x.pdf", "page": 1}
        ],
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline.build_context_from_sources",
        lambda sources: "ctx",
    )

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        return f"answer to {messages[-1]['content'][:30]}"

    monkeypatch.setattr("app.services.eval_pipeline._call_chat", fake_call_chat)

    class FakeResult:
        def to_dict(self):
            return {
                "faithfulness": 0.9,
                "answer_relevancy": 0.8,
                "context_precision": 0.7,
                "context_recall": 0.6,
            }

    def fake_ragas(dataset, llm, embeddings, timeout, max_workers):
        # RAGAS returns an object with .to_dict() and .to_pandas()
        class Pandas:
            def to_dict(self, orient="records"):
                return [
                    {"question": r["question"], "faithfulness": 0.9}
                    for r in dataset.to_list()
                ]

        class Scores:
            def to_pandas(self):
                return Pandas()

        return Scores()

    monkeypatch.setattr(
        "app.services.eval_pipeline._run_ragas_metrics", fake_ragas
    )

    summary = evaluate_dataset(
        dataset_path=str(ds_path),
        out_path=str(out_path),
        base_url="http://x:8080",
        model="m",
    )
    assert summary["num_questions"] == 2
    assert out_path.exists()
    csv_text = out_path.read_text(encoding="utf-8")
    assert "question" in csv_text
    assert "Q1" in csv_text


def test_evaluate_dataset_continues_on_single_question_failure(tmp_path, monkeypatch):
    ds_path = tmp_path / "eval.jsonl"
    ds_path.write_text(
        '{"question": "Q1", "ground_truth": "A1"}\n'
        '{"question": "Q2", "ground_truth": "A2"}\n',
        encoding="utf-8",
    )
    out_path = tmp_path / "report.csv"

    def fake_retrieve(query, top_k=5, source_filter=None):
        if "Q2" in query:
            raise RuntimeError("retrieval boom")
        return [{"text": "ctx", "source": "x.pdf", "page": 1}]

    monkeypatch.setattr(
        "app.services.eval_pipeline.retrieve_with_faiss", fake_retrieve
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline.build_context_from_sources", lambda s: "ctx"
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline._call_chat",
        lambda **kw: "ans",
    )

    def fake_ragas(dataset, llm, embeddings, timeout, max_workers):
        # RAGAS skips empty answers; we just return a stub.
        class Pandas:
            def to_dict(self, orient="records"):
                return list(dataset.to_list())

        class Scores:
            def to_pandas(self):
                return Pandas()

        return Scores()

    monkeypatch.setattr("app.services.eval_pipeline._run_ragas_metrics", fake_ragas)

    summary = evaluate_dataset(
        dataset_path=str(ds_path),
        out_path=str(out_path),
        base_url="http://x:8080",
        model="m",
    )
    assert summary["num_questions"] >= 1
    assert out_path.exists()


def test_evaluate_dataset_raises_on_length_mismatch(tmp_path):
    ds_path = tmp_path / "bad.jsonl"
    ds_path.write_text(
        '{"question": "Q1", "ground_truth": "A1"}\n',
        encoding="utf-8",
    )
    # Manually craft an out-of-sync in-memory dataset
    from app.services.eval_pipeline import DatasetFormatError, evaluate_dataset
    with pytest.raises(DatasetFormatError):
        evaluate_dataset(
            dataset_path=str(ds_path),
            out_path=str(tmp_path / "out.csv"),
            base_url="http://x:8080",
            model="m",
        )
    # The DatasetFormatError is only raised when the JSONL is missing
    # the ground_truth field; the real length mismatch is in the dataset
    # itself. Confirm the bad-record path raises:
    bad_path = tmp_path / "bad2.jsonl"
    bad_path.write_text(
        '{"question": "Q1"}\n', encoding="utf-8"
    )
    with pytest.raises(DatasetFormatError):
        evaluate_dataset(
            dataset_path=str(bad_path),
            out_path=str(tmp_path / "out2.csv"),
            base_url="http://x:8080",
            model="m",
        )
```

**Step 2: Run tests to verify they fail**

Run: `pytest tests/test_eval_pipeline.py -v -k "evaluate_dataset"`
Expected: ImportError for `evaluate_dataset`.

**Step 3: Implement `evaluate_dataset()` and `_run_ragas_metrics`**

Append to `app/services/eval_pipeline.py`:

```python
class DatasetFormatError(EvalPipelineError):
    """Raised when the input JSONL is malformed."""


class QAJsonParseError(EvalPipelineError):
    """Raised when QA-generation LLM output is unparseable."""


def _run_ragas_metrics(dataset, llm, embeddings, timeout: int, max_workers: int):
    """Thin wrapper around RAGAS so tests can mock at this boundary."""
    try:
        from ragas import evaluate as ragas_evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
        from ragas.run_config import RunConfig
    except ImportError as exc:
        raise EvalPipelineError(
            "RAGAS not installed. Run: pip install ragas datasets"
        ) from exc

    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    for metric in metrics:
        if hasattr(metric, "llm"):
            metric.llm = llm

    return ragas_evaluate(
        dataset=dataset,
        metrics=metrics,
        embeddings=embeddings,
        run_config=RunConfig(timeout=timeout, max_workers=max_workers),
    )


def evaluate_dataset(
    *,
    dataset_path: str,
    out_path: str,
    base_url: str,
    model: str,
    top_k: int = 5,
    timeout: int = 300,
    max_workers: int = 4,
) -> Dict[str, Any]:
    """Read JSONL, run RAG + RAGAS, write CSV. Returns summary dict."""
    if not os.path.exists(dataset_path):
        raise DatasetFormatError(f"Dataset not found: {dataset_path}")

    questions: List[str] = []
    ground_truths: List[str] = []
    with open(dataset_path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise DatasetFormatError(f"Bad JSONL line: {exc}") from exc
            if "question" not in record or "ground_truth" not in record:
                raise DatasetFormatError(
                    f"Missing required field in record: {record}"
                )
            questions.append(str(record["question"]))
            ground_truths.append(str(record["ground_truth"]))

    if len(questions) != len(ground_truths):
        raise DatasetFormatError("questions and ground_truths length mismatch")

    # Run RAG for each question
    from app.services.local_rag import (
        build_context_from_sources,
        retrieve_with_faiss,
    )

    rows: List[Dict[str, Any]] = []
    for q in questions:
        try:
            sources = retrieve_with_faiss(query=q, top_k=top_k)
            context = build_context_from_sources(sources)
            answer = _call_chat(
                base_url=base_url,
                model=model,
                messages=[
                    {
                        "role": "user",
                        "content": f"Context: {context}\n\nQuestion: {q}",
                    }
                ],
                timeout=timeout,
            )
            rows.append(
                {
                    "question": q,
                    "answer": answer,
                    "contexts": [s.get("text", "") for s in sources],
                    "ground_truth": next(
                        gt for q_, gt in zip(questions, ground_truths) if q_ == q
                    ),
                }
            )
        except Exception as exc:
            logger.warning("Failed question %r: %s", q[:50], exc)
            rows.append(
                {"question": q, "answer": "", "contexts": [], "ground_truth": ""}
            )

    data = {
        "question": [r["question"] for r in rows if r["answer"]],
        "answer": [r["answer"] for r in rows if r["answer"]],
        "contexts": [r["contexts"] for r in rows if r["answer"]],
        "ground_truth": [
            next(
                gt
                for q_, gt in zip(questions, ground_truths)
                if q_ == r["question"]
            )
            for r in rows
            if r["answer"]
        ],
    }
    if not data["question"]:
        raise EvalPipelineError("No valid RAG results to evaluate")

    try:
        from datasets import Dataset as HFDataset
    except ImportError as exc:
        raise EvalPipelineError(
            "datasets not installed. Run: pip install datasets"
        ) from exc

    dataset = HFDataset.from_dict(data)

    from app.services.embedding import EmbeddingService
    from app.services.runtime_embedding import load_runtime_embedding_settings
    from langchain_core.embeddings import Embeddings
    from langchain_openai import ChatOpenAI
    from ragas.llms import LangchainLLMWrapper

    rt = load_runtime_embedding_settings()
    embedding_service = EmbeddingService(model_name=rt["model_id"])

    class _LocalEmbeddings(Embeddings):
        def embed_documents(self, texts):
            emb = embedding_service.embed_texts(texts)
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            return [[float(v) for v in row] for row in emb]

        def embed_query(self, text):
            emb = embedding_service.embed_query(text)
            if hasattr(emb, "tolist"):
                emb = emb.tolist()
            return [float(v) for v in emb]

    langchain_llm = ChatOpenAI(
        model=model,
        openai_api_key="local",
        openai_api_base=base_url,
        temperature=0,
        max_tokens=4096,
    )
    ragas_llm = LangchainLLMWrapper(langchain_llm)

    result = _run_ragas_metrics(
        dataset=dataset,
        llm=ragas_llm,
        embeddings=_LocalEmbeddings(),
        timeout=timeout,
        max_workers=max_workers,
    )

    df = result.to_pandas()
    df.to_csv(out_path, index=False, encoding="utf-8")
    score_dict = df.to_dict(orient="records")
    return {
        "num_questions": len(data["question"]),
        "scores": score_dict,
        "csv_path": out_path,
    }
```

**Step 4: Run tests to verify they pass**

Run: `pytest tests/test_eval_pipeline.py -v -k "evaluate_dataset"`
Expected: 3 tests pass.

**Step 5: Commit**

```bash
git add app/services/eval_pipeline.py tests/test_eval_pipeline.py
git commit -m "feat(eval_pipeline): add evaluate_dataset with RAGAS scoring and CSV output"
```

---

## Task 6: `scripts/generate_qa_dataset.py` CLI

**Files:**
- Create: `scripts/generate_qa_dataset.py`

**Step 1: Write the CLI script**

```python
"""Phase 1: generate a Q-A evaluation dataset from PDFs.

Usage:
    python scripts/generate_qa_dataset.py \\
        --pdfs notes1.pdf,notes2.pdf \\
        --out eval_dataset.jsonl \\
        --num 5
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running this script directly without ``manage.py``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services.eval_pipeline import (  # noqa: E402
    EvalPipelineError,
    generate_qa_dataset,
    resolve_endpoint,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Q-A evaluation dataset from PDFs via llama.cpp."
    )
    parser.add_argument(
        "--pdfs",
        required=True,
        help="Comma-separated list of PDF paths (absolute or relative).",
    )
    parser.add_argument(
        "--out", required=True, help="Output JSONL path (e.g. eval_dataset.jsonl)."
    )
    parser.add_argument("--num", type=int, default=5, help="Questions per PDF.")
    parser.add_argument(
        "--lang", default="en", choices=["en", "zh"], help="Question language."
    )
    parser.add_argument(
        "--base-url", default=None, help="Override QA_GEN_BASE_URL."
    )
    parser.add_argument("--model", default=None, help="Override QA_GEN_MODEL.")
    parser.add_argument(
        "--timeout", type=int, default=settings.QA_GEN_TIMEOUT_SECONDS
    )
    parser.add_argument("--log-file", default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if args.log_file:
        logging.getLogger().addHandler(
            logging.FileHandler(args.log_file, encoding="utf-8")
        )

    try:
        base_url, model = resolve_endpoint(
            phase="qa_gen",
            settings=settings,
            cli_base_url=args.base_url,
            cli_model=args.model,
        )
    except EvalPipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    pdf_paths = [p.strip() for p in args.pdfs.split(",") if p.strip()]
    if not pdf_paths:
        print("ERROR: --pdfs is empty", file=sys.stderr)
        return 1

    try:
        count = generate_qa_dataset(
            pdf_paths=pdf_paths,
            out_path=args.out,
            base_url=base_url,
            model=model,
            num_questions_per_pdf=args.num,
            language=args.lang,
            timeout=args.timeout,
        )
    except EvalPipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(f"Wrote {count} questions to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Verify it runs and shows the help**

Run: `python scripts/generate_qa_dataset.py --help`
Expected: argparse help text, exit 0.

**Step 3: Commit**

```bash
git add scripts/generate_qa_dataset.py
git commit -m "feat(scripts): add generate_qa_dataset CLI"
```

---

## Task 7: `scripts/run_evaluation.py` CLI

**Files:**
- Create: `scripts/run_evaluation.py`

**Step 1: Write the CLI script**

```python
"""Phase 2: evaluate a Q-A dataset with RAG + RAGAS, output CSV.

Usage:
    python scripts/run_evaluation.py \\
        --dataset eval_dataset.jsonl \\
        --out eval_report.csv
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Allow running this script directly without ``manage.py``.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings  # noqa: E402
from app.services.eval_pipeline import (  # noqa: E402
    DatasetFormatError,
    EvalPipelineError,
    evaluate_dataset,
    resolve_endpoint,
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run RAG + RAGAS evaluation on a JSONL dataset."
    )
    parser.add_argument(
        "--dataset", required=True, help="Path to JSONL dataset (input)."
    )
    parser.add_argument(
        "--out", required=True, help="Output CSV path (e.g. eval_report.csv)."
    )
    parser.add_argument("--top-k", type=int, default=5, help="Chunks to retrieve.")
    parser.add_argument(
        "--base-url", default=None, help="Override EVAL_BASE_URL."
    )
    parser.add_argument("--model", default=None, help="Override EVAL_MODEL.")
    parser.add_argument(
        "--timeout", type=int, default=settings.EVAL_TIMEOUT_SECONDS
    )
    parser.add_argument(
        "--max-workers", type=int, default=settings.EVAL_MAX_WORKERS
    )
    parser.add_argument("--log-file", default=None)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        stream=sys.stderr,
    )
    if args.log_file:
        logging.getLogger().addHandler(
            logging.FileHandler(args.log_file, encoding="utf-8")
        )

    try:
        base_url, model = resolve_endpoint(
            phase="eval",
            settings=settings,
            cli_base_url=args.base_url,
            cli_model=args.model,
        )
    except EvalPipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    try:
        summary = evaluate_dataset(
            dataset_path=args.dataset,
            out_path=args.out,
            base_url=base_url,
            model=model,
            top_k=args.top_k,
            timeout=args.timeout,
            max_workers=args.max_workers,
        )
    except DatasetFormatError as exc:
        print(f"ERROR (dataset format): {exc}", file=sys.stderr)
        return 1
    except EvalPipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    print(
        f"Evaluated {summary['num_questions']} questions. CSV: {summary['csv_path']}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

**Step 2: Verify it runs and shows the help**

Run: `python scripts/run_evaluation.py --help`
Expected: argparse help text, exit 0.

**Step 3: Commit**

```bash
git add scripts/run_evaluation.py
git commit -m "feat(scripts): add run_evaluation CLI"
```

---

## Task 8: End-to-end smoke test (mocked)

**Files:**
- Create: `tests/test_eval_pipeline_e2e.py`

**Step 1: Write the test**

```python
"""End-to-end test for the two-script pipeline (mocked LLM)."""
import json
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_full_pipeline_runs(tmp_path, monkeypatch):
    """Run both scripts in sequence with mocked LLM and verify JSONL + CSV."""
    pdf = tmp_path / "notes.pdf"
    pdf.write_bytes(b"%PDF-stub")

    fake_text = "Lecture content " * 200
    monkeypatch.setattr(
        "app.services.pdf_loader.PDFLoader.extract_text",
        lambda self, path: fake_text,
    )

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        if "Generate" in messages[-1]["content"]:
            return '[{"question": "Q1", "ground_truth": "A1"}]'
        return "RAG answer"

    monkeypatch.setattr(
        "app.services.eval_pipeline._call_chat", fake_call_chat
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline.retrieve_with_faiss",
        lambda query, top_k=5, source_filter=None: [
            {"text": "ctx", "source": "x.pdf", "page": 1}
        ],
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline.build_context_from_sources",
        lambda sources: "ctx",
    )

    class _FakeDF:
        def to_csv(self, path, index=False, encoding="utf-8"):
            Path(path).write_text("question\nQ1\n", encoding=encoding)

        def to_dict(self, orient="records"):
            return [{"question": "Q1"}]

    class _FakeResult:
        def to_pandas(self):
            return _FakeDF()

    monkeypatch.setattr(
        "app.services.eval_pipeline._run_ragas_metrics",
        lambda *a, **kw: _FakeResult(),
    )

    jsonl_path = tmp_path / "eval.jsonl"
    csv_path = tmp_path / "report.csv"

    # Phase 1
    from app.services.eval_pipeline import generate_qa_dataset
    count = generate_qa_dataset(
        pdf_paths=[str(pdf)],
        out_path=str(jsonl_path),
        base_url="http://x:8080",
        model="m",
    )
    assert count == 1
    assert json.loads(jsonl_path.read_text(encoding="utf-8").strip())["question"] == "Q1"

    # Phase 2
    from app.services.eval_pipeline import evaluate_dataset
    summary = evaluate_dataset(
        dataset_path=str(jsonl_path),
        out_path=str(csv_path),
        base_url="http://x:8080",
        model="m",
    )
    assert summary["num_questions"] == 1
    assert csv_path.exists()
```

**Step 2: Run the test**

Run: `pytest tests/test_eval_pipeline_e2e.py -v`
Expected: 1 test passes.

**Step 3: Commit**

```bash
git add tests/test_eval_pipeline_e2e.py
git commit -m "test(eval_pipeline): add end-to-end smoke test for two-phase pipeline"
```

---

## Task 9: Lint, regression, and final verification

**Files:** none

**Step 1: Run lint**

Run: `ruff check app/services/eval_pipeline.py scripts/generate_qa_dataset.py scripts/run_evaluation.py tests/test_eval_pipeline.py tests/test_eval_pipeline_e2e.py`

Expected: no errors. If errors, fix in place — do not silence rules.

**Step 2: Run the full test suite**

Run: `pytest tests/ -q`
Expected: all tests pass (existing + new).

**Step 3: Manual smoke check — both CLIs show help**

Run:
```bash
python scripts/generate_qa_dataset.py --help
python scripts/run_evaluation.py --help
```
Expected: both exit 0 with argparse help.

**Step 4: Verify `RAGASEvaluator` untouched**

Run: `git diff evaluation/ragas_evaluator.py`
Expected: empty diff.

Run: `git diff app/services/question_suggestions.py`
Expected: empty diff.

**Step 5: Commit (only if Step 1 produced fixes)**

```bash
git add -u
git commit -m "chore: address lint findings in eval_pipeline"
```

Only commit if there are actual changes from the lint step.

---

## Done

Phase 1 and Phase 2 are now independently runnable:

```bash
# Generate dataset
python scripts/generate_qa_dataset.py \
    --pdfs notes.pdf --out eval.jsonl --num 5

# (Optional: stop llama.cpp, swap model, restart)

# Run evaluation
python scripts/run_evaluation.py \
    --dataset eval.jsonl --out report.csv
```

Both respect per-phase env vars (`QA_GEN_*` / `EVAL_*`) and accept CLI overrides.
