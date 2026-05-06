import tempfile
import numpy as np
import pytest
from app.services.llama_vector_store import (
    LlamaVectorStore,
    LlamaVectorStoreError,
)


def test_llama_vector_store_creation():
    """测试LlamaVectorStore创建"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)
        assert store is not None
        assert store.get_total_chunks() == 0


def test_llama_vector_store_add_and_search():
    """测试添加和搜索功能"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)

        embeddings = np.random.rand(3, 384).astype(np.float32)
        chunks = [
            {"text": "测试文本1", "source": "test.pdf", "page": 1},
            {"text": "测试文本2", "source": "test.pdf", "page": 2},
            {"text": "测试文本3", "source": "test.pdf", "page": 3},
        ]

        store.add_embeddings(embeddings, chunks)

        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.search_with_metadata(query_embedding, top_k=2)

        assert len(results) == 2
        assert "text" in results[0]
        assert "source" in results[0]
        assert "page" in results[0]
        assert "rank" in results[0]
        assert "distance" in results[0]


def test_llama_vector_store_empty_index_search():
    """搜索空索引应返回空列表"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.search_with_metadata(query_embedding, top_k=3)
        assert results == []


def test_llama_vector_store_mismatched_embeddings_chunks():
    """嵌入和块数量不匹配应抛出错误"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)
        embeddings = np.random.rand(3, 384).astype(np.float32)
        chunks = [{"text": "only one"}]
        with pytest.raises(LlamaVectorStoreError, match="must match"):
            store.add_embeddings(embeddings, chunks)


def test_llama_vector_store_empty_embeddings():
    """空嵌入数组不应报错"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)
        embeddings = np.empty((0, 384), dtype=np.float32)
        store.add_embeddings(embeddings, [])
        assert store.get_total_chunks() == 0


def test_llama_vector_store_save_and_load():
    """保存后重新加载应保留数据"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=4)
        embeddings = np.random.rand(2, 4).astype(np.float32)
        chunks = [
            {"text": "保存测试1", "source": "doc.pdf", "page": 1},
            {"text": "保存测试2", "source": "doc.pdf", "page": 2},
        ]
        store.add_embeddings(embeddings, chunks)
        store.save()

        loaded = LlamaVectorStore(temp_dir, embedding_dim=4)
        assert loaded.get_total_chunks() == 2
        assert loaded.chunks[0]["text"] == "保存测试1"
        assert loaded.chunks[1]["text"] == "保存测试2"


def test_llama_vector_store_clear():
    """清空索引后数据应被重置"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=4)
        embeddings = np.random.rand(2, 4).astype(np.float32)
        chunks = [
            {"text": "清空测试1", "source": "a.pdf", "page": 1},
            {"text": "清空测试2", "source": "a.pdf", "page": 2},
        ]
        store.add_embeddings(embeddings, chunks)
        assert store.get_total_chunks() == 2

        store.clear()
        assert store.get_total_chunks() == 0
        query_embedding = np.random.rand(4).astype(np.float32)
        assert store.search_with_metadata(query_embedding) == []


def test_llama_vector_store_top_k_exceeds_total():
    """top_k超过总数时应返回所有可用结果"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=4)
        embeddings = np.random.rand(2, 4).astype(np.float32)
        chunks = [
            {"text": "a", "source": "x.pdf", "page": 1},
            {"text": "b", "source": "x.pdf", "page": 2},
        ]
        store.add_embeddings(embeddings, chunks)
        query_embedding = np.random.rand(4).astype(np.float32)
        results = store.search_with_metadata(query_embedding, top_k=10)
        assert len(results) == 2


def test_llama_vector_store_incremental_add():
    """多次添加嵌入后搜索应覆盖所有块"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=4)
        for i in range(3):
            emb = np.random.rand(1, 4).astype(np.float32)
            store.add_embeddings(emb, [{"text": f"chunk-{i}", "source": "s.pdf", "page": i}])
        assert store.get_total_chunks() == 3


def test_llama_vector_store_get_cached_returns_same_instance():
    """get_cached应返回同一实例"""
    with tempfile.TemporaryDirectory() as temp_dir:
        a = LlamaVectorStore.get_cached(temp_dir, embedding_dim=4)
        b = LlamaVectorStore.get_cached(temp_dir, embedding_dim=4)
        assert a is b
        LlamaVectorStore.invalidate_cached(temp_dir, 4)


def test_llama_vector_store_invalidate_cached():
    """invalidate_cached应清除缓存"""
    with tempfile.TemporaryDirectory() as temp_dir:
        a = LlamaVectorStore.get_cached(temp_dir, embedding_dim=4)
        LlamaVectorStore.invalidate_cached(temp_dir, 4)
        b = LlamaVectorStore.get_cached(temp_dir, embedding_dim=4)
        assert a is not b
        LlamaVectorStore.invalidate_cached(temp_dir, 4)


def test_llama_vector_store_string_chunks():
    """字符串块应被正常处理"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=4)
        embeddings = np.random.rand(2, 4).astype(np.float32)
        store.add_embeddings(embeddings, ["纯文本块1", "纯文本块2"])
        assert store.get_total_chunks() == 2
        assert store.chunks[0]["source"] == "unknown"
