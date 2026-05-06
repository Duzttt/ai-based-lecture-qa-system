import tempfile
import numpy as np
from app.services.llama_vector_store import LlamaVectorStore


def test_llama_vector_store_creation():
    """测试LlamaVectorStore创建"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)
        assert store is not None


def test_llama_vector_store_add_and_search():
    """测试添加和搜索功能"""
    with tempfile.TemporaryDirectory() as temp_dir:
        store = LlamaVectorStore(temp_dir, embedding_dim=384)

        # 添加测试数据
        embeddings = np.random.rand(3, 384).astype(np.float32)
        chunks = [
            {"text": "测试文本1", "source": "test.pdf", "page": 1},
            {"text": "测试文本2", "source": "test.pdf", "page": 2},
            {"text": "测试文本3", "source": "test.pdf", "page": 3}
        ]

        store.add_embeddings(embeddings, chunks)

        # 搜索测试
        query_embedding = np.random.rand(384).astype(np.float32)
        results = store.search_with_metadata(query_embedding, top_k=2)

        assert len(results) == 2
        assert "text" in results[0]
        assert "source" in results[0]
