import os
from typing import Any, Dict, List, Optional

import faiss
import numpy as np


class LlamaVectorStoreError(Exception):
    pass


class LlamaVectorStore:
    """LlamaIndex-compatible FAISS向量存储包装器

    Maintains compatibility with existing index.faiss and chunks.npy format
    while providing an interface compatible with LlamaIndex patterns.
    """

    def __init__(self, index_path: str, embedding_dim: int = 384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.index: Optional[faiss.Index] = None
        self.chunks: List[Dict[str, Any]] = []
        self._load_or_create_index()

    @staticmethod
    def _normalize_chunk(item: Any) -> Dict[str, Any]:
        if isinstance(item, dict):
            text = str(item.get("text", ""))
            source = str(item.get("source", "unknown")).strip() or "unknown"
            page_raw = item.get("page")
            if isinstance(page_raw, (int, np.integer)):
                page = int(page_raw)
            elif isinstance(page_raw, str) and page_raw.strip().isdigit():
                page = int(page_raw.strip())
            else:
                page = None
            return {"text": text, "source": source, "page": page}

        if isinstance(item, str):
            return {"text": item, "source": "unknown", "page": None}

        if item is None:
            return {"text": "", "source": "unknown", "page": None}

        return {"text": str(item), "source": "unknown", "page": None}

    def _load_or_create_index(self):
        """加载或创建FAISS索引"""
        os.makedirs(self.index_path, exist_ok=True)

        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")

        if os.path.exists(index_file) and os.path.exists(chunks_file):
            try:
                self.index = faiss.read_index(index_file)
                loaded_chunks = np.load(chunks_file, allow_pickle=True).tolist()
                if not isinstance(loaded_chunks, list):
                    loaded_chunks = [loaded_chunks]
                self.chunks = [self._normalize_chunk(chunk) for chunk in loaded_chunks]
            except Exception as e:
                raise LlamaVectorStoreError(f"Failed to load index: {str(e)}")
        else:
            self.index = faiss.IndexFlatL2(self.embedding_dim)

    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Any]) -> None:
        """添加嵌入和对应的块"""
        if len(embeddings) == 0:
            return

        if len(embeddings) != len(chunks):
            raise LlamaVectorStoreError(
                "Number of embeddings must match number of chunks"
            )

        embeddings_array = np.array(embeddings).astype("float32")
        self.index.add(embeddings_array)
        self.chunks.extend([self._normalize_chunk(chunk) for chunk in chunks])

    def search_with_metadata(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """搜索并返回带元数据的结果"""
        if self.index is None or self.index.ntotal == 0:
            return []

        query_vector = np.array([query_embedding]).astype("float32")
        distances, indices = self.index.search(
            query_vector, min(top_k, self.index.ntotal)
        )

        results: List[Dict[str, Any]] = []
        for rank, idx in enumerate(indices[0], start=1):
            if idx < 0:
                continue
            if idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]
            results.append(
                {
                    "index": int(idx),
                    "rank": rank,
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "page": chunk["page"],
                    "distance": float(distances[0][rank - 1]),
                }
            )

        return results

    def save(self) -> None:
        """保存索引到磁盘"""
        if self.index is None:
            return

        os.makedirs(self.index_path, exist_ok=True)
        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")

        faiss.write_index(self.index, index_file)
        np.save(chunks_file, np.array(self.chunks, dtype=object))

    def clear(self) -> None:
        """清空索引"""
        if self.index is not None:
            if self.index.d != self.embedding_dim:
                self.index = faiss.IndexFlatL2(self.embedding_dim)
            else:
                self.index.reset()
        self.chunks = []

    def get_total_chunks(self) -> int:
        """获取总块数"""
        return len(self.chunks)
