import time
from datetime import datetime, timezone
from pathlib import Path

import faiss
import numpy as np
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings

from ._helpers import (
    INDEXING_STATUS_RUNNING,
    _enqueue_full_rebuild,
    _error_response,
    _get_json_body,
    _get_upload_indexing_state,
    _load_rag_config,
    _save_rag_config,
)


# ==========================================
# Dashboard API Endpoints
# ==========================================


@require_http_methods(["GET"])
def dashboard_stats(request: HttpRequest) -> JsonResponse:
    """
    Get dashboard statistics including document stats, vector info, and storage info.
    """

    # Document statistics
    doc_path = Path(settings.DOCUMENTS_PATH)
    pdf_files = list(doc_path.glob("*.pdf")) if doc_path.exists() else []
    total_documents = len(pdf_files)

    # Vector store statistics
    index_path = Path(settings.FAISS_INDEX_PATH)
    index_file = index_path / "index.faiss"
    chunks_file = index_path / "chunks.npy"

    total_vectors = 0
    embedding_dim = settings.EMBEDDING_DIM
    index_type = "IndexFlatL2"
    total_pages = 0
    total_chunks = 0

    if index_file.exists() and chunks_file.exists():
        try:
            index = faiss.read_index(str(index_file))
            total_vectors = index.ntotal

            chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks, list):
                total_chunks = len(chunks)
                # Count unique pages
                pages = set()
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        page = chunk.get("page")
                        if page is not None:
                            pages.add(page)
                        source = chunk.get("source", "")
                total_pages = len(pages) or total_documents
        except Exception:
            pass

    # Storage information
    faiss_size_kb = 0
    docs_size_kb = 0

    if index_file.exists():
        faiss_size_kb = index_file.stat().st_size / 1024

    for pdf in pdf_files:
        docs_size_kb += pdf.stat().st_size / 1024

    return JsonResponse(
        {
            "documents": {
                "total": total_documents,
                "total_pages": total_pages,
                "total_chunks": total_chunks,
            },
            "vectors": {
                "dimension": embedding_dim,
                "index_type": index_type,
                "total_vectors": total_vectors,
            },
            "storage": {
                "faiss_index_size_kb": round(faiss_size_kb, 2),
                "documents_size_kb": round(docs_size_kb, 2),
            },
        }
    )


@require_http_methods(["GET"])
def dashboard_metrics(request: HttpRequest) -> JsonResponse:
    """
    Get performance metrics including average retrieval and embedding times.
    """
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    # Measure embedding time
    embedding_time_ms = 0
    try:
        embedding_service = EmbeddingService()
        test_text = "This is a test sentence for measuring embedding performance."
        start = time.perf_counter()
        embedding_service.embed_query(test_text)
        embedding_time_ms = (time.perf_counter() - start) * 1000
    except Exception:
        pass

    # Measure retrieval time
    retrieval_time_ms = 0
    try:
        vector_store = VectorStore.get_cached(
            settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM
        )
        if vector_store.index and vector_store.index.ntotal > 0:
            embedding_service = EmbeddingService()
            query_embedding = embedding_service.embed_query("test query")
            start = time.perf_counter()
            vector_store.search(query_embedding, top_k=3)
            retrieval_time_ms = (time.perf_counter() - start) * 1000
    except Exception:
        pass

    # Quality metrics (placeholder - would need test set for real accuracy)
    quality_metrics = {
        "top_1_accuracy": None,
        "top_3_accuracy": None,
        "top_5_accuracy": None,
        "note": "Requires test set for accuracy calculation",
    }

    return JsonResponse(
        {
            "performance": {
                "avg_retrieval_time_ms": round(retrieval_time_ms, 2),
                "avg_embedding_time_ms": round(embedding_time_ms, 2),
            },
            "quality": quality_metrics,
        }
    )


@require_http_methods(["GET"])
def dashboard_chunks_distribution(request: HttpRequest) -> JsonResponse:
    """
    Get chunk length distribution data for histogram.
    """

    index_path = Path(settings.FAISS_INDEX_PATH)
    chunks_file = index_path / "chunks.npy"

    chunk_lengths = []
    if chunks_file.exists():
        try:
            chunks = np.load(chunks_file, allow_pickle=True).tolist()
            if isinstance(chunks, list):
                for chunk in chunks:
                    if isinstance(chunk, dict):
                        text = chunk.get("text", "")
                    else:
                        text = str(chunk)
                    chunk_lengths.append(len(text))
        except Exception:
            pass

    # Create histogram bins
    if chunk_lengths:
        min_len = min(chunk_lengths)
        max_len = max(chunk_lengths)
        bin_count = min(20, len(chunk_lengths))
        bin_width = (max_len - min_len) / bin_count if bin_count > 0 else 1

        bins = []
        for i in range(bin_count):
            bin_start = min_len + i * bin_width
            bin_end = min_len + (i + 1) * bin_width
            count = sum(1 for length in chunk_lengths if bin_start <= length < bin_end)
            bins.append(
                {
                    "range": f"{int(bin_start)}-{int(bin_end)}",
                    "count": count,
                }
            )

        stats = {
            "min": min_len,
            "max": max_len,
            "mean": round(sum(chunk_lengths) / len(chunk_lengths), 2),
            "median": sorted(chunk_lengths)[len(chunk_lengths) // 2],
        }
    else:
        bins = []
        stats = {"min": 0, "max": 0, "mean": 0, "median": 0}

    return JsonResponse(
        {
            "histogram": bins,
            "statistics": stats,
            "total_chunks": len(chunk_lengths),
        }
    )


@require_http_methods(["GET"])
def dashboard_similarity_distribution(request: HttpRequest) -> JsonResponse:
    """
    Get similarity score distribution data.
    """
    from app.services.embedding import EmbeddingService
    from app.services.vector_store import VectorStore

    similarity_scores = []

    try:
        vector_store = VectorStore.get_cached(
            settings.FAISS_INDEX_PATH, settings.EMBEDDING_DIM
        )
        if vector_store.index and vector_store.index.ntotal > 0:
            embedding_service = EmbeddingService()

            # Sample some queries and collect similarity scores
            test_queries = ["what is", "explain", "describe", "define", "list"]

            for query in test_queries:
                query_embedding = embedding_service.embed_query(query)
                results = vector_store.search_with_metadata(query_embedding, top_k=10)

                for result in results:
                    distance = result.get("distance", 0)
                    # Convert L2 distance to similarity (approximate)
                    similarity = max(0, 1 - (distance / 2))
                    similarity_scores.append(round(similarity, 3))
    except Exception:
        pass

    # Create distribution bins
    if similarity_scores:
        bins = []
        for i in range(10):
            bin_start = i * 0.1
            bin_end = (i + 1) * 0.1
            count = sum(
                1 for score in similarity_scores if bin_start <= score < bin_end
            )
            bins.append(
                {
                    "range": f"{bin_start:.1f}-{bin_end:.1f}",
                    "count": count,
                }
            )

        stats = {
            "min": round(min(similarity_scores), 3),
            "max": round(max(similarity_scores), 3),
            "mean": round(sum(similarity_scores) / len(similarity_scores), 3),
        }
    else:
        bins = []
        stats = {"min": 0, "max": 0, "mean": 0}

    return JsonResponse(
        {
            "histogram": bins,
            "statistics": stats,
            "sample_size": len(similarity_scores),
        }
    )


@require_http_methods(["GET"])
def dashboard_documents_timeline(request: HttpRequest) -> JsonResponse:
    """
    Get document upload timeline data.
    """
    doc_path = Path(settings.DOCUMENTS_PATH)
    documents = []

    if doc_path.exists():
        for pdf in doc_path.glob("*.pdf"):
            try:
                stats = pdf.stat()
                documents.append(
                    {
                        "name": pdf.name,
                        "display_name": (
                            "_".join(pdf.name.split("_")[1:])
                            if "_" in pdf.name
                            else pdf.name
                        ),
                        "size_kb": round(stats.st_size / 1024, 2),
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

    # Sort by creation date
    documents.sort(key=lambda x: x["created_at"], reverse=True)

    return JsonResponse(
        {
            "documents": documents,
            "total": len(documents),
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def dashboard_update_config(request: HttpRequest) -> JsonResponse:
    """
    Update RAG configuration including chunk_size, overlap, etc.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    chunk_size = payload.get("chunk_size")
    chunk_overlap = payload.get("chunk_overlap")

    # Update .env file or settings (for now, just validate)
    errors = []

    if chunk_size is not None:
        try:
            chunk_size = int(chunk_size)
            if chunk_size < 100 or chunk_size > 2000:
                errors.append("chunk_size must be between 100 and 2000")
        except (ValueError, TypeError):
            errors.append("chunk_size must be an integer")

    if chunk_overlap is not None:
        try:
            chunk_overlap = int(chunk_overlap)
            if chunk_overlap < 0 or chunk_overlap > 500:
                errors.append("chunk_overlap must be between 0 and 500")
        except (ValueError, TypeError):
            errors.append("chunk_overlap must be an integer")

    if errors:
        return _error_response("; ".join(errors), status=400)

    # Save to rag_config.json
    config = _load_rag_config()

    if chunk_size is not None:
        config["chunk_size"] = chunk_size
    if chunk_overlap is not None:
        config["chunk_overlap"] = chunk_overlap

    _save_rag_config(config)

    return JsonResponse(
        {
            "status": "success",
            "config": config,
            "message": "Configuration updated. Reindex required for chunking changes to take effect.",
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def dashboard_reindex(request: HttpRequest) -> JsonResponse:
    """
    Trigger reindexing of all documents.
    """
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    force = payload.get("force", False)

    # Check current indexing state
    current_state = _get_upload_indexing_state()
    if current_state["status"] == INDEXING_STATUS_RUNNING:
        return _error_response("Indexing is already in progress", status=409)

    # Trigger full rebuild
    state = _enqueue_full_rebuild(uploaded_filename="manual_reindex")

    return JsonResponse(
        {
            "status": "success",
            "message": "Reindexing started",
            "indexing_state": state,
        }
    )
