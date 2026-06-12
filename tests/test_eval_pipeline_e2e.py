"""End-to-end test for the two-script pipeline (mocked LLM)."""
import json
import os
from pathlib import Path

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")
django.setup()


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
        "app.services.local_rag.retrieve_with_faiss",
        lambda query, top_k=5, source_filter=None: [
            {"text": "ctx", "source": "x.pdf", "page": 1}
        ],
    )
    monkeypatch.setattr(
        "app.services.local_rag.build_context_from_sources",
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

    from app.services.eval_pipeline import generate_qa_dataset, evaluate_dataset

    count = generate_qa_dataset(
        pdf_paths=[str(pdf)],
        out_path=str(jsonl_path),
        base_url="http://x:8080",
        model="m",
    )
    assert count == 1
    assert json.loads(jsonl_path.read_text(encoding="utf-8").strip())["question"] == "Q1"

    summary = evaluate_dataset(
        dataset_path=str(jsonl_path),
        out_path=str(csv_path),
        base_url="http://x:8080",
        model="m",
    )
    assert summary["num_questions"] == 1
    assert csv_path.exists()
