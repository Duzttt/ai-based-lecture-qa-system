# Retrieval Quality Improvement — Design Document

## 概述

在 RAGAS 评估完成的基础上，系统性地提升检索质量。分为三个 Phase 递进实施：Hybrid 检索持久化 → Cross-Encoder Re-ranking → Query 理解与扩展。

## 当前瓶颈

| 指标 | 当前状况 | 根因 |
|------|---------|------|
| Recall@5 | ~81% (dense only) | 无 BM25 关键词匹配 |
| Context Precision | 部分 query 低至 0.0 | top-k 含不相关 chunk |
| Answer Relevancy | 部分 query 低至 0.25 | query 简短模糊导致检索覆盖面不足 |
| 查询延迟 (Hybrid) | 每次重建索引 | HybridRetriever 未持久化 |

## 总体架构

```
User Query
  │
  ▼
QueryAnalyzer (Phase 3)
  ├─ 分类: simple → BM25, complex → Hybrid
  └─ 扩展: 短 query/缩略语 → LLM 生成同义表述
  │
  ▼
HybridRetrieverService (Phase 1) — 单例，只构建一次
  ├─ BM25Index (cached)
  ├─ DenseRetriever (cached)
  └─ RRF fusion → top-10
  │
  ▼
CrossEncoderReranker (Phase 2) — top-10 → 重排序 → top-3
  │
  ▼
build_context_from_sources() → LLM generate
```

## Phase 1: Hybrid 检索持久化

**目标**：HybridRetriever 只构建一次，默认启用。

### 实现

- 新建 `app/services/hybrid_retriever_service.py`
  - `HybridRetrieverService` 全局单例（`threading.Lock()` 保证线程安全）
  - `get_instance()` → 懒加载，从 `VectorStore.chunks` 构建
  - `refresh()` → 在 PDF 索引完成后调用，重建 BM25 + Dense
  - `search(query, top_k)` → 使用 RRF 融合，返回格式化结果

- 修改 `app/services/local_rag.py`
  - `_is_hybrid_enabled()` → 默认返回 `True`，移除 `use_hybrid_retrieval` 配置
  - `retrieve_with_faiss()` → 直接调用 `HybridRetrieverService.get_instance().search()`
  - 保留 fallback 到纯 dense（当 hybrid 不可用时）

- 修改 `app/services/pdf_indexing.py`
  - 索引完成后调用 `HybridRetrieverService.refresh()`

### 数据流

```
上传 PDF
  → pdf_indexing.index_pdf_file()
    → VectorStore.add_embeddings()
    → VectorStore.save()
    → HybridRetrieverService.refresh()  ← 新增

查询
  → retrieve_with_faiss()
    → HybridRetrieverService.get_instance()
      → BM25Index.search()   (内存中，~12ms)
      → DenseRetriever.search() (内存中，~145ms)
      → RRF fusion (~5ms)
```

## Phase 2: Cross-Encoder Re-ranking

**目标**：提升 Context Precision，确保送入 LLM 的 top-k 全部高相关。

### 实现

- 新建 `app/services/reranker.py`
  - `CrossEncoderReranker` 类
  - `__init__` → 按需加载 `cross-encoder/ms-marco-MiniLM-L-6-v2`
  - `rerank(query, documents, top_k=3)` → `[(doc, score)]`
  - 模型文件缓存到本地，避免重复下载

- 集成到 `HybridRetrieverService`
  - `search()` 新增 `rerank=True` 参数
  - hybrid 返回 top-10 → CrossEncoder 打分 → 返回 top-3

- 延迟预算：CrossEncoder rerank 约 50–100ms，总计延迟 < 300ms (p95)

### 配置
```python
RERANKER_CONFIG = {
    "enabled": True,
    "model_name": "cross-encoder/ms-marco-MiniLM-L-6-v2",
    "top_k_after_rerank": 3,
    "candidate_count": 10,  # hybrid 返回数，供 reranker 重排
}
```

## Phase 3: Query 理解与扩展

**目标**：解决简短/模糊 query 导致的检索覆盖率不足。

### 实现

- 新建 `app/services/query_analyzer.py`
  - `QueryAnalyzer.analyze(query)` → `{"type": "...", "expanded_queries": [...]}`
  - 分类逻辑：
    - 词数 < 5 → `"short"`
    - 包含大写缩略语（如 CDPS, CNP, RRF）→ `"has_acronym"`
    - 其他 → `"normal"`
  - `"short"` 或 `"has_acronym"` 触发 LLM 扩展，否则直接返回原 query

- 集成到 `retrieve_with_faiss()`
  - 分析 query → 需要扩展时调用 LLM 生成 2–3 个同义表述
  - 多个扩展 query 分别检索 → 按最高分去重合并
  - 总检索量限制：最多 3 个扩展 query × top-10 = 30 个候选

### LLM Prompt
```
Generate 2-3 alternative phrasings of this question for document search.
Make them more specific and include synonyms for key terms.
Return as a JSON array of strings.

Original: "{query}"
```

## 测试与验收标准

| Phase | 新文件 | 测试重点 | 验收指标 |
|-------|-------|---------|---------|
| 1 | `test_hybrid_retriever_service.py` | 单例、刷新、fallback | p95 < 200ms, Recall@5 ≥ 85% |
| 2 | `test_reranker.py` | 排序正确性、模型加载 | Context Precision ≥ 0.85 |
| 3 | `test_query_analyzer.py` | 分类、扩展、合并去重 | Recall@5 ≥ 90%, Answer Relevancy ≥ 0.85 |

端到端回归：`pytest tests/` 全部通过，RAGAS CSV 报告与基线对比。

## 不包含的范围

- 不改变 LLM 生成逻辑（SYSTEM_PROMPT、call_llm 保持不变）
- 不新增前端 UI（检索质量提升对用户透明）
- 不修改 FAISS 索引格式（兼容现有 `VectorStore`）
