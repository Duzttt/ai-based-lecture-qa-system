---
description: Run RAGAS evaluation on lecture PDFs and output metrics (faithfulness, answer_relevancy, context_precision, context_recall). Results auto-exported to CSV.
agent: mimo
---

Run RAGAS evaluation on lecture notes.

**Arguments**: `$ARGUMENTS` — optional flags like `--pdf <path>`, `--all`, `--num-questions N`, `--top-k N`, `--language en`

Default command if no arguments given:
```bash
python tests/test_ragas_eval.py --all --num-questions 5 --top-k 5 --language en
```

If the user provides a specific PDF path, use `--pdf "<path>"` instead of `--all`.
If the user provides other flags, include them.

After running, read the output metrics and provide a brief analysis following the RAGAS evaluation skill playbook (check `.mimocode/skills/ragas-evaluation/SKILL.md` for metric interpretation and optimization guidance).

Compare with the most recent CSV in `evaluation/` to show progress.
