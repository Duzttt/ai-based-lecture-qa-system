"""Tests for app.services.eval_pipeline."""
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()

import pytest

from app.config import Settings
from app.services.eval_pipeline import resolve_endpoint, EvalPipelineError


def _make_settings(monkeypatch, **overrides) -> Settings:
    """Create a Settings instance with relevant env vars cleared, then apply overrides.

    We mutate the instance directly (via monkeypatch.setattr) because pydantic-settings
    reads env at construction time and ``LOCAL_LLM_*`` have non-None defaults, so
    setenv/delenv alone cannot produce a "fully unset" Settings.
    """
    for key in (
        "QA_GEN_BASE_URL", "QA_GEN_MODEL", "QA_GEN_TIMEOUT_SECONDS",
        "EVAL_BASE_URL", "EVAL_MODEL", "EVAL_TIMEOUT_SECONDS",
        "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL",
    ):
        monkeypatch.delenv(key, raising=False)
    settings = Settings()
    for k, v in overrides.items():
        monkeypatch.setattr(settings, k, v)
    return settings


def test_resolve_endpoint_cli_flag_wins(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        QA_GEN_BASE_URL="http://env:8080",
        QA_GEN_MODEL="env-model",
    )
    base_url, model = resolve_endpoint(
        phase="qa_gen", settings=settings,
        cli_base_url="http://cli:9090", cli_model="cli-model",
    )
    assert base_url == "http://cli:9090/v1"
    assert model == "cli-model"


def test_resolve_endpoint_env_var_falls_back(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        QA_GEN_BASE_URL="http://env:8080",
        QA_GEN_MODEL="env-model",
        LOCAL_LLM_BASE_URL="http://local:8080",
        LOCAL_LLM_MODEL="local-model",
    )
    base_url, model = resolve_endpoint(phase="qa_gen", settings=settings)
    assert base_url == "http://env:8080/v1"
    assert model == "env-model"


def test_resolve_endpoint_uses_local_llm_fallback(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL="http://local:8080",
        LOCAL_LLM_MODEL="local-model",
    )
    base_url, model = resolve_endpoint(phase="eval", settings=settings)
    assert base_url == "http://local:8080/v1"
    assert model == "local-model"


def test_resolve_endpoint_appends_v1(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL="http://local:8080",
        LOCAL_LLM_MODEL="m",
    )
    base_url, _ = resolve_endpoint(phase="qa_gen", settings=settings)
    assert base_url.endswith("/v1")


def test_resolve_endpoint_strips_trailing_v1_then_readds(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL="http://local:8080/v1/",
        LOCAL_LLM_MODEL="m",
    )
    base_url, _ = resolve_endpoint(phase="qa_gen", settings=settings)
    assert base_url == "http://local:8080/v1"


def test_resolve_endpoint_raises_when_unset(monkeypatch):
    settings = _make_settings(
        monkeypatch,
        LOCAL_LLM_BASE_URL=None,
        LOCAL_LLM_MODEL=None,
    )
    with pytest.raises(EvalPipelineError):
        resolve_endpoint(phase="eval", settings=settings)


from app.services.eval_pipeline import _parse_qa_json, _call_chat


def test_parse_qa_json_strips_markdown_fences():
    raw = '```json\n[{"question": "q", "ground_truth": "a"}]\n```'
    assert _parse_qa_json(raw) == [{"question": "q", "ground_truth": "a"}]


def test_parse_qa_json_extracts_array_from_extra_text():
    raw = 'Here you go: [{"question": "q1", "ground_truth": "a1"}] enjoy!'
    assert _parse_qa_json(raw) == [{"question": "q1", "ground_truth": "a1"}]


def test_parse_qa_json_repairs_truncated_array():
    raw = '[{"question": "q1", "ground_truth": "a1"}, {"question": "q2", "ground_trut'
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


import os
import requests
from app.services.eval_pipeline import generate_qa_dataset, evaluate_dataset


def test_generate_qa_dataset_writes_jsonl(tmp_path, monkeypatch):
    pdf_path = tmp_path / "notes.pdf"
    pdf_path.write_bytes(b"%PDF-stub")
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
    assert call_count["n"] == 2


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


def test_evaluate_dataset_reads_jsonl_and_writes_csv(tmp_path, monkeypatch):
    ds_path = tmp_path / "eval.jsonl"
    ds_path.write_text(
        '{"question": "Q1", "ground_truth": "A1"}\n'
        '{"question": "Q2", "ground_truth": "A2"}\n',
        encoding="utf-8",
    )
    out_path = tmp_path / "report.csv"

    monkeypatch.setattr(
        "app.services.local_rag.retrieve_with_faiss",
        lambda query, top_k=5, source_filter=None: [
            {"text": f"context for {query}", "source": "x.pdf", "page": 1}
        ],
    )
    monkeypatch.setattr(
        "app.services.local_rag.build_context_from_sources",
        lambda sources: "ctx",
    )

    def fake_call_chat(*, base_url, model, messages, timeout, num_predict=None):
        return f"answer to {messages[-1]['content'][:30]}"

    monkeypatch.setattr("app.services.eval_pipeline._call_chat", fake_call_chat)

    def fake_ragas(dataset, llm, embeddings, timeout, max_workers):
        class Pandas:
            def to_dict(self, orient="records"):
                return [
                    {"question": r["question"], "faithfulness": 0.9}
                    for r in dataset.to_list()
                ]

            def to_csv(self, path, index=False, encoding="utf-8"):
                Path(path).write_text(
                    "question,faithfulness\n" + "\n".join(
                        f"{r['question']},0.9" for r in dataset.to_list()
                    ),
                    encoding=encoding,
                )

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
        "app.services.local_rag.retrieve_with_faiss", fake_retrieve
    )
    monkeypatch.setattr(
        "app.services.local_rag.build_context_from_sources", lambda s: "ctx"
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline._call_chat",
        lambda **kw: "ans",
    )

    def fake_ragas(dataset, llm, embeddings, timeout, max_workers):
        class Pandas:
            def to_dict(self, orient="records"):
                return list(dataset.to_list())

            def to_csv(self, path, index=False, encoding="utf-8"):
                Path(path).write_text(
                    "question\n" + "\n".join(r["question"] for r in dataset.to_list()),
                    encoding=encoding,
                )

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


def test_evaluate_dataset_raises_on_missing_field(tmp_path, monkeypatch):
    """Missing ``ground_truth`` raises ``DatasetFormatError``."""
    from app.services.eval_pipeline import DatasetFormatError, evaluate_dataset

    bad_path = tmp_path / "bad.jsonl"
    bad_path.write_text('{"question": "Q1"}\n', encoding="utf-8")

    monkeypatch.setattr(
        "app.services.local_rag.retrieve_with_faiss", lambda **kw: []
    )
    monkeypatch.setattr(
        "app.services.local_rag.build_context_from_sources", lambda s: ""
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline._call_chat", lambda **kw: "ans"
    )
    monkeypatch.setattr(
        "app.services.eval_pipeline._run_ragas_metrics", lambda *a, **kw: None
    )

    with pytest.raises(DatasetFormatError):
        evaluate_dataset(
            dataset_path=str(bad_path),
            out_path=str(tmp_path / "out.csv"),
            base_url="http://x:8080",
            model="m",
        )
