# QA-Generation and Evaluation Pipeline Split — Design Document

## 概述

把 `evaluation/ragas_evaluator.py` 中的两个 LLM 工作拆成两个独立可运行的 CLI 脚本：
- `scripts/generate_qa_dataset.py` — 用 LLM 从 PDF 文本生成 Q-A 评估数据集
- `scripts/run_evaluation.py` — 读取该数据集，跑 RAG + RAGAS 评分

两阶段用 JSONL 文件解耦，允许 llama.cpp 服务在两阶段之间重启或换模型。
`RAGASEvaluator` 与 `QuestionSuggestionService` 完全不动。

## 当前状况

| 流程 | 位置 | LLM 配置来源 |
|------|------|--------------|
| 评估中的 QA 生成 | `RAGASEvaluator.generate_qa_from_text()` | 共享 `LLM_PROVIDER` / `LOCAL_LLM_*` |
| RAGAS 评分 judge | `RAGASEvaluator._resolve_ragas_llm_config()` | 同上，env 优先 |
| RAG 答案生成 | `app/services/local_rag.generate()` | 同上 |

两个阶段共用同一组配置，无法指向不同的模型 / 服务器。
当用户希望用不同模型（如 QA 用小模型、judge 用大模型），
或希望在两阶段之间重启 llama.cpp 服务时，无法做到。

## 总体架构

```
                       llama.cpp server (单台)
                       /                    \
                QA_GEN_BASE_URL        EVAL_BASE_URL
                  :8080 / qwen2.5-3b     :8080 / qwen2.5-7b-instruct
                       |                       |
                       v                       v
  ┌──────────────────────────────┐   ┌──────────────────────────────┐
  │ scripts/generate_qa_dataset  │   │ scripts/run_evaluation       │
  │        .py                   │   │        .py                   │
  └──────────────┬───────────────┘   └──────────────▲───────────────┘
                 │                                  │
                 v                                  │
           eval.jsonl  ───────────────────────────┘
            (one Q-A pair per line)
```

```
+------------------------------------------------------+
|        app/services/eval_pipeline.py                |
+------------------------------------------------------+
| generate_qa_dataset(pdfs, *, base_url, model, …)    |
|     → POST {base_url}/v1/chat/completions (Q-A gen) |
|     → write JSONL (atomic via .tmp + rename)        |
|                                                      |
| evaluate_dataset(jsonl_path, *, base_url, model, …)  |
|     → for each Q: retrieve + build_context + answer  |
|     → POST {base_url}/v1/chat/completions (RAG ans)  |
|     → build Dataset                                  |
|     → run RAGAS with same base_url/model as judge    |
|     → write CSV (same shape as ragas_results_*.csv)  |
+------------------------------------------------------+
```

## 新增文件

| 路径 | 作用 |
|------|------|
| `app/services/eval_pipeline.py` | 共享的纯函数：QA 生成 + 数据集评估。无 Django 依赖。 |
| `scripts/generate_qa_dataset.py` | CLI 入口 1：argparse + 日志 + 调 `generate_qa_dataset` |
| `scripts/run_evaluation.py` | CLI 入口 2：argparse + 日志 + 调 `evaluate_dataset` |
| `tests/test_eval_pipeline.py` | 单元测试，使用 `monkeypatch` mock `requests.post` |

## 配置

在 `app/config.py` 末尾追加：

```python
QA_GEN_BASE_URL: Optional[str] = None
QA_GEN_MODEL: Optional[str] = None
QA_GEN_TIMEOUT_SECONDS: int = 120

EVAL_BASE_URL: Optional[str] = None
EVAL_MODEL: Optional[str] = None
EVAL_TIMEOUT_SECONDS: int = 300
EVAL_MAX_WORKERS: int = 4
```

**解析顺序**（在 `eval_pipeline.py` 中）：

1. CLI flag `--base-url` / `--model`（最高优先级）
2. 阶段 env var（`QA_GEN_BASE_URL` / `EVAL_BASE_URL`）
3. 全局回退（`LOCAL_LLM_BASE_URL` / `LOCAL_LLM_MODEL`）

`.env` 示例（单台 llama.cpp 服务 + 两个模型）：

```dotenv
QA_GEN_BASE_URL=http://localhost:8080
QA_GEN_MODEL=qwen2.5-3b
EVAL_BASE_URL=http://localhost:8080
EVAL_MODEL=qwen2.5-7b-instruct
```

## 数据契约：JSONL schema

一行一个 Q-A 记录，UTF-8：

```json
{"question": "What is RAG?", "ground_truth": "Retrieval-Augmented Generation is ..."}
```

字段说明：
- `question` (str) — 必填，RAG 要回答的问题
- `ground_truth` (str) — 必填，参考答案

## CLI 用法

### Phase 1: 生成评估数据集

```bash
python scripts/generate_qa_dataset.py \
    --pdfs data/notes_week1.pdf,data/notes_week2.pdf \
    --out outputs/eval_dataset.jsonl \
    --num 5 \
    --lang en
```

可选 flag：
- `--base-url http://gpu-b:8080` — 覆盖 `QA_GEN_BASE_URL`
- `--model qwen2.5-7b-instruct` — 覆盖 `QA_GEN_MODEL`
- `--log-file eval_gen.log`

### Phase 2: 跑评估

```bash
python scripts/run_evaluation.py \
    --dataset outputs/eval_dataset.jsonl \
    --out outputs/eval_report.csv \
    --top-k 5
```

可选 flag：
- `--base-url` / `--model` — 覆盖 `EVAL_BASE_URL` / `EVAL_MODEL`
- `--log-file eval_run.log`

## 错误处理

### `generate_qa_dataset.py`

| 场景 | 行为 |
|------|------|
| PDF 路径不存在 | 记录 warning，跳过该 PDF，继续 |
| 文本提取为空 | 静默跳过 |
| LLM 返回无法解析的 JSON | 重试一次（追加 "Return ONLY valid JSON" 到 prompt），仍失败则跳过该 PDF 并把原始响应写入 `--log-file` |
| `requests.exceptions.Timeout` (>`QA_GEN_TIMEOUT_SECONDS`) | 重试一次并把文本截断到 2000 字符，仍超时则跳过 |
| 启动时连不上 llama.cpp | 致命退出，stderr 打印：`Cannot reach {base_url}. Is the llama.cpp server running?` |
| JSONL 写入中断 | 写到 `eval.jsonl.tmp`，最后 rename，保证原子性 |

### `run_evaluation.py`

| 场景 | 行为 |
|------|------|
| JSONL 不存在 | 致命退出，code 1 |
| `len(questions) != len(ground_truths)` | 抛出 `DatasetFormatError`，致命退出 |
| 单条问题的 RAG 答案失败 | 记 `answer=""`, `contexts=[]`，继续下一条（RAGAS 会跳过） |
| RAGAS 整体抛错 | 写部分 CSV（已评分的行），然后致命退出 |
| 启动时连不上 llama.cpp | 致命退出，stderr 打印清晰错误 |

### 自定义异常（`app/services/eval_pipeline.py`）

```python
class EvalPipelineError(Exception): ...
class QAJsonParseError(EvalPipelineError): ...
class DatasetFormatError(EvalPipelineError): ...
```

## 测试

新文件 `tests/test_eval_pipeline.py`，mock `requests.post` 不打真实服务。

| 测试 | 验证 |
|------|------|
| `test_generate_qa_dataset_writes_jsonl` | mock 返回 3 个有效 Q-A 对；JSONL 3 行、schema 正确、utf-8 |
| `test_generate_qa_dataset_skips_invalid_pdf` | 路径不存在 → warning，文件为空，exit 0 |
| `test_generate_qa_dataset_retries_bad_json` | 第 1 次返回乱码、第 2 次有效；断言重试一次且最终 JSONL 正确 |
| `test_generate_qa_dataset_falls_back_to_truncated_text` | 第 1 次超时、第 2 次（截断 prompt）成功；断言两次调用均发生 |
| `test_evaluate_dataset_reads_jsonl` | mock RAG + judge；CSV 有 4 个指标列 + 每行数据 |
| `test_evaluate_dataset_continues_on_single_question_failure` | 第 2 题抛错；CSV 仍有 Q1 和 Q3 |
| `test_evaluate_dataset_fails_on_length_mismatch` | 3 questions / 2 truths → `DatasetFormatError` |
| `test_resolution_precedence` | CLI > env > LOCAL_LLM_*（参数化） |
| `test_resolve_eval_url_appends_v1` | 裸 URL 自动加 `/v1` 后缀（与现有 `_resolve_ragas_llm_config` 一致） |

Mock 策略：
- `monkeypatch.setattr("requests.post", mock_post)` — 返回固定 OpenAI 兼容 JSON
- RAGAS 调用包在 `run_ragas_metrics(dataset, llm, embeddings)` 薄函数里，测试在该边界 mock

**回归保护**：`RAGASEvaluator`、`QuestionSuggestionService` 一行未改，
`pytest tests/` 全部通过的回归风险为零。

## 与现有代码的关系

- `RAGASEvaluator.generate_qa_from_text` —— **不删**，旧路径继续可用
- `RAGASEvaluator.evaluate_from_jsonl` —— **不删**，旧路径继续可用
- `RAGASEvaluator._parse_qa_json` —— **不删**，新模块独立实现等价函数
  （避免新模块反向依赖 `RAGASEvaluator`，保持单向依赖）
- `app/services/local_rag.retrieve_with_faiss` / `build_context_from_sources` —— **复用**

## 不包含的范围

- 不修改 `RAGASEvaluator` / `QuestionSuggestionService` 内部
- 不新增 Django view 或前端 UI
- 不修改 FAISS 索引格式
- 不引入 RAGAS 之外的评估框架
- 不把 judge LLM 与 RAG 答案生成 LLM 拆成两个独立 env 组（YAGNI：
  现阶段 RAGAS judge 与 RAG 答案用同一组 `EVAL_BASE_URL` / `EVAL_MODEL`）
