"""
RAGAS Evaluation Example Script.

This script demonstrates how to use RAGAS to evaluate the RAG pipeline.

Usage:
    # Evaluate from PDF files (auto-generate questions)
    python tests/test_ragas_eval.py --pdf media/data_source/your_file.pdf

    # Evaluate from JSONL file (pre-defined questions)
    python tests/test_ragas_eval.py --jsonl tests/eval_dataset.jsonl

    # Evaluate with custom settings
    python tests/test_ragas_eval.py --pdf media/data_source/your_file.pdf --num-questions 10 --top-k 5 --language zh
"""

import argparse
import os
import sys
import types
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_sample_jsonl(output_path: str) -> None:
    """Create a sample JSONL evaluation dataset."""
    sample_data = [
        {
            "question": "What is machine learning?",
            "ground_truth": "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience without being explicitly programmed.",
        },
        {
            "question": "What are the main types of machine learning?",
            "ground_truth": "The main types of machine learning are supervised learning, unsupervised learning, and reinforcement learning.",
        },
        {
            "question": "What is deep learning?",
            "ground_truth": "Deep learning is a subset of machine learning that uses neural networks with multiple layers to model complex patterns in data.",
        },
    ]

    import json

    with open(output_path, "w", encoding="utf-8") as f:
        for item in sample_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Created sample JSONL at: {output_path}")


def test_evaluate_passes_local_embeddings_to_ragas(monkeypatch):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()

    from evaluation.ragas_evaluator import RAGASEvaluator

    evaluator = RAGASEvaluator()
    local_embeddings = object()
    captured = {}

    monkeypatch.setattr(
        evaluator,
        "run_rag_pipeline",
        lambda questions, top_k=5: [
            {
                "question": question,
                "answer": "generated answer",
                "contexts": ["retrieved context"],
            }
            for question in questions
        ],
    )
    monkeypatch.setattr(
        evaluator,
        "_build_ragas_embeddings",
        lambda: local_embeddings,
        raising=False,
    )

    class FakeFrame:
        def to_dict(self, orient=None):
            return [{"faithfulness": 1.0}]

    class FakeRagasResult:
        def to_pandas(self):
            return FakeFrame()

    def fake_ragas_evaluate(**kwargs):
        captured.update(kwargs)
        return FakeRagasResult()

    import ragas

    monkeypatch.setattr(ragas, "evaluate", fake_ragas_evaluate)

    result = evaluator.evaluate(["What is ML?"], ["Machine learning"])

    assert result["num_questions"] == 1
    assert captured["embeddings"] is local_embeddings
    assert captured["run_config"].timeout == 300
    assert captured["run_config"].max_workers == 4


def test_ragas_llm_config_uses_runtime_local_llm(monkeypatch):
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()

    import evaluation.ragas_evaluator as ragas_evaluator
    from evaluation.ragas_evaluator import RAGASEvaluator

    monkeypatch.delenv("RAGAS_API_KEY", raising=False)
    monkeypatch.delenv("RAGAS_BASE_URL", raising=False)
    monkeypatch.delenv("RAGAS_MODEL", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setattr(ragas_evaluator.settings, "OPENROUTER_API_KEY", None)
    monkeypatch.setattr(
        ragas_evaluator,
        "load_runtime_llm_settings",
        lambda: {
            "provider": "local_llm",
            "model": "Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M",
            "api_key": None,
            "base_url": "http://localhost:8080",
        },
    )

    config = RAGASEvaluator()._resolve_ragas_llm_config()

    assert config["api_key"] == "local"
    assert config["base_url"] == "http://localhost:8080/v1"
    assert config["model"] == "Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M"


def test_main_all_evaluates_pdfs_from_documents_path(monkeypatch, tmp_path):
    (tmp_path / "a.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "b.pdf").write_bytes(b"%PDF-1.4\n")
    (tmp_path / "notes.txt").write_text("ignore me", encoding="utf-8")

    captured = {}

    class FakeEvaluator:
        def evaluate_from_pdfs(self, **kwargs):
            captured.update(kwargs)
            return {"num_questions": 0, "metrics": {}}

        @staticmethod
        def format_report(result):
            return "ok"

    monkeypatch.setattr(
        sys,
        "argv",
        [
            "test_ragas_eval.py",
            "--all",
            "--num-questions",
            "2",
            "--top-k",
            "3",
            "--language",
            "en",
        ],
    )
    monkeypatch.setitem(sys.modules, "django", types.SimpleNamespace(setup=lambda: None))
    monkeypatch.setitem(
        sys.modules,
        "app.config",
        types.SimpleNamespace(settings=types.SimpleNamespace(DOCUMENTS_PATH=str(tmp_path))),
    )
    monkeypatch.setitem(
        sys.modules,
        "evaluation.ragas_evaluator",
        types.SimpleNamespace(RAGASEvaluator=FakeEvaluator),
    )

    main()

    assert captured["pdf_paths"] == [
        str(tmp_path / "a.pdf"),
        str(tmp_path / "b.pdf"),
    ]
    assert captured["num_questions_per_pdf"] == 2
    assert captured["top_k"] == 3
    assert captured["language"] == "en"


def main():
    parser = argparse.ArgumentParser(description="RAGAS Evaluation Script")
    parser.add_argument(
        "--pdf",
        type=str,
        nargs="+",
        help="PDF file paths to evaluate",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Evaluate all PDFs in media/data_source/",
    )
    parser.add_argument(
        "--jsonl",
        type=str,
        help="JSONL file with pre-defined questions",
    )
    parser.add_argument(
        "--num-questions",
        type=int,
        default=5,
        help="Number of questions per PDF (default: 5)",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of chunks to retrieve (default: 5)",
    )
    parser.add_argument(
        "--language",
        type=str,
        default="en",
        choices=["en", "zh"],
        help="Language for generated questions (default: en)",
    )
    parser.add_argument(
        "--ragas-timeout",
        type=int,
        default=300,
        help="RAGAS per-job timeout in seconds (default: 300)",
    )
    parser.add_argument(
        "--ragas-model",
        type=str,
        help="OpenAI-compatible judge model for RAGAS metrics",
    )
    parser.add_argument(
        "--ragas-api-key",
        type=str,
        help="OpenAI-compatible API key for RAGAS metrics",
    )
    parser.add_argument(
        "--ragas-base-url",
        type=str,
        help="OpenAI-compatible base URL for RAGAS metrics",
    )
    parser.add_argument(
        "--ragas-max-workers",
        type=int,
        default=4,
        help="Maximum concurrent RAGAS metric jobs (default: 4)",
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Create a sample JSONL file",
    )

    args = parser.parse_args()

    # Create sample JSONL if requested
    if args.create_sample:
        sample_path = "tests/eval_dataset.jsonl"
        create_sample_jsonl(sample_path)
        print(f"\nEdit {sample_path} with your own questions, then run:")
        print(f"  python tests/test_ragas_eval.py --jsonl {sample_path}")
        return

    # Validate arguments
    if not args.pdf and not args.jsonl and not args.all:
        print("Error: Please provide --pdf, --all, or --jsonl argument")
        print("Run with --help for usage information")
        sys.exit(1)

    # Import Django settings
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "django_backend.settings")

    import django

    django.setup()

    # Run evaluation
    from evaluation.ragas_evaluator import RAGASEvaluator
    from app.config import settings

    evaluator = RAGASEvaluator()

    try:
        if args.jsonl:
            print(f"Evaluating from JSONL: {args.jsonl}")
            result = evaluator.evaluate_from_jsonl(
                jsonl_path=args.jsonl,
                top_k=args.top_k,
                openai_api_key=args.ragas_api_key,
                openai_base_url=args.ragas_base_url,
                ragas_model=args.ragas_model,
                ragas_timeout=args.ragas_timeout,
                ragas_max_workers=args.ragas_max_workers,
            )
        else:
            # Get PDF paths
            if args.all:
                data_dir = Path(settings.DOCUMENTS_PATH)
                pdf_paths = sorted(str(p) for p in data_dir.glob("*.pdf"))
                if not pdf_paths:
                    print(f"No PDF files found in {data_dir}")
                    sys.exit(1)
                print(f"Found {len(pdf_paths)} PDFs in {data_dir}")
            else:
                pdf_paths = args.pdf

            print(f"Evaluating {len(pdf_paths)} PDFs...")
            result = evaluator.evaluate_from_pdfs(
                pdf_paths=pdf_paths,
                num_questions_per_pdf=args.num_questions,
                top_k=args.top_k,
                language=args.language,
                openai_api_key=args.ragas_api_key,
                openai_base_url=args.ragas_base_url,
                ragas_model=args.ragas_model,
                ragas_timeout=args.ragas_timeout,
                ragas_max_workers=args.ragas_max_workers,
            )

        # Print report
        report = RAGASEvaluator.format_report(result)
        print("\n" + report)

        # Export detailed results to CSV
        import csv
        from datetime import datetime

        csv_path = f"evaluation/ragas_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        detailed = result.get("detailed", [])
        if detailed:
            os.makedirs("evaluation", exist_ok=True)
            with open(csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=detailed[0].keys())
                writer.writeheader()
                writer.writerows(detailed)
            print(f"\nDetailed results exported to: {csv_path}")

    except Exception as exc:
        print(f"Evaluation failed: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
