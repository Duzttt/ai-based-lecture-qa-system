---
name: ragas-evaluation
description: Run RAGAS evaluation on lecture notes, analyze metrics (faithfulness, answer_relevancy, context_precision, context_recall), compare with baselines, and suggest optimizations. Use when the user asks to evaluate RAG quality, analyze RAGAS results, or optimize retrieval performance.
---

# RAGAS Evaluation Workflow

Run RAGAS evaluations on lecture PDFs, analyze the four core metrics, and iteratively optimize the RAG pipeline.

## When To Use

- User asks to evaluate RAG quality on lecture notes
- User pastes a RAGAS evaluation report and asks for analysis
- User wants to compare before/after optimization results
- User asks to optimize chunking, retrieval, or LLM settings for better scores

## Evaluation Commands

### Single PDF
```bash
python tests/test_ragas_eval.py --pdf "media/data_source/<filename>.pdf" --num-questions 5 --top-k 5 --language en
```

### All PDFs
```bash
python tests/test_ragas_eval.py --all --num-questions 5 --top-k 5 --language en
```

### With custom parameters
```bash
python tests/test_ragas_eval.py --pdf "<path>" --num-questions 10 --top-k 10 --language en --ragas-model <model>
```

Results are automatically exported to `evaluation/ragas_results_<timestamp>.csv`.

## Metric Interpretation Guide

| Metric | Good | Acceptable | Poor | What It Measures |
|--------|------|------------|------|------------------|
| **Faithfulness** | >0.80 | 0.60-0.80 | <0.60 | LLM hallucination — does the answer stick to retrieved context? |
| **Answer Relevancy** | >0.85 | 0.70-0.85 | <0.70 | Does the answer address the question? (uses embedding similarity) |
| **Context Precision** | >0.70 | 0.50-0.70 | <0.50 | Are retrieved chunks relevant? (signal-to-noise ratio) |
| **Context Recall** | >0.80 | 0.60-0.80 | <0.60 | Did we retrieve all relevant passages? |

### NaN Indicators
- `answer_relevancy = NaN` → Check that RAGAS judge LLM is properly configured and has API credits
- All metrics NaN → Judge LLM API key is invalid or exhausted

## Optimization Playbook

When metrics are low, apply fixes in this priority order:

### 1. Low Context Precision / Recall (Retrieval Issues)
- **Check chunking config** in `app/config.py`: `CHUNK_SIZE` and `CHUNK_OVERLAP`
  - Default: 400/50. Try 500/100 or 700/120 for lecture notes.
  - Larger chunks preserve semantic units better.
- **Enable hybrid retrieval** in `rag_config.json`: set `"use_hybrid_retrieval": true`
  - BM25 keyword search + dense vector search improves precision.
- **Rebuild FAISS index** after any chunking change:
  ```bash
  python scripts/pdf_to_faiss_with_metadata.py --pdf media/data_source/<file>.pdf
  ```

### 2. Low Faithfulness (LLM Hallucination)
- Use a more capable judge LLM (Gemini, DeepSeek, GPT-4o)
- Reduce `top_k` to give the LLM less noisy context
- Add source grounding prompts

### 3. Low Answer Relevancy
- Check that the question generation uses English prompts
- Ensure `--language en` flag is set for English lectures
- Verify embedding model matches lecture language (all-MiniLM-L6-v2 for English)

### 4. Dependency / API Issues
- RAGAS judge LLM priority chain: CLI args → `RAGAS_*` env vars → OpenRouter → local LLM
- For free evaluation: use NVIDIA API (`build.nvidia.com`) with `meta/llama-3.1-8b-instruct`
- `.env` must have: `RAGAS_API_KEY`, `RAGAS_BASE_URL`, `RAGAS_MODEL`

## Baseline Reference

Record latest results to CSV. Compare future runs against the most recent CSV in `evaluation/`.

## Typical Workflow

1. Run evaluation (single or all PDFs)
2. Read the CSV output and metric scores
3. Identify the weakest metric(s)
4. Apply the corresponding fix from the playbook above
5. If chunking or index changed, rebuild the index
6. Re-run evaluation and compare with previous CSV
7. Repeat until all metrics are in "Good" range

## Files Involved

- `evaluation/ragas_evaluator.py` — Main RAGAS evaluator (heavily customized)
- `tests/test_ragas_eval.py` — CLI entry point for running evaluations
- `app/config.py` — Chunk size/overlap settings (`CHUNK_SIZE`, `CHUNK_OVERLAP`)
- `rag_config.json` — Runtime flags (hybrid retrieval toggle)
- `app/services/vector_store.py` — FAISS index (uses cosine similarity via IndexFlatIP)
- `scripts/pdf_to_faiss_with_metadata.py` — Index rebuild script
- `.env` — API keys for judge LLMs
