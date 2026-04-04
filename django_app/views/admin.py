import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.pdf_indexing import (
    index_pdf_directory,
    index_pdf_file,
)

from django_app.views.helpers import (
    _error_response,
    _get_json_body,
    _get_upload_indexing_state,
    _invalidate_index_dependent_caches,
)


@require_http_methods(["GET"])
def admin_stats(request: HttpRequest) -> JsonResponse:
    from django_app.models import QueryLog
    from django.db.models import Avg, Max

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
    from django_app.models import QueryLog
    from django.db.models import Avg, Count

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
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query", "")).strip()
    if not query:
        return _error_response("Query is required", status=400)

    params = payload.get("params", {})
    _alpha = float(params.get("alpha", 0.3))
    fusion_method = params.get("fusion", "rrf")
    top_k = int(params.get("top_k", 5))
    rrf_k = int(params.get("rrf_k", 60))

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
    _invalidate_index_dependent_caches()

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
    _invalidate_index_dependent_caches()

    return JsonResponse(
        {
            "success": True,
            "message": f"Document {doc_id} reindexed",
            "chunks_created": index_stats["chunks_created"],
        }
    )


@require_http_methods(["GET"])
def admin_indexing_status(request: HttpRequest) -> JsonResponse:
    state = _get_upload_indexing_state()
    return JsonResponse(state)


# A/B Testing

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
    tests = _load_ab_tests()
    return JsonResponse({"tests": tests})


@csrf_exempt
@require_http_methods(["POST"])
def admin_ab_test_create(request: HttpRequest) -> JsonResponse:
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
