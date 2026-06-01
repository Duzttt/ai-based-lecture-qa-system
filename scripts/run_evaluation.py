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
