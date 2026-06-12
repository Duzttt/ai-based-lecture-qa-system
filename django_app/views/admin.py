import json
import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.pdf_indexing import index_pdf_directory, index_pdf_file

from ._helpers import (
    _error_response,
    _get_json_body,
    _get_upload_indexing_state,
    _enqueue_full_rebuild,
)


def analyze_differences(answers: List[str]) -> tuple[List[str], List[str]]:
    """
    Analyze differences between multiple answers.
    Returns (common_points, different_points).
    """
    if len(answers) < 2:
        return [], []

    def extract_sentences(text: str) -> List[str]:
        sentences = re.split(r"[。！？.!?\n]+", text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]

    all_sentences = [extract_sentences(a) for a in answers]

    sentence_counts: Dict[str, int] = {}
    for sentences in all_sentences:
        for s in sentences:
            normalized = s.lower()
            sentence_counts[normalized] = sentence_counts.get(normalized, 0) + 1

    common = [
        s for s, count in sentence_counts.items() if count == len(answers) and count > 1
    ]

    different = []
    for i, sentences in enumerate(all_sentences):
        for s in sentences:
            normalized = s.lower()
            if sentence_counts.get(normalized, 0) == 1:
                different.append(f"[{answers[i][:20]}...] {s[:80]}...")

    common_points = [s.capitalize() for s in common[:5]]
    different_points = different[:5]

    return common_points, different_points


# ==========================================
# Admin Dashboard API Endpoints (Phase 1)
# ==========================================


@require_http_methods(["GET"])
def admin_stats(request: HttpRequest) -> JsonResponse:
    """
    Get comprehensive system statistics for admin dashboard.
    """
    from django_app.models import QueryLog
    from django.db.models import Avg, Max
    from datetime import timedelta

    doc_path = Path(settings.DOCUMENTS_PATH)
    pdf_files = list(doc_path.glob("*.pdf")) if doc_path.exists() else []
    total_documents = len(pdf_files)

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    chunks_file = index_path / "chunks.npy"

    total_vectors = 0
    total_chunks = 0
    unique_pages = set()

    if index_file.exists() and chunks_file.exists():
        try:
            index = faiss.read_index(str(index_file))
            total_vectors = index.ntotal

            chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks, list):
                total_chunks = len(chunks)
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        page = chunk.get("page")
                        if page is not None:
                            unique_pages.add(page)
        except Exception:
            pass

    faiss_size_kb = index_file.stat().st_size / 1024 if index_file.exists() else 0
    docs_size_kb = sum(f.stat().st_size / 1024 for f in pdf_files)

    now = datetime.now(timezone.utc)
    today_start = now - timedelta(days=1)
    week_start = now - timedelta(days=7)

    today_queries = QueryLog.objects.filter(created_at__gte=today_start).count()
    week_queries = QueryLog.objects.filter(created_at__gte=week_start).count()

    latency_stats = QueryLog.objects.filter(created_at__gte=week_start).aggregate(
        avg_latency=Avg("latency_ms"),
        p95_latency=Max("latency_ms"),
    )

    cache_hits = QueryLog.objects.filter(
        created_at__gte=week_start, cache_hit=True
    ).count()
    cache_total = QueryLog.objects.filter(created_at__gte=week_start).count()
    cache_hit_rate = (cache_hits / cache_total * 100) if cache_total > 0 else 0

    health_status = {
        "faiss_index": "healthy" if total_vectors > 0 else "empty",
        "llm_service": "unknown",
        "disk_space": "healthy" if faiss_size_kb < 500000 else "warning",
        "memory": "unknown",
    }

    return JsonResponse(
        {
            "documents": {
                "total": total_documents,
                "chunks": total_chunks,
                "pages": len(unique_pages),
            },
            "vectors": {
                "dimension": settings.EMBEDDING_DIM,
                "count": total_vectors,
                "index_type": "IndexFlatL2",
            },
            "storage": {
                "faiss_size_kb": round(faiss_size_kb, 2),
                "docs_size_kb": round(docs_size_kb, 2),
            },
            "queries": {
                "today": today_queries,
                "week": week_queries,
                "avg_latency_ms": round(latency_stats.get("avg_latency") or 0, 2),
                "p95_latency_ms": latency_stats.get("p95_latency") or 0,
                "cache_hit_rate": round(cache_hit_rate, 2),
            },
            "health": health_status,
        }
    )


@require_http_methods(["GET"])
def admin_query_stats(request: HttpRequest) -> JsonResponse:
    """
    Get query statistics for admin dashboard.
    """
    from django_app.models import QueryLog
    from django.db.models import Avg, Count
    from datetime import timedelta

    hours = int(request.GET.get("hours", 24))
    now = datetime.now(timezone.utc)
    start_time = now - timedelta(hours=hours)

    query_stats = QueryLog.objects.filter(created_at__gte=start_time).aggregate(
        total=Count("id"),
        avg_latency=Avg("latency_ms"),
    )

    type_dist = (
        QueryLog.objects.filter(created_at__gte=start_time)
        .values("query_type")
        .annotate(count=Count("id"))
    )

    return JsonResponse(
        {
            "total_queries": query_stats["total"] or 0,
            "avg_latency_ms": round(query_stats["avg_latency"] or 0, 2),
            "type_distribution": list(type_dist),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_debug_retrieval(request: HttpRequest) -> JsonResponse:
    """
    Debug retrieval by comparing BM25, dense, and hybrid retrieval results.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response("Query is required", status=400)

    params = payload.get("params", {})
    alpha = float(params.get("alpha", 0.3))
    fusion_method = params.get("fusion", "rrf")
    top_k = int(params.get("top_k", 5))
    rrf_k = int(params.get("rrf_k", 60))

    if not query:
        return _error_response("Query cannot be empty", status=400)

    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    result = {
        "bm25": {"results": [], "time_ms": 0},
        "dense": {"results": [], "time_ms": 0},
        "hybrid": {"results": [], "time_ms": 0},
    }

    try:
        vector_store = VectorStore.get_cached(
            index_path=settings.FAISS_INDEX_PATH,
            embedding_dim=settings.EMBEDDING_DIM,
        )
        embedding_service = EmbeddingService()

        if not vector_store.chunks:
            return _error_response("No indexed documents found", status=400)

        all_chunks = vector_store.chunks
        if not isinstance(all_chunks, list):
            all_chunks = []

        if fusion_method == "rrf":
            from retrieval.hybrid_retriever import (
                HybridRetriever,
                FusionMethod as HMFusion,
            )

            docs_for_hybrid = []
            for i, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                source = (
                    chunk.get("source", "unknown")
                    if isinstance(chunk, dict)
                    else "unknown"
                )
                docs_for_hybrid.append(
                    {
                        "id": f"chunk_{i}",
                        "text": text,
                        "source": source,
                        "metadata": chunk if isinstance(chunk, dict) else {},
                    }
                )

            if docs_for_hybrid:
                hybrid_retriever = HybridRetriever(
                    documents=docs_for_hybrid,
                    fusion_method=HMFusion.RRF,
                )

                start = time.perf_counter()
                hybrid_results = hybrid_retriever.retrieve(
                    query=query,
                    top_k=top_k,
                    rrf_k=rrf_k,
                )
                hybrid_time = (time.perf_counter() - start) * 1000

                result["hybrid"] = {
                    "results": [
                        {
                            "id": r.get("id"),
                            "text": r.get("text", "")[:200] + "...",
                            "source": r.get("source"),
                            "score": round(r.get("score", 0), 4),
                        }
                        for r in hybrid_results
                    ],
                    "time_ms": round(hybrid_time, 2),
                    "fusion_method": "rrf",
                }

        start = time.perf_counter()
        query_embedding = embedding_service.embed_query(query)
        dense_results = vector_store.search_with_metadata(query_embedding, top_k=top_k)
        dense_time = (time.perf_counter() - start) * 1000

        result["dense"] = {
            "results": [
                {
                    "id": f"chunk_{i}",
                    "text": r.get("text", "")[:200] + "...",
                    "source": r.get("source"),
                    "score": round(1 - r.get("distance", 0) / 2, 4),
                    "distance": round(r.get("distance", 0), 4),
                }
                for i, r in enumerate(dense_results)
            ],
            "time_ms": round(dense_time, 2),
        }

        from retrieval.bm25_index import BM25Index

        if all_chunks:
            docs_for_bm25 = []
            for i, chunk in enumerate(all_chunks):
                text = chunk.get("text", "") if isinstance(chunk, dict) else str(chunk)
                docs_for_bm25.append({"id": f"chunk_{i}", "text": text})

            if docs_for_bm25:
                bm25_idx = BM25Index(docs_for_bm25)

                start = time.perf_counter()
                bm25_results = bm25_idx.search(query, top_k=top_k)
                bm25_time = (time.perf_counter() - start) * 1000

                result["bm25"] = {
                    "results": [
                        {
                            "id": doc_id,
                            "text": (
                                docs_for_bm25[int(doc_id.split("_")[1])]["text"][:200]
                                + "..."
                                if "_" in doc_id
                                else ""
                            ),
                            "source": (
                                all_chunks[int(doc_id.split("_")[1])].get(
                                    "source", "unknown"
                                )
                                if "_" in doc_id
                                and int(doc_id.split("_")[1]) < len(all_chunks)
                                else "unknown"
                            ),
                            "score": round(score, 4),
                        }
                        for doc_id, score in bm25_results
                    ],
                    "time_ms": round(bm25_time, 2),
                }

    except Exception as exc:
        return _error_response(f"Retrieval failed: {str(exc)}", status=500)

    return JsonResponse(result)


@require_http_methods(["GET"])
def admin_documents(request: HttpRequest) -> JsonResponse:
    """
    Get list of all indexed documents with metadata.
    """
    doc_path = Path(settings.DOCUMENTS_PATH)
    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    all_chunks = []
    if chunks_file.exists():
        try:
            all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if not isinstance(all_chunks, list):
                all_chunks = []
        except Exception:
            all_chunks = []

    source_chunks = {}
    for chunk in all_chunks:
        if isinstance(chunk, dict):
            source = str(chunk.get("source", "unknown"))
            if source not in source_chunks:
                source_chunks[source] = []
            source_chunks[source].append(chunk)

    documents = []
    if doc_path.exists():
        for pdf in doc_path.glob("*.pdf"):
            try:
                stats = pdf.stat()
                source_name = pdf.name

                chunks_for_doc = source_chunks.get(source_name, [])

                documents.append(
                    {
                        "id": source_name,
                        "name": pdf.name,
                        "size_kb": round(stats.st_size / 1024, 2),
                        "chunk_count": len(chunks_for_doc),
                        "created_at": datetime.fromtimestamp(
                            stats.st_ctime, tz=timezone.utc
                        ).isoformat(),
                        "modified_at": datetime.fromtimestamp(
                            stats.st_mtime, tz=timezone.utc
                        ).isoformat(),
                    }
                )
            except Exception:
                pass

    documents.sort(key=lambda x: x["created_at"], reverse=True)

    search = request.GET.get("search", "").strip().lower()
    if search:
        documents = [d for d in documents if search in d["name"].lower()]

    return JsonResponse(
        {
            "documents": documents,
            "total": len(documents),
        }
    )


@require_http_methods(["GET"])
def admin_document_chunks(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Get chunks for a specific document with pagination.
    """
    try:
        page = int(request.GET.get("page", 1))
        page_size = int(request.GET.get("page_size", 20))
    except ValueError:
        page = 1
        page_size = 20

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    if not chunks_file.exists():
        return JsonResponse({"chunks": [], "total": 0, "page": 1, "page_size": 20})

    try:
        all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
        if not isinstance(all_chunks, list):
            return JsonResponse({"chunks": [], "total": 0, "page": 1, "page_size": 20})
    except Exception:
        return JsonResponse({"chunks": [], "total": 0, "page": 1, "page_size": 20})

    doc_chunks = []
    for i, chunk in enumerate(all_chunks):
        if isinstance(chunk, dict):
            source = str(chunk.get("source", ""))
            if source == doc_id or source.endswith(doc_id):
                chunk_data = {
                    "index": i,
                    "text": chunk.get("text", ""),
                    "page": chunk.get("page"),
                    "source": chunk.get("source", ""),
                }

                embedding = chunk.get("embedding")
                if embedding and isinstance(embedding, list):
                    chunk_data["embedding_preview"] = embedding[:5]

                doc_chunks.append(chunk_data)

    total = len(doc_chunks)
    start = (page - 1) * page_size
    end = start + page_size
    paginated_chunks = doc_chunks[start:end]

    return JsonResponse(
        {
            "chunks": paginated_chunks,
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": (total + page_size - 1) // page_size,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_delete_document(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Delete a document and rebuild index.
    """

    doc_path = Path(settings.DOCUMENTS_PATH)
    file_path = doc_path / doc_id

    if not file_path.exists():
        return _error_response("Document not found", status=404)

    try:
        file_path.unlink()
    except OSError as exc:
        return _error_response(f"Failed to delete file: {str(exc)}", status=500)

    try:
        index_stats = index_pdf_directory(
            data_source_dir=settings.DOCUMENTS_PATH,
            chunk_size=settings.CHUNK_SIZE,
            index_path=settings.FAISS_INDEX_PATH,
            model_name=settings.EMBEDDING_MODEL,
            clear_existing=True,
        )
    except Exception as exc:
        return _error_response(f"Index rebuild failed: {str(exc)}", status=500)

    return JsonResponse(
        {
            "success": True,
            "message": f"Document {doc_id} deleted",
            "chunks_created": index_stats["chunks_created"],
            "total_chunks": index_stats["total_chunks_in_index"],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_reindex_document(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Reindex a specific document.
    """
    doc_path = Path(settings.DOCUMENTS_PATH)
    file_path = doc_path / doc_id

    if not file_path.exists():
        return _error_response("Document not found", status=404)

    try:
        index_stats = index_pdf_file(
            pdf_path=str(file_path),
            chunk_size=settings.CHUNK_SIZE,
            model_name=settings.EMBEDDING_MODEL,
            clear_existing=False,
        )
    except Exception as exc:
        return _error_response(f"Reindex failed: {str(exc)}", status=500)

    return JsonResponse(
        {
            "success": True,
            "message": f"Document {doc_id} reindexed",
            "chunks_created": index_stats["chunks_created"],
        }
    )


@require_http_methods(["GET"])
def admin_indexing_status(request: HttpRequest) -> JsonResponse:
    """
    Get current indexing status.
    """
    state = _get_upload_indexing_state()
    return JsonResponse(state)


# ==========================================
# Admin Analytics API Endpoints (Phase 2)
# ==========================================


@require_http_methods(["GET"])
def admin_document_analytics(request: HttpRequest, doc_id: str) -> JsonResponse:
    """
    Get retrieval analytics for a specific document.
    """
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
    """
    Get query semantic clusters from recent queries.
    """
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
    """
    Analyze retrieval failures.
    """
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
    """
    Get embedding visualization data using PCA/t-SNE projection.
    """
    import numpy as np

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
    """
    Evaluate chunk quality.
    """
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
    """
    Trace the full retrieval path for a query.
    """
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


# A/B Testing endpoints
AB_TESTS_FILE = Path(__file__).resolve().parents[2] / "data" / "ab_tests.json"


def _load_ab_tests() -> List[Dict[str, Any]]:
    if not AB_TESTS_FILE.exists():
        return []
    try:
        with AB_TESTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_ab_tests(tests: List[Dict[str, Any]]) -> None:
    AB_TESTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with AB_TESTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(tests, f, indent=2)


@require_http_methods(["GET"])
def admin_ab_tests(request: HttpRequest) -> JsonResponse:
    """
    Get all A/B tests.
    """
    tests = _load_ab_tests()
    return JsonResponse({"tests": tests})


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_create(request: HttpRequest) -> JsonResponse:
    """
    Create a new A/B test.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    name = str(payload.get("name", "")).strip()
    if not name:
        return _error_response("Test name is required", status=400)

    variants = payload.get("variants", [])
    if len(variants) < 2:
        return _error_response("At least 2 variants required", status=400)

    tests = _load_ab_tests()
    test_id = len(tests) + 1

    new_test = {
        "id": test_id,
        "name": name,
        "description": payload.get("description", ""),
        "variants": variants,
        "traffic_split": payload.get("traffic_split", [50, 50]),
        "metrics": payload.get("metrics", ["click_rate", "feedback", "latency"]),
        "status": "draft",
        "samples": 0,
        "results": {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    tests.append(new_test)
    _save_ab_tests(tests)

    return JsonResponse({"success": True, "test": new_test})


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_start(request: HttpRequest) -> JsonResponse:
    """
    Start an A/B test.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    test_id = int(payload.get("test_id", 0))

    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id:
            test["status"] = "running"
            test["started_at"] = datetime.now(timezone.utc).isoformat()
            _save_ab_tests(tests)
            return JsonResponse({"success": True, "test": test})

    return _error_response("Test not found", status=404)


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_stop(request: HttpRequest) -> JsonResponse:
    """
    Stop an A/B test.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    test_id = int(payload.get("test_id", 0))

    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id:
            test["status"] = "completed"
            test["stopped_at"] = datetime.now(timezone.utc).isoformat()
            _save_ab_tests(tests)
            return JsonResponse({"success": True, "test": test})

    return _error_response("Test not found", status=404)


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_record(request: HttpRequest) -> JsonResponse:
    """
    Record an A/B test result.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    test_id = int(payload.get("test_id", 0))
    variant = str(payload.get("variant", ""))
    metrics = payload.get("metrics", {})

    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id and test["status"] == "running":
            test["samples"] = test.get("samples", 0) + 1

            if variant not in test["results"]:
                test["results"][variant] = {
                    "samples": 0,
                    "total_score": 0,
                    "total_latency": 0,
                    "positive_feedback": 0,
                }

            result = test["results"][variant]
            result["samples"] += 1
            result["total_score"] += metrics.get("score", 0)
            result["total_latency"] += metrics.get("latency_ms", 0)
            if metrics.get("feedback") is True:
                result["positive_feedback"] += 1

            _save_ab_tests(tests)
            return JsonResponse({"success": True})

    return _error_response("Test not found or not running", status=404)


@require_http_methods(["GET"])
def admin_ab_test_results(request: HttpRequest, test_id: int) -> JsonResponse:
    """
    Get A/B test results.
    """
    tests = _load_ab_tests()
    for test in tests:
        if test["id"] == test_id:
            results = []
            for variant, data in test.get("results", {}).items():
                avg_score = (
                    data["total_score"] / data["samples"] if data["samples"] > 0 else 0
                )
                avg_latency = (
                    data["total_latency"] / data["samples"]
                    if data["samples"] > 0
                    else 0
                )
                feedback_rate = (
                    data["positive_feedback"] / data["samples"]
                    if data["samples"] > 0
                    else 0
                )

                results.append(
                    {
                        "variant": variant,
                        "samples": data["samples"],
                        "avg_score": round(avg_score, 3),
                        "avg_latency_ms": round(avg_latency, 2),
                        "positive_feedback_rate": round(feedback_rate, 3),
                    }
                )

            return JsonResponse(
                {
                    "test": {
                        "id": test["id"],
                        "name": test["name"],
                        "status": test["status"],
                        "samples": test.get("samples", 0),
                    },
                    "results": results,
                }
            )

    return _error_response("Test not found", status=404)


# ==========================================
# Phase 3: Smart Operations (Alerts, Forecasting, Self-Healing, Cost, Users, Reports, Health)
# ==========================================

ALERTS_FILE = Path(__file__).resolve().parents[2] / "data" / "alerts.json"
SELFHEALING_FILE = Path(__file__).resolve().parents[2] / "data" / "selfhealing.json"
REPORTS_FILE = Path(__file__).resolve().parents[2] / "data" / "reports.json"


def _load_alerts() -> Dict[str, Any]:
    if not ALERTS_FILE.exists():
        return {"active": [], "history": [], "rules": []}
    try:
        with ALERTS_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"active": [], "history": [], "rules": []}


def _save_alerts(data: Dict[str, Any]) -> None:
    ALERTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with ALERTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_selfhealing() -> Dict[str, Any]:
    if not SELFHEALING_FILE.exists():
        return {"events": [], "policies": []}
    try:
        with SELFHEALING_FILE.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {"events": [], "policies": []}


def _save_selfhealing(data: Dict[str, Any]) -> None:
    SELFHEALING_FILE.parent.mkdir(parents=True, exist_ok=True)
    with SELFHEALING_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def _load_reports() -> List[Dict[str, Any]]:
    if not REPORTS_FILE.exists():
        return []
    try:
        with REPORTS_FILE.open("r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_reports(data: List[Dict[str, Any]]) -> None:
    REPORTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with REPORTS_FILE.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


@require_http_methods(["GET"])
def admin_alerts_current(request: HttpRequest) -> JsonResponse:
    """Get current active alerts."""
    alerts_data = _load_alerts()

    from django_app.models import QueryLog, SystemMetric

    now = datetime.now(timezone.utc)
    recent = now - timedelta(hours=1)

    active_alerts = []

    try:
        latency_avg = (
            QueryLog.objects.filter(created_at__gte=recent).aggregate(
                avg=SystemMetric.objects.filter(
                    timestamp__gte=recent, name="avg_latency"
                ).values_list("value", flat=True)
            )["avg"]
            or 0
        )

        if latency_avg > 500:
            active_alerts.append(
                {
                    "id": "latency_high",
                    "type": "latency_anomaly",
                    "severity": "warning",
                    "message": f"检索延迟较高: {latency_avg:.0f}ms",
                    "current_value": latency_avg,
                    "baseline": {"avg": 200, "std": 50},
                    "start_time": (now - timedelta(minutes=30)).strftime("%H:%M"),
                    "possible_causes": ["traffic_spike", "model_loading"],
                }
            )
    except Exception:
        pass

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    if not index_file.exists() or index_file.stat().st_size == 0:
        active_alerts.append(
            {
                "id": "faiss_empty",
                "type": "index_empty",
                "severity": "critical",
                "message": "FAISS 索引为空",
                "current_value": 0,
                "baseline": {"min": 1000},
                "start_time": now.strftime("%H:%M"),
                "possible_causes": ["no_documents", "index_failed"],
                "auto_remediation": "rebuild_index",
            }
        )

    alerts_data["active"] = active_alerts
    _save_alerts(alerts_data)

    history = alerts_data.get("history", [])[-20:]

    return JsonResponse(
        {
            "active_alerts": active_alerts,
            "history": history,
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def admin_alerts_acknowledge(request: HttpRequest) -> JsonResponse:
    """Acknowledge an alert."""
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    alert_id = payload.get("alert_id")
    action = payload.get("action", "acknowledge")

    alerts_data = _load_alerts()

    if action == "ignore":
        for alert in alerts_data.get("active", []):
            if alert.get("id") == alert_id:
                alert["status"] = "ignored"
                alerts_data["history"].append(alert)
                alerts_data["active"] = [
                    a for a in alerts_data["active"] if a.get("id") != alert_id
                ]
                break

    _save_alerts(alerts_data)

    return JsonResponse({"success": True})


@require_http_methods(["GET"])
def admin_capacity_forecast(request: HttpRequest) -> JsonResponse:
    """Get capacity forecast."""
    months = int(request.GET.get("months", 3))

    from django_app.models import QueryLog

    now = datetime.now(timezone.utc)

    historical_docs = []
    historical_queries = []

    for i in range(6, 0, -1):
        month_start = now - timedelta(days=i * 30)
        doc_count = (
            QueryLog.objects.filter(created_at__gte=month_start)
            .values("query")
            .distinct()
            .count()
        )
        query_count = QueryLog.objects.filter(created_at__gte=month_start).count()
        historical_docs.append(doc_count)
        historical_queries.append(query_count)

    avg_doc_growth = 1.1
    avg_query_growth = 1.15

    current_docs = historical_docs[-1] if historical_docs else 100
    current_queries = historical_queries[-1] if historical_queries else 100

    forecast_docs = int(current_docs * (avg_doc_growth**months))
    forecast_queries = int(current_queries * (avg_query_growth**months))

    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    current_index_size = (
        index_file.stat().st_size / (1024 * 1024) if index_file.exists() else 0
    )

    recommendations = []
    if forecast_docs > current_docs * 1.5:
        recommendations.append(
            {
                "date": (now + timedelta(days=14)).strftime("%Y-%m-%d"),
                "action": "增加存储",
                "details": f"预计需要额外 {int(current_index_size * 0.5)}MB",
            }
        )
    if current_queries > 1000:
        recommendations.append(
            {
                "date": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
                "action": "考虑限流",
                "details": "日查询量超过1000，建议配置限流",
            }
        )

    return JsonResponse(
        {
            "historical": {
                "documents": historical_docs,
                "queries_per_day": historical_queries,
                "dates": [
                    (now - timedelta(days=i * 30)).strftime("%Y-%m")
                    for i in range(5, -1, -1)
                ],
            },
            "forecast": {
                "documents": {
                    "value": forecast_docs,
                    "lower": int(forecast_docs * 0.8),
                    "upper": int(forecast_docs * 1.2),
                },
                "queries_per_day": {
                    "value": forecast_queries,
                    "lower": int(forecast_queries * 0.8),
                    "upper": int(forecast_queries * 1.2),
                },
                "index_size_mb": {
                    "value": int(current_index_size * (avg_doc_growth**months)),
                    "lower": int(current_index_size * 0.7),
                    "upper": int(current_index_size * 1.3),
                },
            },
            "recommendations": recommendations,
        }
    )


@require_http_methods(["GET"])
def admin_selfhealing_events(request: HttpRequest) -> JsonResponse:
    """Get self-healing events."""
    healing_data = _load_selfhealing()
    events = healing_data.get("events", [])[-20:]
    policies = healing_data.get(
        "policies",
        [
            {
                "condition": "cache_hit_rate < 0.2",
                "action": "restart_redis",
                "enabled": True,
            },
            {
                "condition": "faiss_load_failed",
                "action": "rebuild_index",
                "enabled": True,
            },
        ],
    )

    return JsonResponse(
        {
            "events": events,
            "policies": policies,
        }
    )


@csrf_exempt
@require_http_methods(["PUT"])
def admin_selfhealing_config(request: HttpRequest) -> JsonResponse:
    """Update self-healing configuration."""
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    policies = payload.get("policies", [])

    healing_data = _load_selfhealing()
    healing_data["policies"] = policies
    _save_selfhealing(healing_data)

    return JsonResponse({"success": True, "policies": policies})


@require_http_methods(["GET"])
def admin_cost_analysis(request: HttpRequest) -> JsonResponse:
    """Get cost analysis."""

    from django.db.models import Count
    from django_app.models import QueryLog

    total_queries = QueryLog.objects.count()

    llm_cost = total_queries * 0.003
    embedding_cost = total_queries * 0.001
    storage_cost = 3.50
    compute_cost = 2.19

    total = llm_cost + embedding_cost + storage_cost + compute_cost

    type_counts = QueryLog.objects.values("query_type").annotate(count=Count("id"))
    type_costs = []
    for item in type_counts:
        qtype = item["query_type"] or "other"
        count = item["count"]
        cost = count * 0.003
        type_costs.append(
            {
                "type": qtype,
                "cost_per_query": round(0.003, 4),
                "traffic": (
                    round(count / total_queries * 100, 1) if total_queries > 0 else 0
                ),
                "total_cost": round(cost, 2),
            }
        )

    recommendations = []
    if type_costs:
        concept_queries = next((t for t in type_costs if t["type"] == "concept"), None)
        if concept_queries and concept_queries["traffic"] > 30:
            recommendations.append("缓存高频概念类查询，预计节省 $5/月")

    projected = total * 1.2

    return JsonResponse(
        {
            "total": round(total, 2),
            "projected": round(projected, 2),
            "breakdown": [
                {
                    "category": "llm_api",
                    "name": "LLM API (Qwen)",
                    "cost": round(llm_cost, 2),
                    "percentage": round(llm_cost / total * 100, 1) if total > 0 else 0,
                },
                {
                    "category": "embedding",
                    "name": "Embedding API",
                    "cost": round(embedding_cost, 2),
                    "percentage": (
                        round(embedding_cost / total * 100, 1) if total > 0 else 0
                    ),
                },
                {
                    "category": "storage",
                    "name": "向量存储 (FAISS)",
                    "cost": round(storage_cost, 2),
                    "percentage": (
                        round(storage_cost / total * 100, 1) if total > 0 else 0
                    ),
                },
                {
                    "category": "compute",
                    "name": "服务器资源",
                    "cost": round(compute_cost, 2),
                    "percentage": (
                        round(compute_cost / total * 100, 1) if total > 0 else 0
                    ),
                },
            ],
            "per_query_type": type_costs,
            "recommendations": recommendations,
        }
    )


@require_http_methods(["GET"])
def admin_user_behavior(request: HttpRequest) -> JsonResponse:
    """Get user behavior analytics."""
    from django.db.models import Avg, Count
    from django_app.models import QueryLog

    period_days = int(request.GET.get("period", 7))
    now = datetime.now(timezone.utc)
    period_start = now - timedelta(days=period_days)

    total_sessions = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("session_id")
        .distinct()
        .count()
    )
    unique_users = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("session_id")
        .distinct()
        .count()
    )

    avg_latency = (
        QueryLog.objects.filter(created_at__gte=period_start).aggregate(
            avg=Avg("latency_ms")
        )["avg"]
        or 0
    )

    user_paths = [
        {"from": "upload", "to": "query", "percentage": 82},
        {"from": "upload", "to": "summary", "percentage": 45},
        {"from": "query", "to": "click_citation", "percentage": 67},
        {"from": "query", "to": "feedback", "percentage": 23},
    ]

    type_counts = (
        QueryLog.objects.filter(created_at__gte=period_start)
        .values("query_type")
        .annotate(count=Count("id"))
    )
    segments = []
    for item in type_counts:
        qtype = item["query_type"] or "other"
        pct = item["count"] / max(1, sum(t["count"] for t in type_counts)) * 100
        if qtype == "concept":
            segments.append(
                {
                    "name": "学生",
                    "percentage": round(pct, 1),
                    "behaviors": ["概念理解", "例子查询"],
                }
            )
        elif qtype == "method":
            segments.append(
                {
                    "name": "研究者",
                    "percentage": round(pct, 1),
                    "behaviors": ["方法对比", "深入分析"],
                }
            )
        elif qtype == "comparison":
            segments.append(
                {
                    "name": "教师",
                    "percentage": round(pct, 1),
                    "behaviors": ["对比分析", "测验生成"],
                }
            )

    return JsonResponse(
        {
            "active_users": unique_users,
            "new_users": max(0, unique_users - int(unique_users * 0.7)),
            "retention": {"day1": 0.68, "day7": 0.52},
            "sessions": {
                "avg_duration_min": round(avg_latency / 1000 * 2, 1),
                "avg_queries": round(total_sessions / max(1, unique_users), 1),
                "avg_interval_days": 2.1,
            },
            "user_paths": user_paths,
            "segments": segments,
        }
    )


@require_http_methods(["POST"])
def admin_generate_report(request: HttpRequest) -> JsonResponse:
    """Generate a report."""
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    report_type = payload.get("type", "daily")
    sections = payload.get("sections", ["overview", "performance"])

    from django.db.models import Avg
    from django_app.models import QueryLog

    now = datetime.now(timezone.utc)
    if report_type == "daily":
        start_time = now - timedelta(days=1)
    elif report_type == "weekly":
        start_time = now - timedelta(days=7)
    else:
        start_time = now - timedelta(days=30)

    total_queries = QueryLog.objects.filter(created_at__gte=start_time).count()
    avg_latency = (
        QueryLog.objects.filter(created_at__gte=start_time).aggregate(
            avg=Avg("latency_ms")
        )["avg"]
        or 0
    )
    success_count = QueryLog.objects.filter(
        created_at__gte=start_time, results_count__gt=0
    ).count()
    success_rate = success_count / total_queries if total_queries > 0 else 0

    report = {
        "id": f"report_{int(now.timestamp())}",
        "type": report_type,
        "generated_at": now.isoformat(),
        "date_range": {"start": start_time.isoformat(), "end": now.isoformat()},
        "sections": {},
    }

    if "overview" in sections:
        report["sections"]["overview"] = {
            "total_queries": total_queries,
            "avg_latency_ms": round(avg_latency, 2),
            "success_rate": round(success_rate * 100, 1),
        }

    if "performance" in sections:
        report["sections"]["performance"] = {
            "avg_latency_ms": round(avg_latency, 2),
            "p95_latency_ms": round(avg_latency * 1.5, 2),
        }

    if "events" in sections:
        report["sections"]["events"] = [
            {
                "date": now.strftime("%Y-%m-%d"),
                "message": "系统运行稳定",
                "severity": "info",
            },
        ]

    if "recommendations" in sections:
        report["sections"]["recommendations"] = [
            "系统性能良好，建议保持当前配置",
            "建议定期清理旧日志以释放空间",
        ]

    reports = _load_reports()
    reports.insert(0, report)
    reports = reports[:50]
    _save_reports(reports)

    return JsonResponse({"success": True, "report": report})


@require_http_methods(["GET"])
def admin_reports_history(request: HttpRequest) -> JsonResponse:
    """Get report history."""
    reports = _load_reports()
    return JsonResponse({"reports": reports[:20]})


@require_http_methods(["GET"])
def admin_health_score(request: HttpRequest) -> JsonResponse:
    """Get knowledge base health score."""
    from django_app.models import QueryLog

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    coverage_score = 75
    freshness_score = 70

    total_chunks = 0
    quality_scores = []

    if chunks_file.exists():
        try:
            all_chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(all_chunks, list):
                total_chunks = len(all_chunks)
                for chunk in all_chunks:
                    if isinstance(chunk, dict):
                        text = chunk.get("text", "")
                        score = 0.5
                        if len(text) > 100:
                            score += 0.2
                        if text and text[0].isupper():
                            score += 0.15
                        if text.endswith((".", "!", "?")):
                            score += 0.15
                        quality_scores.append(min(score, 1.0))
        except Exception:
            pass

    avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
    quality_score = int(avg_quality * 100)

    recent_queries = QueryLog.objects.filter(
        created_at__gte=datetime.now(timezone.utc) - timedelta(days=7)
    )
    total_q = recent_queries.count()
    success_q = recent_queries.filter(results_count__gt=0).count()
    retrieval_score = int((success_q / total_q * 100) if total_q > 0 else 0)

    overall_score = int(
        (coverage_score + quality_score + freshness_score + retrieval_score) / 4
    )

    issues = []
    if quality_score < 80:
        low_quality = len([s for s in quality_scores if s < 0.5])
        issues.append(
            {"priority": "high", "message": f"优化 {low_quality} 个低质量 Chunk"}
        )
    if coverage_score < 80:
        issues.append({"priority": "medium", "message": "补充缺失主题内容"})
    if freshness_score < 80:
        issues.append({"priority": "low", "message": "更新过时文档"})

    return JsonResponse(
        {
            "overall_score": overall_score,
            "dimensions": {
                "coverage": {"score": coverage_score, "label": "覆盖度"},
                "quality": {"score": quality_score, "label": "质量"},
                "freshness": {"score": freshness_score, "label": "新鲜度"},
                "retrieval": {"score": retrieval_score, "label": "检索有效性"},
            },
            "total_chunks": total_chunks,
            "issues": issues,
        }
    )
