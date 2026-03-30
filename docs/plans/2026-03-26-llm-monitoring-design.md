# LLM 调用监控后台 — 设计文档

## 概述

为 RAG 系统添加 LLM 调用监控功能，通过独立页面查看所有 LLM 调用记录，支持按提供商筛选。

## 背景

当前项目有 3 个 LLM 提供商（Gemini、OpenRouter、本地 Qwen），分布在 5 个服务模块中调用：
- `app/services/local_rag.py` — 主要问答生成
- `app/services/rag_pipeline.py` — RAGPipeline 类
- `app/services/citation_rag.py` — 引用感知 RAG
- `app/services/summarizer.py` — 文档摘要
- `app/services/question_suggestions.py` — 问题建议

目前只有 `ask_qwen` 视图通过 `log_query()` 记录查询日志，其他调用路径没有记录。需要统一采集所有 LLM 调用并提供可视化页面。

## 需求

- **监控内容**: 基础调用记录 — 时间、提供商、模型、响应时间、成功/失败状态、错误信息
- **UI 形式**: 独立新页面（`/llm-logs`）
- **筛选**: 按 LLM 提供商筛选
- **数据采集**: 所有 LLM 调用（问答 + 摘要 + 问题建议 + citation）
- **数据存储**: 扩展现有 `QueryLog` 模型

## 设计方案

采用 **方案 1：集中式 LLM 调用包装函数**。创建统一的 `call_llm()` 函数，所有服务模块通过它调用 LLM，集中处理计时和日志记录。

### 1. 数据模型 — 扩展 QueryLog

在 `django_app/models.py` 的 `QueryLog` 模型中添加以下字段：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `llm_provider` | CharField(20) | `""` | LLM 提供商：gemini / openrouter / local_qwen |
| `llm_status` | CharField(10) | `"success"` | 调用状态：success / error |
| `error_message` | TextField | `""` | 失败时的错误信息 |
| `call_type` | CharField(20) | `"qa"` | 调用类型：qa / summary / suggestion / citation |

添加索引：
- `models.Index(fields=["llm_provider"])`
- `models.Index(fields=["llm_status"])`

### 2. 集中式 LLM 包装函数

新建 `app/services/llm_client.py`，提供：

```python
def call_llm(
    provider: str,           # "gemini" / "openrouter" / "local_qwen"
    model: str,              # 模型名称
    call_type: str,          # "qa" / "summary" / "suggestion" / "citation"
    messages: list[dict],    # 标准 messages 格式 [{"role": "system", "content": ...}, ...]
    timeout: int = 60,
    **kwargs                 # provider 特定参数（temperature 等）
) -> str
```

内部流程：
1. 记录 `start_time`
2. 根据 `provider` 调用对应的 HTTP 请求（复用现有逻辑）
3. 记录 `end_time`，计算 `latency_ms`
4. 无论成功或失败，都写入 `QueryLog`
5. 成功时返回 response text，失败时 raise 原始异常

### 3. 服务模块改造

5 个服务模块需要改造，将直接的 HTTP 调用替换为 `call_llm()` 调用：

- `local_rag.py`: `generate_with_local_qwen()`、`generate_with_openrouter()`
- `rag_pipeline.py`: `_generate_gemini()`、`_generate_openrouter()`
- `citation_rag.py`: `_generate_with_qwen()`、`generate_with_openrouter()`
- `summarizer.py`: `_call_local_qwen()`、`_call_gemini()`、`_call_openrouter()`
- `question_suggestions.py`: `_call_local_qwen()`、`_call_gemini()`、`_call_openrouter()`

每个模块的 `_call_*` 方法改为构建 messages 并调用 `call_llm()`。

### 4. API 接口

新增在 `django_app/views/llm_logs.py`：

**`GET /api/llm-logs/`**
- 查询参数: `provider`, `call_type`, `page`, `page_size`
- 返回: 调用记录 JSON 列表

**`GET /api/llm-logs/stats/`**
- 返回: 总调用次数、各 provider 调用次数、平均延迟、错误率

### 5. 前端页面

新建 `django_app/templates/llm_logs.html`：

- 顶部统计卡片：总调用次数、平均延迟、错误率
- 调用记录表格：时间 | 调用类型 | Provider | 模型 | 延迟(ms) | 状态 | 错误信息
- Provider 筛选下拉框
- 分页导航
- 自动刷新按钮

### 6. URL 路由

在 `django_backend/urls.py` 中添加：
- `path("llm-logs", llm_logs_page)` — 渲染页面
- `path("api/llm-logs/", llm_logs_list)` — API 接口
- `path("api/llm-logs/stats/", llm_logs_stats)` — 统计接口

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `django_app/models.py` | 修改 | 扩展 QueryLog 模型 |
| `app/services/llm_client.py` | 新建 | 集中式 LLM 包装函数 |
| `app/services/local_rag.py` | 修改 | 使用 call_llm() |
| `app/services/rag_pipeline.py` | 修改 | 使用 call_llm() |
| `app/services/citation_rag.py` | 修改 | 使用 call_llm() |
| `app/services/summarizer.py` | 修改 | 使用 call_llm() |
| `app/services/question_suggestions.py` | 修改 | 使用 call_llm() |
| `django_app/views/llm_logs.py` | 新建 | LLM 日志 API 视图 |
| `django_app/views/__init__.py` | 修改 | 导出新视图 |
| `django_app/templates/llm_logs.html` | 新建 | 前端页面 |
| `django_backend/urls.py` | 修改 | 添加路由 |

## 测试策略

- 单元测试 `call_llm()` 函数：mock HTTP 请求，验证日志写入
- 测试 API 接口：验证筛选、分页功能
- 测试各服务模块改造后的功能不变
