import os
import threading
from typing import Any, Dict, List, Optional, Tuple

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

_GLOBAL_LLAMA_CACHE: Dict[Tuple[str, int], "LlamaVectorStore"] = {}
_GLOBAL_LLAMA_CACHE_LOCK = threading.Lock()


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
        self._node_id_to_chunk_index: Dict[str, int] = {}
        self._load_or_create_index()
        self._init_llama_objects()

    @classmethod
    def get_cached(
        cls,
        index_path: str,
        embedding_dim: int = 384,
    ) -> "LlamaVectorStore":
        """Return a cached instance, creating one on first use (thread-safe)."""
        key = (index_path, embedding_dim)
        cached = _GLOBAL_LLAMA_CACHE.get(key)
        if cached is not None:
            return cached

        with _GLOBAL_LLAMA_CACHE_LOCK:
            cached = _GLOBAL_LLAMA_CACHE.get(key)
            if cached is not None:
                return cached
            store = cls(index_path=index_path, embedding_dim=embedding_dim)
            _GLOBAL_LLAMA_CACHE[key] = store
            return store

    @classmethod
    def set_cached(cls, store: "LlamaVectorStore") -> None:
        """Update the cache with the provided store instance."""
        _GLOBAL_LLAMA_CACHE[(store.index_path, store.embedding_dim)] = store

    @classmethod
    def invalidate_cached(
        cls,
        index_path: Optional[str] = None,
        embedding_dim: Optional[int] = None,
    ) -> None:
        """Invalidate cached stores matching the provided scope."""
        keys_to_delete: List[Tuple[str, int]] = []
        for key in _GLOBAL_LLAMA_CACHE:
            key_index_path, key_embedding_dim = key
            if index_path is not None and key_index_path != index_path:
                continue
            if embedding_dim is not None and key_embedding_dim != embedding_dim:
                continue
            keys_to_delete.append(key)
        for key in keys_to_delete:
            _GLOBAL_LLAMA_CACHE.pop(key, None)

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

    @staticmethod
    def _normalize(vectors: np.ndarray) -> np.ndarray:
        """L2-normalize vectors so that inner product equals cosine similarity."""
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1, norms)
        return vectors / norms

    def _load_or_create_index(self):
        """加载或创建FAISS索引"""
        os.makedirs(self.index_path, exist_ok=True)

        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")
        mapping_file = os.path.join(self.index_path, "node_mapping.npy")

        if os.path.exists(index_file) and os.path.exists(chunks_file):
            try:
                self.faiss_index = faiss.read_index(index_file)
                loaded_chunks = np.load(chunks_file, allow_pickle=True).tolist()
                if not isinstance(loaded_chunks, list):
                    loaded_chunks = [loaded_chunks]
                self.chunks = [self._normalize_chunk(chunk) for chunk in loaded_chunks]
                if os.path.exists(mapping_file):
                    items = np.load(mapping_file, allow_pickle=True).tolist()
                    self._node_id_to_chunk_index = {
                        str(k): int(v) for k, v in items
                    }
            except Exception as e:
                raise LlamaVectorStoreError(f"Failed to load index: {str(e)}")
        else:
            self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)

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
        base_index = len(self.chunks)
        emb_array = self._normalize(np.array(embeddings, dtype="float32"))
        nodes: List[TextNode] = []
        for i, (emb, chunk) in enumerate(zip(emb_array, normalized)):
            node = TextNode(
                text=chunk["text"],
                embedding=emb.tolist(),
                metadata={"source": chunk["source"], "page": chunk["page"]},
            )
            nodes.append(node)

        self.vector_store.add(nodes)
        for i, node in enumerate(nodes):
            self._node_id_to_chunk_index[node.node_id] = base_index + i
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
        norm_query = self._normalize(
            np.array([query_embedding], dtype="float32")
        )[0]
        query = VectorStoreQuery(
            query_embedding=norm_query.tolist(),
            similarity_top_k=actual_k,
        )
        result: VectorStoreQueryResult = self.vector_store.query(query)

        results: List[Dict[str, Any]] = []
        for rank, (node_id, similarity) in enumerate(
            zip(result.ids or [], result.similarities or []), start=1
        ):
            idx = self._node_id_to_chunk_index.get(str(node_id))
            if idx is None:
                try:
                    idx = int(node_id)
                except (ValueError, TypeError):
                    continue
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
        mapping_file = os.path.join(self.index_path, "node_mapping.npy")

        faiss.write_index(self.faiss_index, index_file)
        np.save(chunks_file, np.array(self.chunks, dtype=object))
        np.save(
            mapping_file,
            np.array(list(self._node_id_to_chunk_index.items()), dtype=object),
        )

    def clear(self) -> None:
        """清空索引"""
        if self.faiss_index is not None:
            if self.faiss_index.d != self.embedding_dim:
                self.faiss_index = faiss.IndexFlatIP(self.embedding_dim)
            else:
                self.faiss_index.reset()
        self.chunks = []
        self._node_id_to_chunk_index = {}
        self._init_llama_objects()

    def get_total_chunks(self) -> int:
        """获取总块数"""
        return len(self.chunks)
