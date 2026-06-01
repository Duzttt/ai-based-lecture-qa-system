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
