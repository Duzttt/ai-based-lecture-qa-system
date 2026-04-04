"""
Admin Dashboard Utilities

Helper functions for monitoring, analytics, and system diagnostics.
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
from django.db.models import Avg, Count

from app.config import settings
from app.services.vector_store import VectorStore
from django_app.models import ConfigHistory, QueryLog, SystemMetric


def get_system_stats() -> Dict[str, Any]:
    """
    Get comprehensive system statistics.

    Returns:
        Dictionary containing document stats, vector stats, and storage info.
    """
    # Document statistics
    doc_path = Path(settings.DOCUMENTS_PATH)
    pdf_files = list(doc_path.glob("*.pdf")) if doc_path.exists() else []
    total_documents = len(pdf_files)

    # Calculate total pages and size
    total_pages = 0
    total_docs_size = 0
    for pdf in pdf_files:
        try:
            total_docs_size += pdf.stat().st_size
            # Page count would require PDF parsing; use chunk estimate instead
        except OSError:
            continue

    # Vector store statistics
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"
    index_file = index_path / "index.faiss"

    total_chunks = 0
    index_size = 0

    if chunks_file.exists():
        try:
            chunks_data = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks_data, list):
                total_chunks = len(chunks_data)
                # Estimate pages from chunks (rough estimate: ~2 chunks per page)
                total_pages = max(total_pages, len(chunks_data) // 2)
        except Exception:
            pass

    if index_file.exists():
        try:
            index_size = index_file.stat().st_size
        except OSError:
            pass

    # Storage statistics
    faiss_index_size_kb = index_size / 1024
    documents_size_kb = total_docs_size / 1024

    return {
        "documents": {
            "total": total_documents,
            "total_pages": total_pages,
            "total_chunks": total_chunks,
        },
        "vectors": {
            "dimension": settings.EMBEDDING_DIM,
            "index_type": "IndexFlatL2",
            "total_vectors": total_chunks,
        },
        "storage": {
            "faiss_index_size_kb": round(faiss_index_size_kb, 2),
            "documents_size_kb": round(documents_size_kb, 2),
        },
    }


def get_query_stats(time_range_hours: int = 24) -> Dict[str, Any]:
    """
    Get query statistics for a given time range.

    Args:
        time_range_hours: Number of hours to look back

    Returns:
        Dictionary containing query metrics.
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=time_range_hours)

    # Filter queries by time range
    queries = QueryLog.objects.filter(created_at__gte=cutoff_time)

    total_queries = queries.count()

    if total_queries == 0:
        return {
            "total_queries": 0,
            "avg_latency_ms": 0,
            "p95_latency_ms": 0,
            "cache_hit_rate": 0.0,
        }

    # Calculate latency statistics
    latencies = list(queries.values_list("latency_ms", flat=True))
    avg_latency = sum(latencies) / len(latencies)

    # P95 latency
    sorted_latencies = sorted(latencies)
    p95_index = int(len(sorted_latencies) * 0.95)
    p95_latency = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]

    # Cache hit rate
    cache_hits = queries.filter(cache_hit=True).count()
    cache_hit_rate = (cache_hits / total_queries * 100) if total_queries > 0 else 0

    return {
        "total_queries": total_queries,
        "avg_latency_ms": round(avg_latency, 2),
        "p95_latency_ms": p95_latency,
        "cache_hit_rate": round(cache_hit_rate, 2),
    }


def get_health_status() -> Dict[str, Any]:
    """
    Get system health status.

    Returns:
        Dictionary containing health checks for various components.
    """
    health_checks = {}

    # FAISS Index health
    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    chunks_file = index_path / "chunks.npy"

    faiss_healthy = index_file.exists() and chunks_file.exists()
    health_checks["faiss_index"] = {
        "healthy": faiss_healthy,
        "message": "OK" if faiss_healthy else "Index files missing",
    }

    # LLM service health
    llm_healthy = True
    llm_message = "OK"

    if settings.LLM_PROVIDER == "gemini":
        llm_healthy = bool(settings.GEMINI_API_KEY)
        llm_message = "OK" if llm_healthy else "API key missing"
    elif settings.LLM_PROVIDER == "openrouter":
        llm_healthy = bool(settings.OPENROUTER_API_KEY)
        llm_message = "OK" if llm_healthy else "API key missing"
    elif settings.LLM_PROVIDER == "local_llm":
        # Check if Ollama is reachable
        import httpx

        try:
            response = httpx.get(settings.LOCAL_LLM_BASE_URL, timeout=5)
            llm_healthy = response.status_code == 200
            llm_message = "OK" if llm_healthy else "Ollama not responding"
        except Exception:
            llm_healthy = False
            llm_message = "Cannot connect to Ollama"

    health_checks["llm_service"] = {
        "healthy": llm_healthy,
        "message": llm_message,
        "provider": settings.LLM_PROVIDER,
    }

    # Disk space check
    try:
        import shutil

        total_disk, used_disk, free_disk = shutil.disk_usage(
            str(Path(settings.DOCUMENTS_PATH).parent)
        )
        free_disk_gb = free_disk / (1024**3)
        disk_healthy = free_disk_gb > 1.0  # At least 1GB free
        health_checks["disk_space"] = {
            "healthy": disk_healthy,
            "message": f"{free_disk_gb:.2f} GB free",
        }
    except Exception:
        health_checks["disk_space"] = {
            "healthy": True,
            "message": "Unable to check",
        }

    # Memory check (basic)
    try:
        import psutil

        memory = psutil.virtual_memory()
        memory_percent = memory.percent
        memory_healthy = memory_percent < 90
        health_checks["memory"] = {
            "healthy": memory_healthy,
            "message": f"{memory_percent}% used",
        }
    except ImportError:
        health_checks["memory"] = {
            "healthy": True,
            "message": "psutil not installed",
        }
    except Exception:
        health_checks["memory"] = {
            "healthy": True,
            "message": "Unable to check",
        }

    # Overall health
    all_healthy = all(check["healthy"] for check in health_checks.values())

    return {
        "overall_healthy": all_healthy,
        "checks": health_checks,
    }


def get_performance_data(time_range: str = "24h") -> Dict[str, Any]:
    """
    Get performance data for charts.

    Args:
        time_range: Time range specifier ("24h", "7d", etc.)

    Returns:
        Dictionary containing time series data for charts.
    """
    if time_range == "24h":
        hours = 24
        interval = timedelta(hours=1)
    elif time_range == "7d":
        hours = 168
        interval = timedelta(hours=6)
    else:
        hours = 24
        interval = timedelta(hours=1)

    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    # Get latency trend
    latency_data = []
    current_time = cutoff_time
    while current_time < datetime.now(timezone.utc):
        window_end = current_time + interval
        queries = QueryLog.objects.filter(
            created_at__gte=current_time, created_at__lt=window_end
        )

        if queries.exists():
            avg_latency = queries.aggregate(Avg("latency_ms"))["latency_ms__avg"] or 0
            query_count = queries.count()
        else:
            avg_latency = 0
            query_count = 0

        latency_data.append(
            {
                "timestamp": current_time.isoformat(),
                "avg_latency_ms": round(avg_latency, 2),
                "query_count": query_count,
            }
        )

        current_time = window_end

    # Get query type distribution
    query_types = (
        QueryLog.objects.filter(created_at__gte=cutoff_time)
        .values("query_type")
        .annotate(count=Count("id"))
    )

    query_type_distribution = {
        item["query_type"]: item["count"] for item in query_types
    }

    # Get slow queries (top 5)
    slow_queries = QueryLog.objects.filter(created_at__gte=cutoff_time).order_by(
        "-latency_ms"
    )[:5]

    slow_queries_list = []
    for q in slow_queries:
        slow_queries_list.append(
            {
                "query": q.query[:100],
                "latency_ms": q.latency_ms,
                "query_type": q.query_type,
                "created_at": q.created_at.isoformat(),
                "possible_reason": _analyze_slow_query(q),
            }
        )

    return {
        "latency_trend": latency_data,
        "query_type_distribution": query_type_distribution,
        "slow_queries": slow_queries_list,
        "time_range": time_range,
    }


def _analyze_slow_query(query_log: QueryLog) -> str:
    """Analyze a slow query and suggest possible reasons."""
    reasons = []

    if query_log.latency_ms > 2000:
        reasons.append("Very high latency")

    if query_log.top_k > 10:
        reasons.append(f"High top_k ({query_log.top_k})")

    if not query_log.cache_hit:
        reasons.append("Cache miss")

    if query_log.results_count == 0:
        reasons.append("No results found")

    if len(query_log.query) > 200:
        reasons.append("Long query text")

    return "; ".join(reasons) if reasons else "Unknown"


def get_retrieval_debug_results(
    query: str, params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Get retrieval results for debugging with different strategies.

    Args:
        query: The query text
        params: Optional parameters (alpha, fusion method, etc.)

    Returns:
        Dictionary containing results from BM25, dense, and hybrid retrieval.
    """
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    params = params or {}
    alpha = params.get("alpha", 0.3)
    fusion_method = params.get("fusion", "rrf")

    # Initialize services
    embedding_service = EmbeddingService(model_name=settings.EMBEDDING_MODEL)
    vector_store = VectorStore.get_cached(
        index_path=settings.FAISS_INDEX_PATH,
        embedding_dim=settings.EMBEDDING_DIM,
    )

    results = {}

    # Dense retrieval (vector search)
    start_time = time.time()
    query_embedding = embedding_service.embed_query(query)
    dense_results = vector_store.search_with_metadata(query_embedding, top_k=10)
    dense_time = (time.time() - start_time) * 1000

    results["dense"] = {
        "results": [
            {
                "document_id": r.get("source", "unknown"),
                "score": float(1.0 - r.get("distance", 1.0)),
                "text_preview": str(r.get("text", ""))[:200],
                "page": r.get("page"),
            }
            for r in dense_results[:5]
        ],
        "time_ms": round(dense_time, 2),
    }

    # BM25 retrieval (keyword-based) - placeholder
    # In a real implementation, you'd use a library like rank-bm25
    start_time = time.time()
    bm25_results = _bm25_search(query, vector_store)
    bm25_time = (time.time() - start_time) * 1000

    results["bm25"] = {
        "results": bm25_results[:5],
        "time_ms": round(bm25_time, 2),
    }

    # Hybrid retrieval
    start_time = time.time()
    if fusion_method == "rrf":
        hybrid_results = _reciprocal_rank_fusion(dense_results, bm25_results, k=60)
    else:  # weighted
        hybrid_results = _weighted_fusion(dense_results, bm25_results, alpha=alpha)
    hybrid_time = (time.time() - start_time) * 1000

    results["hybrid"] = {
        "results": hybrid_results[:5],
        "time_ms": round(hybrid_time, 2),
        "fusion_method": fusion_method,
        "alpha": alpha,
    }

    return results


def _bm25_search(query: str, vector_store: VectorStore) -> List[Dict[str, Any]]:
    """
    Simple BM25-like search using keyword matching.

    This is a simplified implementation. For production, use rank-bm25 library.
    """
    query_terms = set(query.lower().split())

    scored_chunks = []
    for chunk in vector_store.chunks:
        text = str(chunk.get("text", "")).lower()

        # Simple term matching score
        score = sum(1 for term in query_terms if term in text)

        if score > 0:
            scored_chunks.append(
                {
                    "document_id": chunk.get("source", "unknown"),
                    "score": score / len(query_terms),
                    "text_preview": chunk.get("text", "")[:200],
                    "page": chunk.get("page"),
                }
            )

    # Sort by score descending
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    return scored_chunks


def _reciprocal_rank_fusion(
    dense_results: List[Dict], bm25_results: List[Dict], k: int = 60
) -> List[Dict[str, Any]]:
    """
    Reciprocal Rank Fusion for combining retrieval results.
    """
    # Create rank maps
    dense_ranks = {}
    for i, r in enumerate(dense_results):
        key = (r.get("source"), r.get("page"))
        dense_ranks[key] = i + 1

    bm25_ranks = {}
    for i, r in enumerate(bm25_results):
        key = (r.get("source"), r.get("page"))
        bm25_ranks[key] = i + 1

    # Calculate RRF scores
    all_keys = set(dense_ranks.keys()) | set(bm25_ranks.keys())

    fused_scores = {}
    for key in all_keys:
        dense_rank = dense_ranks.get(key, len(dense_results) + 1)
        bm25_rank = bm25_ranks.get(key, len(bm25_results) + 1)

        rrf_score = (1 / (k + dense_rank)) + (1 / (k + bm25_rank))
        fused_scores[key] = rrf_score

    # Sort by RRF score
    sorted_keys = sorted(
        fused_scores.keys(), key=lambda k: fused_scores[k], reverse=True
    )

    # Build results
    results = []
    for key in sorted_keys[:10]:
        # Find original result
        for r in dense_results + bm25_results:
            if (r.get("source"), r.get("page")) == key:
                results.append(
                    {
                        "document_id": r.get("source", "unknown"),
                        "score": fused_scores[key],
                        "text_preview": r.get("text", "")[:200],
                        "page": r.get("page"),
                    }
                )
                break

    return results


def _weighted_fusion(
    dense_results: List[Dict], bm25_results: List[Dict], alpha: float = 0.3
) -> List[Dict[str, Any]]:
    """
    Weighted fusion for combining retrieval results.
    """
    # Create score maps
    dense_scores = {}
    for r in dense_results:
        key = (r.get("source"), r.get("page"))
        dense_scores[key] = r.get("distance", 1.0)

    bm25_scores = {}
    for r in bm25_results:
        key = (r.get("source"), r.get("page"))
        bm25_scores[key] = r.get("score", 0.0)

    # Normalize scores
    max_dense = max(dense_scores.values()) if dense_scores else 1
    max_bm25 = max(bm25_scores.values()) if bm25_scores else 1

    all_keys = set(dense_scores.keys()) | set(bm25_scores.keys())

    fused_scores = {}
    for key in all_keys:
        dense_norm = 1 - (dense_scores.get(key, 1) / max_dense)
        bm25_norm = bm25_scores.get(key, 0) / max_bm25

        fused_score = alpha * dense_norm + (1 - alpha) * bm25_norm
        fused_scores[key] = fused_score

    # Sort by fused score
    sorted_keys = sorted(
        fused_scores.keys(), key=lambda k: fused_scores[k], reverse=True
    )

    # Build results
    results = []
    for key in sorted_keys[:10]:
        # Find original result
        for r in dense_results + bm25_results:
            if (r.get("source"), r.get("page")) == key:
                results.append(
                    {
                        "document_id": r.get("source", "unknown"),
                        "score": fused_scores[key],
                        "text_preview": r.get("text", "")[:200],
                        "page": r.get("page"),
                    }
                )
                break

    return results


def log_query(
    query: str,
    latency_ms: int,
    results_count: int,
    query_type: str = "other",
    cache_hit: bool = False,
    top_k: int = 3,
    similarity_threshold: float = 0.6,
    retrieved_documents: Optional[List] = None,
    user_feedback: Optional[bool] = None,
    session_id: str = "",
    llm_model: str = "",
    answer_length: int = 0,
    log_id: Optional[int] = None,
) -> QueryLog:
    """
    Log a query to the database.

    Args:
        query: The query text
        latency_ms: Query latency in milliseconds
        results_count: Number of results returned
        query_type: Type of query
        cache_hit: Whether result was from cache
        top_k: Top-K parameter used
        similarity_threshold: Similarity threshold used
        retrieved_documents: List of retrieved document references
        user_feedback: User feedback if provided
        session_id: Session identifier
        llm_model: LLM model used
        answer_length: Length of generated answer
        log_id: Existing QueryLog ID to update instead of creating a new row

    Returns:
        Created or updated QueryLog instance
    """
    payload = {
        "query": query,
        "query_type": query_type,
        "latency_ms": latency_ms,
        "cache_hit": cache_hit,
        "results_count": results_count,
        "top_k": top_k,
        "similarity_threshold": similarity_threshold,
        "retrieved_documents": retrieved_documents or [],
        "user_feedback": user_feedback,
        "session_id": session_id,
        "llm_model": llm_model,
        "answer_length": answer_length,
    }

    if log_id is not None:
        try:
            log_entry = QueryLog.objects.get(id=log_id)
        except QueryLog.DoesNotExist:
            pass
        else:
            for field, value in payload.items():
                setattr(log_entry, field, value)
            log_entry.save(update_fields=list(payload.keys()))
            return log_entry

    return QueryLog.objects.create(
        query=query,
        query_type=query_type,
        latency_ms=latency_ms,
        cache_hit=cache_hit,
        results_count=results_count,
        top_k=top_k,
        similarity_threshold=similarity_threshold,
        retrieved_documents=retrieved_documents or [],
        user_feedback=user_feedback,
        session_id=session_id,
        llm_model=llm_model,
        answer_length=answer_length,
    )


def record_metric(
    name: str,
    value: float,
    metadata: Optional[Dict[str, Any]] = None,
) -> SystemMetric:
    """
    Record a system metric.

    Args:
        name: Metric name
        value: Metric value
        metadata: Additional metadata

    Returns:
        Created SystemMetric instance
    """
    return SystemMetric.objects.create(
        name=name,
        value=value,
        metadata=metadata or {},
    )


def save_config_change(
    category: str,
    config: Dict[str, Any],
    previous_config: Optional[Dict[str, Any]] = None,
    changed_by: str = "system",
    reason: str = "",
) -> ConfigHistory:
    """
    Save a configuration change to history.

    Args:
        category: Configuration category
        config: New configuration values
        previous_config: Previous configuration values
        changed_by: Who made the change
        reason: Reason for the change

    Returns:
        Created ConfigHistory instance
    """
    # Deactivate previous active config for this category
    ConfigHistory.objects.filter(category=category, is_active=True).update(
        is_active=False
    )

    return ConfigHistory.objects.create(
        category=category,
        config=config,
        previous_config=previous_config or {},
        changed_by=changed_by,
        reason=reason,
        is_active=True,
    )
