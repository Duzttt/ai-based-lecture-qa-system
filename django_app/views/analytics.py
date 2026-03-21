import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict

import numpy as np
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from django_app.views.helpers import _error_response, _get_json_body


@require_http_methods(["GET"])
def admin_document_analytics(request: HttpRequest, doc_id: str) -> JsonResponse:
    from django_app.models import QueryLog

    decoded_doc_id = urllib.parse.unquote(doc_id)

    all_logs = QueryLog.objects.all()

    appearance_count = 0
    click_count = 0
    total_score = 0
    score_count = 0
    query_counts: Dict[str, int] = {}

    for log in all_logs:
        retrieved = log.retrieved_documents or []
        for item in retrieved:
            source = item.get("source", "")
            if decoded_doc_id in source or source.endswith(decoded_doc_id):
                appearance_count += 1
                score = item.get("score", 0)
                if score > 0:
                    total_score += score
                    score_count += 1
                if log.user_feedback is True:
                    click_count += 1

        query_text = log.query.lower()
        for item in retrieved:
            source = item.get("source", "")
            if decoded_doc_id in source or source.endswith(decoded_doc_id):
                if query_text not in query_counts:
                    query_counts[query_text] = 0
                query_counts[query_text] += 1

    top_queries = sorted(
        [{"query": q, "count": c} for q, c in query_counts.items()],
        key=lambda x: x["count"],
        reverse=True,
    )[:10]

    avg_score = total_score / score_count if score_count > 0 else 0
    click_rate = click_count / appearance_count if appearance_count > 0 else 0

    return JsonResponse(
        {
            "document_id": decoded_doc_id,
            "retrieval_stats": {
                "appearance_count": appearance_count,
                "avg_score": round(avg_score, 3),
                "click_count": click_count,
                "click_rate": round(click_rate, 3),
            },
            "top_queries": top_queries,
        }
    )


@require_http_methods(["GET"])
def admin_query_clusters(request: HttpRequest) -> JsonResponse:
    from django_app.models import QueryLog

    days = int(request.GET.get("days", 30))
    limit = min(int(request.GET.get("limit", 1000)), 5000)

    start_time = datetime.now(timezone.utc) - timedelta(days=days)
    queries = list(
        QueryLog.objects.filter(created_at__gte=start_time)
        .values_list("query", "query_type")
        .distinct()[:limit]
    )

    if not queries:
        return JsonResponse(
            {
                "clusters": [],
                "total_queries": 0,
                "message": "No queries found for clustering",
            }
        )

    type_counts: Dict[str, int] = {}
    for _, qtype in queries:
        qtype = qtype or "other"
        type_counts[qtype] = type_counts.get(qtype, 0) + 1

    total = len(queries)
    cluster_definitions = {
        "concept": {
            "name": "concept_definition",
            "patterns": ["what is", "define", "explain", "meaning of", "what does"],
            "color": "#22c55e",
        },
        "method": {
            "name": "method_process",
            "patterns": ["how to", "steps to", "process of", "how does", "method"],
            "color": "#3b82f6",
        },
        "comparison": {
            "name": "comparison",
            "patterns": ["difference between", "compare", "vs ", "versus", " versus "],
            "color": "#f59e0b",
        },
        "reason": {
            "name": "reason_explanation",
            "patterns": ["why does", "reason", "because", "explain why"],
            "color": "#8b5cf6",
        },
        "example": {
            "name": "example_application",
            "patterns": ["example", "application", "use case", "instance of"],
            "color": "#ec4899",
        },
    }

    clusters = []
    for qtype, info in cluster_definitions.items():
        count = type_counts.get(qtype, 0)
        if count > 0:
            queries_of_type = [q for q, t in queries if t == qtype]
            clusters.append(
                {
                    "name": info["name"],
                    "query_type": qtype,
                    "percentage": round(count / total * 100, 1),
                    "count": count,
                    "patterns": info["patterns"],
                    "color": info["color"],
                    "representative": queries_of_type[0] if queries_of_type else "",
                    "sample_queries": queries_of_type[:5],
                }
            )

    clusters.sort(key=lambda x: x["count"], reverse=True)

    return JsonResponse(
        {
            "clusters": clusters,
            "total_queries": total,
            "days": days,
        }
    )


@require_http_methods(["GET"])
def admin_failure_analysis(request: HttpRequest) -> JsonResponse:
    from django_app.models import QueryLog

    hours = int(request.GET.get("time_range", 24))
    start_time = datetime.now(timezone.utc) - timedelta(hours=hours)

    logs = QueryLog.objects.filter(created_at__gte=start_time)
    total = logs.count()

    if total == 0:
        return JsonResponse(
            {
                "failure_rate": 0,
                "breakdown": [],
                "suggestions": ["No query data available for analysis"],
            }
        )

    no_results = logs.filter(results_count=0).count()
    low_score_count = 0
    negative_feedback = logs.filter(user_feedback=False).count()

    for log in logs:
        if log.user_feedback is None and (log.latency_ms or 0) > 2000:
            low_score_count += 1

    failure_rate = (no_results + low_score_count + negative_feedback) / total

    suggestions = []
    if no_results > total * 0.05:
        suggestions.append("Consider adding synonym expansion for technical terms")
        suggestions.append("Review document coverage for common query topics")
    if low_score_count > total * 0.05:
        suggestions.append("Adjust similarity threshold or increase top_k")
        suggestions.append("Consider adding more descriptive content to documents")
    if negative_feedback > total * 0.02:
        suggestions.append("Review retrieved chunks for relevance")
        suggestions.append("Improve chunk boundaries for better context")

    return JsonResponse(
        {
            "failure_rate": round(failure_rate, 3),
            "time_range_hours": hours,
            "total_queries": total,
            "breakdown": [
                {
                    "type": "no_results",
                    "count": no_results,
                    "percentage": round(no_results / total * 100, 1),
                },
                {
                    "type": "low_score",
                    "count": low_score_count,
                    "percentage": round(low_score_count / total * 100, 1),
                },
                {
                    "type": "negative_feedback",
                    "count": negative_feedback,
                    "percentage": round(negative_feedback / total * 100, 1),
                },
            ],
            "suggestions": suggestions if suggestions else ["System performing well"],
        }
    )


@require_http_methods(["GET"])
def admin_embedding_visualization(request: HttpRequest) -> JsonResponse:
    method = request.GET.get("method", "pca")
    perplexity = int(request.GET.get("perplexity", 30))
    sample_size = min(int(request.GET.get("sample_size", 500)), 1000)

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse(
            {
                "points": [],
                "documents": [],
                "error": "No indexed data found",
            }
        )

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse(
                {"points": [], "documents": [], "error": "Invalid data"}
            )
    except Exception:
        return JsonResponse(
            {"points": [], "documents": [], "error": "Failed to load data"}
        )

    documents = list(
        set(str(c.get("source", "unknown")) for c in all_chunks if isinstance(c, dict))
    )
    doc_colors = {
        doc: f"hsl({(i * 360 / len(documents)) % 360}, 70%, 50%)"
        for i, doc in enumerate(documents)
    }

    chunks_with_embeddings = []
    for i, chunk in enumerate(all_chunks):
        if isinstance(chunk, dict):
            embedding = chunk.get("embedding")
            if embedding and isinstance(embedding, (list, np.ndarray)):
                chunks_with_embeddings.append(
                    {
                        "index": i,
                        "text": chunk.get("text", "")[:100],
                        "document": chunk.get("source", "unknown"),
                        "page": chunk.get("page"),
                        "embedding": embedding,
                    }
                )

    if len(chunks_with_embeddings) < 10:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Not enough embeddings for visualization",
            }
        )

    embeddings = np.array([c["embedding"] for c in chunks_with_embeddings])

    if embeddings.shape[1] != settings.EMBEDDING_DIM:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": f"Embedding dimension mismatch: {embeddings.shape[1]} vs {settings.EMBEDDING_DIM}",
            }
        )

    try:
        from sklearn.decomposition import PCA
        from sklearn.manifold import TSNE

        if method == "tsne":
            n_components = 2
            n_iter = 1000
            tsne = TSNE(
                n_components=n_components,
                perplexity=min(perplexity, len(embeddings) - 1),
                n_iter=n_iter,
                random_state=42,
            )
            projected = tsne.fit_transform(embeddings)
        else:
            pca = PCA(n_components=2, random_state=42)
            projected = pca.fit_transform(embeddings)
    except Exception:
        return JsonResponse(
            {
                "points": [],
                "documents": documents,
                "error": "Projection failed",
            }
        )

    points = []
    for i, chunk in enumerate(chunks_with_embeddings):
        points.append(
            {
                "x": float(projected[i, 0]),
                "y": float(projected[i, 1]),
                "chunk_index": chunk["index"],
                "document": chunk["document"],
                "document_color": doc_colors.get(chunk["document"], "#888"),
                "text_preview": chunk["text"],
                "page": chunk["page"],
            }
        )

    return JsonResponse(
        {
            "points": points[:sample_size],
            "documents": documents,
            "method": method,
            "total_chunks": len(chunks_with_embeddings),
        }
    )


@require_http_methods(["GET"])
def admin_chunk_quality(request: HttpRequest) -> JsonResponse:
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse(
            {
                "chunks": [],
                "overall_score": 0,
                "error": "No indexed data found",
            }
        )

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse({"chunks": [], "error": "Invalid data"})
    except Exception:
        return JsonResponse({"chunks": [], "error": "Failed to load data"})

    from django_app.models import QueryLog

    chunk_stats: Dict[int, Dict[str, Any]] = {}

    for log in QueryLog.objects.all():
        retrieved = log.retrieved_documents or []
        for i, item in enumerate(retrieved):
            chunk_idx = item.get("chunk_index", -1)
            if chunk_idx >= 0:
                if chunk_idx not in chunk_stats:
                    chunk_stats[chunk_idx] = {"hits": 0, "total_score": 0}
                chunk_stats[chunk_idx]["hits"] += 1
                chunk_stats[chunk_idx]["total_score"] += item.get("score", 0)

    chunk_qualities = []
    for i, chunk in enumerate(all_chunks):
        if not isinstance(chunk, dict):
            continue

        text = chunk.get("text", "")
        stats = chunk_stats.get(i, {"hits": 0, "total_score": 0})

        quality_score = 0.5

        if len(text) > 100:
            quality_score += 0.1
        if text and text[0].isupper():
            quality_score += 0.1
        if " " in text.strip():
            quality_score += 0.1

        if stats["hits"] > 0:
            quality_score += 0.1
            avg_score = stats["total_score"] / stats["hits"]
            if avg_score > 0.7:
                quality_score += 0.2
            elif avg_score > 0.5:
                quality_score += 0.1

        quality_score = min(quality_score, 1.0)

        issues = []
        if len(text) < 50:
            issues.append("Too short")
        if text.startswith("As mentioned") or text.startswith("Figure"):
            issues.append("Context dependent")
        if not text.endswith((".", "!", "?", ")")):
            issues.append("Incomplete sentence")

        chunk_qualities.append(
            {
                "index": i,
                "text_preview": text[:150] + "..." if len(text) > 150 else text,
                "source": chunk.get("source", ""),
                "page": chunk.get("page"),
                "quality_score": round(quality_score, 2),
                "retrieval_hits": stats["hits"],
                "avg_score": (
                    round(stats["total_score"] / stats["hits"], 3)
                    if stats["hits"] > 0
                    else 0
                ),
                "issues": issues,
            }
        )

    chunk_qualities.sort(key=lambda x: x["quality_score"], reverse=True)

    top_chunks = chunk_qualities[:10]
    low_chunks = [c for c in chunk_qualities if c["quality_score"] < 0.5][:10]

    overall = (
        sum(c["quality_score"] for c in chunk_qualities) / len(chunk_qualities)
        if chunk_qualities
        else 0
    )

    return JsonResponse(
        {
            "top_chunks": top_chunks,
            "low_quality_chunks": low_chunks,
            "overall_score": round(overall * 100),
            "total_chunks": len(chunk_qualities),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_retrieval_trace(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response("Query is required", status=400)

    trace_id = payload.get("trace_id") or f"trace_{int(time.time() * 1000)}"

    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    stages = []

    start = time.perf_counter()
    query_processed = query.lower().strip()
    tokens = query_processed.split()
    query_time = (time.perf_counter() - start) * 1000

    stages.append(
        {
            "name": "query_processing",
            "time_ms": round(query_time, 2),
            "details": {
                "original": query,
                "processed": query_processed,
                "tokens": tokens,
                "token_count": len(tokens),
            },
        }
    )

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        embedding_service = EmbeddingService()

        start = time.perf_counter()
        query_embedding = embedding_service.embed_query(query)
        embed_time = (time.perf_counter() - start) * 1000

        stages.append(
            {
                "name": "embedding_generation",
                "time_ms": round(embed_time, 2),
                "details": {
                    "model": settings.EMBEDDING_MODEL,
                    "dimension": len(query_embedding),
                },
            }
        )

        top_k = payload.get("top_k", 5)

        start = time.perf_counter()
        dense_results = vector_store.search_with_metadata(
            query_embedding, top_k=top_k * 3
        )
        dense_time = (time.perf_counter() - start) * 1000

        stages.append(
            {
                "name": "dense_retrieval",
                "time_ms": round(dense_time, 2),
                "results": [
                    {
                        "source": r.get("source"),
                        "score": round(1 - r.get("distance", 0) / 2, 4),
                        "text_preview": r.get("text", "")[:100],
                    }
                    for r in dense_results[:top_k]
                ],
            }
        )

        from retrieval.hybrid_retriever import HybridRetriever, FusionMethod
        from retrieval.bm25_index import BM25Index

        all_chunks = vector_store.chunks
        if isinstance(all_chunks, list) and len(all_chunks) > 0:
            docs_for_bm25 = []
            for j, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                docs_for_bm25.append({"id": f"chunk_{j}", "text": text})

            if docs_for_bm25:
                bm25_idx = BM25Index(docs_for_bm25)

                start = time.perf_counter()
                bm25_results = bm25_idx.search(query, top_k=top_k * 3)
                bm25_time = (time.perf_counter() - start) * 1000

                stages.append(
                    {
                        "name": "bm25_retrieval",
                        "time_ms": round(bm25_time, 2),
                        "results": [
                            {
                                "doc_id": doc_id,
                                "score": round(score, 4),
                            }
                            for doc_id, score in bm25_results[:top_k]
                        ],
                    }
                )

                docs_for_hybrid = []
                for j, chunk in enumerate(all_chunks):
                    text = (
                        chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                    )
                    source = (
                        chunk.get("source", "unknown")
                        if isinstance(chunk, dict)
                        else "unknown"
                    )
                    docs_for_hybrid.append(
                        {
                            "id": f"chunk_{j}",
                            "text": text,
                            "source": source,
                        }
                    )

                hybrid_retriever = HybridRetriever(
                    documents=docs_for_hybrid,
                    fusion_method=FusionMethod.RRF,
                )

                start = time.perf_counter()
                hybrid_results = hybrid_retriever.retrieve(query, top_k=top_k)
                fusion_time = (time.perf_counter() - start) * 1000

                stages.append(
                    {
                        "name": "hybrid_fusion",
                        "time_ms": round(fusion_time, 2),
                        "method": "rrf",
                        "results": [
                            {
                                "id": r.get("id"),
                                "score": round(r.get("score", 0), 4),
                                "source": r.get("source"),
                            }
                            for r in hybrid_results
                        ],
                    }
                )

        context_start = time.perf_counter()
        top_chunks = dense_results[:3]
        context_lines = []
        for idx, item in enumerate(top_chunks, 1):
            source = item.get("source", "unknown")
            page = item.get("page")
            text = item.get("text", "")
            context_lines.append(f"[{idx}] source={source} page={page}\n{text}")
        context = "\n\n".join(context_lines)
        context_time = (time.perf_counter() - context_start) * 1000

        stages.append(
            {
                "name": "context_building",
                "time_ms": round(context_time, 2),
                "chunks_used": len(top_chunks),
                "context_length": len(context),
            }
        )

        total_time = sum(s["time_ms"] for s in stages)

        bottleneck = max(stages, key=lambda s: s["time_ms"])

        return JsonResponse(
            {
                "trace_id": trace_id,
                "query": query,
                "stages": stages,
                "total_time": round(total_time, 2),
                "bottleneck": bottleneck["name"],
            }
        )

    except Exception as exc:
        return _error_response(f"Trace failed: {str(exc)}", status=500)
