import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

AVAILABLE_MODELS = {
    "sentence-transformers/all-MiniLM-L6-v2": {
        "name": "MiniLM (L6-v2)",
        "dimension": 384,
        "speed": "Very Fast",
        "memory": "~80 MB",
        "description": "Lightweight, fast model for general-purpose embeddings",
        "recommended": True,
    },
    "BAAI/bge-small-en-v1.5": {
        "name": "BGE-small",
        "dimension": 384,
        "speed": "Fast",
        "memory": "~120 MB",
        "description": "Small model with good retrieval performance",
        "recommended": False,
    },
    "BAAI/bge-large-en-v1.5": {
        "name": "BGE-large",
        "dimension": 1024,
        "speed": "Medium",
        "memory": "~1.2 GB",
        "description": "Large model with excellent retrieval accuracy",
        "recommended": False,
    },
    "intfloat/e5-large-v2": {
        "name": "E5-large",
        "dimension": 1024,
        "speed": "Medium",
        "memory": "~1.3 GB",
        "description": "Microsoft E5 model for text embeddings",
        "recommended": False,
    },
    "Qwen/Qwen3-Embedding-0.6B": {
        "name": "Qwen3-0.6B",
        "dimension": 1024,
        "speed": "Slow",
        "memory": "~2.5 GB",
        "description": "Qwen3 large embedding model",
        "recommended": False,
    },
    "sentence-transformers/all-mpnet-base-v2": {
        "name": "MPNet-base",
        "dimension": 768,
        "speed": "Medium",
        "memory": "~420 MB",
        "description": "Strong all-around performance model",
        "recommended": False,
    },
}


class EmbeddingError(Exception):
    pass


class _ModelCache:
    def __init__(self, max_size: int = 3) -> None:
        self.max_size = max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()
        self.stats: Dict[str, int] = {"hits": 0, "misses": 0, "loads": 0, "evictions": 0}

    def get(self, model_id: str) -> Optional[Any]:
        with self._lock:
            if model_id in self._cache:
                self._cache.move_to_end(model_id)
                self.stats["hits"] += 1
                return self._cache[model_id]
            self.stats["misses"] += 1
            return None

    def put(self, model_id: str, model: Any) -> None:
        with self._lock:
            if model_id in self._cache:
                self._cache.move_to_end(model_id)
                self._cache[model_id] = model
            else:
                if len(self._cache) >= self.max_size:
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    self.stats["evictions"] += 1
                self._cache[model_id] = model
                self.stats["loads"] += 1

    def remove(self, model_id: str) -> bool:
        with self._lock:
            if model_id in self._cache:
                del self._cache[model_id]
                return True
            return False

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def contains(self, model_id: str) -> bool:
        with self._lock:
            return model_id in self._cache


_model_cache = _ModelCache(max_size=3)
_cache_lock = threading.Lock()


class EmbeddingService:
    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or "sentence-transformers/all-MiniLM-L6-v2"
        self._model: Optional[SentenceTransformer] = None
        self._model_lock = threading.Lock()

    def _get_model(self) -> SentenceTransformer:
        cached = _model_cache.get(self.model_name)
        if cached is not None:
            return cached

        with self._model_lock:
            cached = _model_cache.get(self.model_name)
            if cached is not None:
                return cached

            try:
                start = time.time()
                model = SentenceTransformer(self.model_name)
                load_ms = (time.time() - start) * 1000
                logger.info("Loaded embedding model '%s' in %.0fms", self.model_name, load_ms)
                _model_cache.put(self.model_name, model)
                self._model = model
                return model
            except Exception as e:
                raise EmbeddingError(f"Failed to load embedding model '{self.model_name}': {e}") from e

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.array([])
        try:
            model = self._get_model()
            return model.encode(texts, show_progress_bar=False)
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"Failed to create embeddings: {e}") from e

    def embed_query(self, query: str) -> np.ndarray:
        if not query or not query.strip():
            raise EmbeddingError("Query cannot be empty")
        try:
            model = self._get_model()
            return model.encode([query], show_progress_bar=False)[0]
        except EmbeddingError:
            raise
        except Exception as e:
            raise EmbeddingError(f"Failed to embed query: {e}") from e

    def get_embedding_dimension(self) -> int:
        model = self._get_model()
        dim = model.get_sentence_embedding_dimension()
        if dim is None:
            raise EmbeddingError("Could not determine embedding dimension")
        return dim


def get_available_models() -> List[Dict[str, Any]]:
    return [{"id": mid, **meta} for mid, meta in AVAILABLE_MODELS.items()]


def get_current_model_id() -> str:
    return _current_model_id


_current_model_id: str = "sentence-transformers/all-MiniLM-L6-v2"
_current_model_lock = threading.Lock()
_performance_metrics: List[Dict[str, Any]] = []
_metrics_lock = threading.Lock()


def set_current_model(model_id: str) -> Dict[str, Any]:
    global _current_model_id
    if model_id not in AVAILABLE_MODELS:
        raise EmbeddingError(f"Unknown model: {model_id}")

    start = time.time()
    svc = EmbeddingService(model_name=model_id)
    test_emb = svc.embed_query("test")
    dimension = len(test_emb)
    load_ms = (time.time() - start) * 1000

    with _current_model_lock:
        old = _current_model_id
        _current_model_id = model_id

    _record_metric("switch", model_id, load_ms)

    return {
        "model_id": model_id,
        "model_name": AVAILABLE_MODELS[model_id]["name"],
        "dimension": dimension,
        "load_time_ms": round(load_ms, 2),
        "was_cached": _model_cache.contains(model_id),
        "previous_model": old,
    }


def test_model(model_id: str, query: str, top_k: int = 3) -> Dict[str, Any]:
    from app.config import settings
    from app.services.vector_store import VectorStore

    start = time.time()
    svc = EmbeddingService(model_name=model_id)
    query_embedding = svc.embed_query(query)
    embed_ms = (time.time() - start) * 1000

    dim = AVAILABLE_MODELS.get(model_id, {}).get("dimension", 384)
    vector_store = VectorStore(index_path=settings.FAISS_INDEX_PATH, embedding_dim=dim)

    search_start = time.time()
    results = vector_store.search_with_metadata(query_embedding, top_k=top_k)
    search_ms = (time.time() - search_start) * 1000
    total_ms = (time.time() - start) * 1000

    formatted = []
    for i, r in enumerate(results):
        formatted.append({
            "rank": i + 1,
            "text": r.get("text", "N/A"),
            "distance": round(r.get("distance", 0), 4),
            "score": round(1.0 - r.get("distance", 0), 4),
        })

    _record_metric("test", model_id, total_ms)

    return {
        "model_id": model_id,
        "query": query,
        "results": formatted,
        "total_results": len(formatted),
        "retrieval_time_ms": round(total_ms, 2),
        "embed_time_ms": round(embed_ms, 2),
        "search_time_ms": round(search_ms, 2),
    }


def get_performance_metrics(model_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
    with _metrics_lock:
        metrics = list(_performance_metrics[-limit:])
    if model_id:
        metrics = [m for m in metrics if m["model_id"] == model_id]
    return metrics


def get_cache_stats() -> Dict[str, Any]:
    return {
        **_model_cache.stats,
        "cache_size": len(_model_cache._cache),
        "max_size": _model_cache.max_size,
        "cached_models": list(_model_cache._cache.keys()),
    }


def clear_cache() -> None:
    _model_cache.clear()


def _record_metric(action: str, model_id: str, time_ms: float) -> None:
    with _metrics_lock:
        _performance_metrics.append({
            "action": action,
            "model_id": model_id,
            "time_ms": round(time_ms, 2),
            "timestamp": time.time(),
        })
        if len(_performance_metrics) > 100:
            _performance_metrics[:] = _performance_metrics[-100:]
