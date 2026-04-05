"""
Embedding Model Manager with caching support.

This module provides a centralized manager for loading and caching
embedding models to avoid repeated loading overhead.
"""

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import settings


class EmbeddingModelCache:
    """LRU cache for embedding models with configurable max size."""

    def __init__(self, max_size: int = 3):
        self.max_size = max_size
        self._cache: OrderedDict[str, Any] = OrderedDict()
        self._lock = threading.RLock()
        self._stats: Dict[str, Any] = {
            "hits": 0,
            "misses": 0,
            "loads": 0,
            "evictions": 0,
        }

    def get(self, model_id: str) -> Optional[Any]:
        """Get model from cache, moving it to end (most recently used)."""
        with self._lock:
            if model_id in self._cache:
                # Move to end (most recently used)
                self._cache.move_to_end(model_id)
                self._stats["hits"] += 1
                return self._cache[model_id]
            self._stats["misses"] += 1
            return None

    def put(self, model_id: str, model: Any) -> None:
        """Add model to cache, evicting least recently used if necessary."""
        with self._lock:
            if model_id in self._cache:
                # Update existing and move to end
                self._cache.move_to_end(model_id)
                self._cache[model_id] = model
            else:
                # Add new entry
                if len(self._cache) >= self.max_size:
                    # Evict least recently used
                    oldest = next(iter(self._cache))
                    del self._cache[oldest]
                    self._stats["evictions"] += 1
                self._cache[model_id] = model
                self._stats["loads"] += 1

    def remove(self, model_id: str) -> bool:
        """Remove model from cache."""
        with self._lock:
            if model_id in self._cache:
                del self._cache[model_id]
                return True
            return False

    def clear(self) -> None:
        """Clear all cached models."""
        with self._lock:
            self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        with self._lock:
            return {
                **self._stats,
                "cached_models": list(self._cache.keys()),
                "cache_size": len(self._cache),
                "max_size": self.max_size,
            }


# Global model cache instance
_model_cache = EmbeddingModelCache(max_size=3)


class EmbeddingModelManager:
    """
    Manager for loading and using embedding models with caching.
    
    Supports multiple embedding models and caches recently used models
    to avoid repeated loading overhead.
    """

    # Registry of available models with metadata
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
        "sentence-transformers/all-MiniLM-L12-v2": {
            "name": "MiniLM (L12-v2)",
            "dimension": 384,
            "speed": "Very Fast",
            "memory": "~120 MB",
            "description": "12-layer MiniLM with better accuracy than L6 variant",
            "recommended": False,
        },
        "thenlper/gte-small": {
            "name": "GTE-small",
            "dimension": 384,
            "speed": "Very Fast",
            "memory": "~70 MB",
            "description": "Alibaba GTE small model, strong MTEB score for its size",
            "recommended": False,
        },
        "intfloat/e5-small-v2": {
            "name": "E5-small",
            "dimension": 384,
            "speed": "Very Fast",
            "memory": "~130 MB",
            "description": "Microsoft E5 small model for efficient text retrieval",
            "recommended": False,
        },
        "Snowflake/snowflake-arctic-embed-s": {
            "name": "Arctic-embed-s",
            "dimension": 384,
            "speed": "Very Fast",
            "memory": "~130 MB",
            "description": "Snowflake retrieval-optimized small model, SOTA for its size",
            "recommended": False,
        },
        "nomic-ai/nomic-embed-text-v1.5": {
            "name": "Nomic-embed-v1.5",
            "dimension": 768,
            "speed": "Fast",
            "memory": "~550 MB",
            "description": "8K context model with Matryoshka flexible dimensions",
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
        "BAAI/bge-m3": {
            "name": "BGE-M3",
            "dimension": 1024,
            "speed": "Medium",
            "memory": "~2.3 GB",
            "description": "Multilingual model with dense, sparse, and ColBERT retrieval",
            "recommended": False,
        },
        "nvidia/NV-Embed-v2": {
            "name": "NV-Embed-v2",
            "dimension": 4096,
            "speed": "Very Slow",
            "memory": "~15 GB",
            "description": "NVIDIA top-ranked MTEB model based on Mistral-7B",
            "recommended": False,
        },
        "Qwen/Qwen3-Embedding-8B": {
            "name": "Qwen3-8B",
            "dimension": 4096,
            "speed": "Very Slow",
            "memory": "~16 GB",
            "description": "Qwen3 8B embedding model with 32K context and MRL support",
            "recommended": False,
        },
        "BAAI/bge-en-icl": {
            "name": "BGE-en-ICL",
            "dimension": 4096,
            "speed": "Very Slow",
            "memory": "~14 GB",
            "description": "In-context learning retrieval model based on Mistral-7B",
            "recommended": False,
        },
        "Alibaba-NLP/gte-Qwen2-7B-instruct": {
            "name": "GTE-Qwen2-7B",
            "dimension": 3584,
            "speed": "Very Slow",
            "memory": "~26 GB",
            "description": "Alibaba GTE 7B instruct model for multilingual embeddings",
            "recommended": False,
        },
    }

    def __init__(self, default_model: str = None):
        self.default_model = default_model or settings.EMBEDDING_MODEL
        self._current_model_id: Optional[str] = None
        self._lock = threading.RLock()
        self._performance_metrics: List[Dict[str, Any]] = []

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Get list of all available models with metadata."""
        return [
            {"id": model_id, **metadata}
            for model_id, metadata in self.AVAILABLE_MODELS.items()
        ]

    def get_current_model_id(self) -> str:
        """Get the currently active model ID."""
        return self._current_model_id or self.default_model

    def _load_model(self, model_id: str) -> Any:
        """Load an embedding model using SentenceTransformers."""
        try:
            from sentence_transformers import SentenceTransformer
            return SentenceTransformer(model_id)
        except Exception as e:
            raise EmbeddingModelError(f"Failed to load model '{model_id}': {str(e)}")

    def get_model(self, model_id: str = None) -> Any:
        """
        Get an embedding model, loading from cache if available.
        
        Args:
            model_id: Model ID to load. If None, uses current model.
            
        Returns:
            Loaded SentenceTransformer model.
        """
        target_id = model_id or self.get_current_model_id()
        
        # Try cache first
        model = _model_cache.get(target_id)
        if model is not None:
            return model
        
        # Load model
        start_time = time.time()
        model = self._load_model(target_id)
        load_time = (time.time() - start_time) * 1000  # ms
        
        # Cache the model
        _model_cache.put(target_id, model)
        
        # Record metric
        self._record_metric("load", target_id, load_time)
        
        return model

    def set_current_model(self, model_id: str) -> Dict[str, Any]:
        """
        Set the current active model.
        
        Args:
            model_id: Model ID to switch to.
            
        Returns:
            Dict with model info and load time.
        """
        if model_id not in self.AVAILABLE_MODELS:
            raise EmbeddingModelError(f"Unknown model: {model_id}")
        
        start_time = time.time()
        
        with self._lock:
            # Load model (will use cache if available)
            model = self.get_model(model_id)
            
            # Verify model works
            try:
                test_embedding = model.encode(["test"], show_progress_bar=False)
                dimension = len(test_embedding[0])
            except Exception as e:
                raise EmbeddingModelError(f"Model validation failed: {str(e)}")
            
            old_model_id = self._current_model_id
            self._current_model_id = model_id
        
        load_time = (time.time() - start_time) * 1000  # ms
        
        # Record metric
        self._record_metric("switch", model_id, load_time)
        
        return {
            "model_id": model_id,
            "model_name": self.AVAILABLE_MODELS[model_id]["name"],
            "dimension": dimension,
            "load_time_ms": round(load_time, 2),
            "was_cached": model_id in _model_cache._cache,
            "previous_model": old_model_id,
        }

    def embed_texts(self, texts: List[str], model_id: str = None) -> np.ndarray:
        """Embed multiple texts using the specified or current model."""
        model = self.get_model(model_id)
        if not texts:
            return np.array([])
        
        start_time = time.time()
        embeddings = model.encode(texts, show_progress_bar=False)
        embed_time = (time.time() - start_time) * 1000
        
        self._record_metric("embed", model_id or self.get_current_model_id(), embed_time)
        
        return embeddings

    def embed_query(self, query: str, model_id: str = None) -> np.ndarray:
        """Embed a single query using the specified or current model."""
        if not query or not query.strip():
            raise EmbeddingModelError("Query cannot be empty")
        
        model = self.get_model(model_id)
        
        start_time = time.time()
        embedding = model.encode([query], show_progress_bar=False)[0]
        embed_time = (time.time() - start_time) * 1000
        
        self._record_metric("embed_query", model_id or self.get_current_model_id(), embed_time)
        
        return embedding

    def test_model(self, model_id: str, query: str, top_k: int = 3) -> Dict[str, Any]:
        """
        Test a model by embedding a query and retrieving results.
        
        Args:
            model_id: Model to test.
            query: Test query.
            top_k: Number of results to retrieve.
            
        Returns:
            Test results with retrieval time and chunks.
        """
        from app.services.vector_store import VectorStore
        
        start_time = time.time()
        
        # Embed query
        query_embedding = self.embed_query(query, model_id)
        embed_time = (time.time() - start_time) * 1000
        
        # Search in vector store
        vector_store = VectorStore(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=self.AVAILABLE_MODELS.get(model_id, {}).get("dimension", 384),
        )
        
        search_start = time.time()
        results = vector_store.search(query_embedding, top_k=top_k)
        search_time = (time.time() - search_start) * 1000
        
        total_time = (time.time() - start_time) * 1000
        
        # Format results
        formatted_results = []
        for i, (distance, idx) in enumerate(zip(results["distances"], results["indices"])):
            similarity = 1.0 - distance  # Simple similarity conversion
            formatted_results.append({
                "rank": i + 1,
                "text": vector_store.chunks[idx] if hasattr(vector_store, 'chunks') and idx < len(vector_store.chunks) else "N/A",
                "distance": round(float(distance), 4),
                "score": round(float(similarity), 4),
            })
        
        self._record_metric("test", model_id, total_time)
        
        return {
            "model_id": model_id,
            "query": query,
            "results": formatted_results,
            "total_results": len(formatted_results),
            "retrieval_time_ms": round(total_time, 2),
            "embed_time_ms": round(embed_time, 2),
            "search_time_ms": round(search_time, 2),
        }

    def _record_metric(self, action: str, model_id: str, time_ms: float) -> None:
        """Record a performance metric."""
        self._performance_metrics.append({
            "action": action,
            "model_id": model_id,
            "time_ms": round(time_ms, 2),
            "timestamp": time.time(),
        })
        
        # Keep only last 100 metrics
        if len(self._performance_metrics) > 100:
            self._performance_metrics = self._performance_metrics[-100:]

    def get_performance_metrics(self, model_id: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent performance metrics."""
        metrics = self._performance_metrics[-limit:]
        if model_id:
            metrics = [m for m in metrics if m["model_id"] == model_id]
        return metrics

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get model cache statistics."""
        return _model_cache.get_stats()

    def clear_cache(self) -> None:
        """Clear the model cache."""
        _model_cache.clear()


class EmbeddingModelError(Exception):
    """Exception raised for embedding model errors."""
    pass


# Global manager instance
_embedding_manager: Optional[EmbeddingModelManager] = None
_manager_lock = threading.Lock()


def get_embedding_manager() -> EmbeddingModelManager:
    """Get or create the global embedding model manager.

    On first creation, applies the persisted model from
    ``embedding_model_settings.json`` so the in-memory state matches disk.
    """
    global _embedding_manager

    with _manager_lock:
        if _embedding_manager is None:
            _embedding_manager = EmbeddingModelManager()
            _sync_manager_from_persisted(_embedding_manager)
        return _embedding_manager


def _sync_manager_from_persisted(manager: EmbeddingModelManager) -> None:
    """Apply the persisted embedding model selection (if valid) to *manager*."""
    try:
        from app.services.runtime_embedding import load_runtime_embedding_settings

        rt = load_runtime_embedding_settings()
        model_id = rt["model_id"]
        if model_id in manager.AVAILABLE_MODELS and model_id != manager.default_model:
            manager._current_model_id = model_id
    except Exception:
        pass


def reset_embedding_manager() -> None:
    """Reset the global embedding manager (for testing)."""
    global _embedding_manager
    with _manager_lock:
        _embedding_manager = None
