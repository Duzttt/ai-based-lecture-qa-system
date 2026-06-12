import os
import threading
from typing import Any, Dict, List, Optional, Tuple

import faiss
import numpy as np


class VectorStoreError(Exception):
    pass


_GLOBAL_INDEX_CACHE: Dict[Tuple[str, int], "VectorStore"] = {}
_GLOBAL_INDEX_CACHE_LOCK = threading.Lock()


class VectorStore:
    def __init__(self, index_path: str, embedding_dim: int = 384):
        self.index_path = index_path
        self.embedding_dim = embedding_dim
        self.index: Optional[faiss.Index] = None
        self.chunks: List[Dict[str, Any]] = []
        self._load_or_create_index()

    @classmethod
    def get_cached(
        cls,
        index_path: str,
        embedding_dim: int = 384,
    ) -> "VectorStore":
        """
        Return a cached VectorStore instance for the given index path and
        embedding dimension, creating and caching it on first use.
        """
        key = (index_path, embedding_dim)
        with _GLOBAL_INDEX_CACHE_LOCK:
            cached = _GLOBAL_INDEX_CACHE.get(key)
            if cached is not None:
                return cached
            store = cls(index_path=index_path, embedding_dim=embedding_dim)
            _GLOBAL_INDEX_CACHE[key] = store
            return store

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
                raise VectorStoreError(f"Failed to load index: {str(e)}")
        else:
            self.index = faiss.IndexFlatL2(self.embedding_dim)

    def add_embeddings(self, embeddings: np.ndarray, chunks: List[Any]) -> None:
        if len(embeddings) == 0:
            return

        if len(embeddings) != len(chunks):
            raise VectorStoreError("Number of embeddings must match number of chunks")

        embeddings_array = np.array(embeddings).astype("float32")
        self.index.add(embeddings_array)
        self.chunks.extend([self._normalize_chunk(chunk) for chunk in chunks])

    def search_with_metadata(
        self,
        query_embedding: np.ndarray,
        top_k: int = 3,
    ) -> List[Dict[str, Any]]:
        if self.index.ntotal == 0:
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

    def search(
        self, query_embedding: np.ndarray, top_k: int = 3
    ) -> Tuple[List[str], List[float]]:
        grounded_results = self.search_with_metadata(
            query_embedding=query_embedding,
            top_k=top_k,
        )
        return (
            [result["text"] for result in grounded_results],
            [result["distance"] for result in grounded_results],
        )

    def save(self) -> None:
        if self.index is None:
            return

        os.makedirs(self.index_path, exist_ok=True)
        index_file = os.path.join(self.index_path, "index.faiss")
        chunks_file = os.path.join(self.index_path, "chunks.npy")

        faiss.write_index(self.index, index_file)
        np.save(chunks_file, np.array(self.chunks, dtype=object))

    def clear(self) -> None:
        if self.index is not None:
            if self.index.d != self.embedding_dim:
                self.index = faiss.IndexFlatL2(self.embedding_dim)
            else:
                self.index.reset()
        self.chunks = []

    def get_total_chunks(self) -> int:
        return len(self.chunks)
