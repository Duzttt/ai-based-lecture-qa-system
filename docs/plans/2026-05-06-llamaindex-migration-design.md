# LlamaIndex迁移设计文档

## 概述

本设计文档描述了将现有RAG系统从LangChain迁移到LlamaIndex的方案。采用混合迁移策略，关键组件迁移到LlamaIndex，保留部分现有实现。

## 用户需求

1. **迁移动机**：更简单的API
2. **迁移策略**：混合方案（在特定场景使用LlamaIndex，其他场景保留现有实现）
3. **替换范围**：向量存储、文档加载、文本分割、RAG管道
4. **LLM兼容性**：使用LlamaIndex的LLM集成，支持Gemini、OpenRouter和本地llama.cpp
5. **验证方式**：添加新测试和性能基准测试

## 整体架构

采用混合方案，关键组件迁移到LlamaIndex，保留部分现有实现：

1. **文档加载**：保留现有的`PDFLoader`，添加LlamaIndex文档适配器
2. **文本分割**：迁移到LlamaIndex的`SentenceSplitter`
3. **向量存储**：迁移到LlamaIndex的FAISS集成
4. **RAG管道**：迁移到LlamaIndex的查询引擎
5. **LLM集成**：使用LlamaIndex的LLM抽象，支持Gemini、OpenRouter和本地llama.cpp

## 详细设计

### 文档加载

保留现有的`PDFLoader`，但添加LlamaIndex文档适配器：

- **现有实现**：`app/services/pdf_loader.py` 使用LangChain的`PyPDFLoader`
- **适配器模式**：创建`LlamaDocumentAdapter`将现有PDF加载器输出转换为LlamaIndex的`Document`格式
- **兼容性**：保持现有的PDF解析逻辑不变，只添加格式转换

```python
# 新增文件：app/services/llama_document_adapter.py
class LlamaDocumentAdapter:
    @staticmethod
    def from_pdf_loader(pdf_loader_output):
        """将PDF加载器输出转换为LlamaIndex Document格式"""
        # 转换逻辑
```

### 文本分割

迁移到LlamaIndex的`SentenceSplitter`：

- **替换实现**：将`app/services/chunker.py`中的LangChain `RecursiveCharacterTextSplitter`替换为LlamaIndex的`SentenceSplitter`
- **配置兼容**：保持现有的`chunk_size`和`chunk_overlap`参数
- **API保持**：保持`TextChunker`类的公共API不变

```python
# 修改文件：app/services/chunker.py
from llama_index.core.node_parser import SentenceSplitter

class TextChunker:
    def __init__(self, chunk_size=400, chunk_overlap=50):
        self.splitter = SentenceSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap
        )
    
    def chunk_text(self, text):
        return self.splitter.split_text(text)
```

### 向量存储

迁移到LlamaIndex的FAISS集成：

- **新实现**：创建`LlamaVectorStore`包装LlamaIndex的`FaissVectorStore`
- **索引兼容**：保持现有FAISS索引文件格式兼容
- **API适配**：提供与现有`VectorStore`类似的API

```python
# 新增文件：app/services/llama_vector_store.py
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core import VectorStoreIndex, StorageContext

class LlamaVectorStore:
    def __init__(self, index_path, embedding_dim=384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.vector_store = FaissVectorStore.from_persist_dir(index_path)
        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )
        self.index = VectorStoreIndex.from_vector_store(
            self.vector_store,
            storage_context=self.storage_context
        )
```

### RAG管道

迁移到LlamaIndex的查询引擎：

- **新实现**：创建`LlamaRAGPipeline`使用LlamaIndex的查询引擎
- **简化API**：使用`index.as_query_engine()`简化查询流程
- **LLM集成**：使用LlamaIndex的LLM抽象，支持多个提供商

```python
# 新增文件：app/services/llama_rag_pipeline.py
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.llms.openrouter import OpenRouter
from llama_index.llms.openai_like import OpenAILike

class LlamaRAGPipeline:
    def __init__(self, index, provider="gemini", **kwargs):
        self.index = index
        self._configure_llm(provider, **kwargs)
        self.query_engine = index.as_query_engine()
    
    def _configure_llm(self, provider, **kwargs):
        if provider == "gemini":
            Settings.llm = Gemini(**kwargs)
        elif provider == "openrouter":
            Settings.llm = OpenRouter(**kwargs)
        elif provider == "local":
            # llama.cpp服务器提供OpenAI兼容API
            Settings.llm = OpenAILike(**kwargs)
    
    def query(self, question, top_k=3):
        response = self.query_engine.query(question)
        return {
            "answer": response.response,
            "sources": self._extract_sources(response)
        }
```

### LLM集成

使用LlamaIndex的LLM抽象：

- **统一接口**：通过LlamaIndex的`Settings.llm`统一配置LLM
- **多提供商支持**：支持Gemini、OpenRouter和本地llama.cpp
- **配置管理**：保留现有的配置管理，但适配到LlamaIndex

```python
# 修改文件：app/services/llama_llm_config.py
from llama_index.core import Settings
from llama_index.llms.gemini import Gemini
from llama_index.llms.openrouter import OpenRouter
from llama_index.llms.openai_like import OpenAILike

def configure_llm(provider, model=None, api_key=None, base_url=None):
    """配置LlamaIndex LLM设置"""
    if provider == "gemini":
        Settings.llm = Gemini(
            model=model or "gemini-2.0-flash",
            api_key=api_key
        )
    elif provider == "openrouter":
        Settings.llm = OpenRouter(
            model=model or "anthropic/claude-3-haiku",
            api_key=api_key
        )
    elif provider == "local":
        # llama.cpp服务器提供OpenAI兼容API
        Settings.llm = OpenAILike(
            model=model or "qwen2.5:3b",
            api_base=base_url or "http://localhost:8080/v1",
            api_key="not-needed"  # llama.cpp不需要API密钥
        )
```

## 整体集成

将LlamaIndex组件集成到现有Django应用：

1. **依赖更新**：在`requirements.txt`中添加LlamaIndex依赖
2. **配置管理**：保留现有的配置管理，但适配到LlamaIndex
3. **API兼容**：保持现有的API端点不变，只改变内部实现
4. **渐进式迁移**：可以逐步替换组件，保持向后兼容

```txt
# requirements.txt 新增依赖
llama-index-core>=0.10.0
llama-index-llms-gemini>=0.1.0
llama-index-llms-openrouter>=0.1.0
llama-index-vector-stores-faiss>=0.1.0
llama-index-embeddings-huggingface>=0.1.0
```

## 测试和验证

### 单元测试

为新的LlamaIndex组件添加单元测试：

```python
# 新增测试文件：tests/test_llama_components.py
def test_llama_document_adapter():
    """测试文档适配器"""
    pass

def test_llama_text_chunker():
    """测试文本分割器"""
    pass

def test_llama_vector_store():
    """测试向量存储"""
    pass

def test_llama_rag_pipeline():
    """测试RAG管道"""
    pass
```

### 性能基准测试

比较迁移前后的性能差异：

```python
# 性能基准测试：tests/benchmark_performance.py
def benchmark_retrieval_speed():
    """比较检索速度"""
    pass

def benchmark_indexing_speed():
    """比较索引速度"""
    pass
```

## 实施计划

1. **阶段1**：添加LlamaIndex依赖，创建文档适配器
2. **阶段2**：替换文本分割器
3. **阶段3**：替换向量存储
4. **阶段4**：替换RAG管道和LLM集成
5. **阶段5**：添加测试和性能基准测试

## 风险和缓解措施

1. **兼容性风险**：现有FAISS索引可能不兼容
   - 缓解：创建索引迁移工具或重建索引
2. **性能风险**：LlamaIndex可能引入额外开销
   - 缓解：性能基准测试，优化关键路径
3. **功能风险**：某些现有功能可能在LlamaIndex中不可用
   - 缓解：详细功能对比，保留必要的自定义实现

## 结论

本设计采用混合迁移策略，将关键组件迁移到LlamaIndex，同时保留现有实现的稳定性。通过渐进式迁移和充分的测试，可以确保系统平滑过渡到LlamaIndex，获得更简单的API和更好的可维护性。