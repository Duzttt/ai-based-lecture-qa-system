import os
from typing import Any, Dict, List, Optional

import faiss
import numpy as np
from llama_index.core import StorageContext, VectorStoreIndex
from llama_index.core.embeddings import BaseEmbedding
from llama_index.core.schema import TextNode
from llama_index.core.vector_stores.types import (
    VectorStoreQuery,
    VectorStoreQueryResult,
)
from llama_index.vector_stores.faiss import FaissVectorStore
from pydantic import PrivateAttr


class _NoOpEmbedding(BaseEmbedding):
    """Embedding stub — embeddings are supplied externally, not computed by LlamaIndex."""

    _dim: int = PrivateAttr(default=384)

    def __init__(self, dim: int = 384, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._dim = dim

    def _get_query_embedding(self, query: str) -> List[float]:
        return [0.0] * self._dim

    def _get_text_embedding(self, text: str) -> List[float]:
        return [0.0] * self._dim

    async def _aget_query_embedding(self, query: str) -> List[float]:
        return [0.0] * self._dim


class LlamaVectorStoreError(Exception):
    pass


class LlamaVectorStore:
    """LlamaIndex FAISS向量存储包装器

    Wraps LlamaIndex's ``FaissVectorStore``, ``StorageContext``, and
    ``VectorStoreIndex`` while maintaining compatibility with the existing
    ``index.faiss`` / ``chunks.npy`` persistence format and the original
    ``VectorStore`` public API.

    Embeddings are supplied externally (via ``add_embeddings``) and stored
    directly in the underlying FAISS index through ``FaissVectorStore.add()``.
    """

    def __init__(self, index_path: str, embedding_dim: int = 384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.faiss_index: Optional[faiss.Index] = None
        self.chunks: List[Dict[str, Any]] = []
        self.vector_store: Optional[FaissVectorStore] = None
        self.storage_context: Optional[StorageContext] = None
        self.index: Optional[VectorStoreIndex] = None
        self._load_or_create_index()
        self._init_llama_objects()

    def _init_llama_objects(self) -> None:
        """Initialize LlamaIndex FaissVectorStore, StorageContext and VectorStoreIndex."""
        self.vector_store = FaissVectorStore(faiss_index=self.faiss_index)
        self.storage_context = StorageContext.from_defaults(
            vector_store=self.vector_store
        )
        self.index = VectorStoreIndex(
            nodes=[],
            storage_context=self.storage_context,
            embed_model=_NoOpEmbedding(dim=self.embedding_dim),
        )

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
                self.faiss_index = faiss.read_index(index_file)
                loaded_chunks = np.load(chunks_file, allow_pickle=True).tolist()
                if not isinstance(loaded_chunks, list):
                    loaded_chunks = [loaded_chunks]
                self.chunks = [self._normalize_chunk(chunk) for chunk in loaded_chunks]
            except Exception as e:
                raise LlamaVectorStoreError(f"Failed to load index: {str(e)}")
        else:
            self.faiss_index = faiss.IndexFlatL2(self.embedding_dim)

    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Any]) -> None:
        """添加嵌入和对应的块

        Converts raw embeddings and chunks into LlamaIndex ``TextNode`` objects
        and adds them through the ``FaissVectorStore``.
        """
        if len(embeddings) == 0:
            return

        if len(embeddings) != len(chunks):
            raise LlamaVectorStoreError(
                "Number of embeddings must match number of chunks"
            )

        normalized = [self._normalize_chunk(chunk) for chunk in chunks]
        nodes: List[TextNode] = []
        for emb, chunk in zip(embeddings, normalized):
            node = TextNode(
                text=chunk["text"],
                embedding=emb.tolist(),
                metadata={"source": chunk["source"], "page": chunk["page"]},
            )
            nodes.append(node)

        self.vector_store.add(nodes)
        self.chunks.extend(normalized)

    def search_with_metadata(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        """搜索并返回带元数据的结果

        Uses LlamaIndex's ``VectorStoreQuery`` to search the
        ``FaissVectorStore`` and returns results with chunk metadata.
        """
        if self.faiss_index is None or self.faiss_index.ntotal == 0:
            return []

        actual_k = min(top_k, self.faiss_index.ntotal)
        query = VectorStoreQuery(
            query_embedding=query_embedding.tolist(),
            similarity_top_k=actual_k,
        )
        result: VectorStoreQueryResult = self.vector_store.query(query)

        results: List[Dict[str, Any]] = []
        for rank, (node_id, similarity) in enumerate(
            zip(result.ids or [], result.similarities or []), start=1
        ):
            idx = int(node_id)
            if idx < 0 or idx >= len(self.chunks):
                continue

            chunk = self.chunks[idx]
            results.append(
                {
                    "index": idx,
                    "rank": rank,
                    "text": chunk["text"],
                    "source": chunk["source"],
                    "page": chunk["page"],
                    "distance": float(similarity),
                }
            )

        return results

    def save(self) -> None:
        """保存索引到磁盘"""
        if self.faiss_index is None:
            return

        os.makedirs(self.index_path, exist_ok=True)
        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")

        faiss.write_index(self.faiss_index, index_file)
        np.save(chunks_file, np.array(self.chunks, dtype=object))

    def clear(self) -> None:
        """清空索引"""
        if self.faiss_index is not None:
            if self.faiss_index.d != self.embedding_dim:
                self.faiss_index = faiss.IndexFlatL2(self.embedding_dim)
            else:
                self.faiss_index.reset()
        self.chunks = []
        self._init_llama_objects()

    def get_total_chunks(self) -> int:
        """获取总块数"""
        return len(self.chunks)
