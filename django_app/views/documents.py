import os
from pathlib import Path

from django.conf import settings as django_settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.pdf_loader import PDFLoader
from app.services.pdf_indexing import (
    PDFIndexingError,
    index_pdf_directory,
    index_pdf_file,
)
from app.services.runtime_embedding import load_runtime_embedding_settings

from django_app.views.helpers import (
    INDEXING_STATUS_COMPLETED,
    INDEXING_STRATEGY_APPEND,
    INDEXING_STRATEGY_FULL_REBUILD,
    _enqueue_full_rebuild,
    _error_response,
    _get_json_body,
    _get_upload_indexing_state,
    _invalidate_index_dependent_caches,
    _resolve_upload_indexing_strategy,
)


@require_http_methods(["GET"])
def upload_index_status(request: HttpRequest) -> JsonResponse:
    return JsonResponse(_get_upload_indexing_state())


@csrf_exempt
@require_http_methods(["POST"])
def upload_pdf(request: HttpRequest) -> JsonResponse:
    upload_file = request.FILES.get("file")
    if upload_file is None or not upload_file.name:
        return _error_response("No file provided", status=400)

    original_filename = os.path.basename(str(upload_file.name).strip())
    if not original_filename:
        return _error_response("Invalid filename", status=400)

    file_ext = os.path.splitext(original_filename)[1].lower()
    allowed_extensions = settings.allowed_extensions
    if file_ext not in allowed_extensions:
        return _error_response(
            f"Invalid file type. Allowed types: {sorted(allowed_extensions)}",
            status=400,
        )

    if upload_file.size > settings.MAX_UPLOAD_SIZE:
        return _error_response(
            f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE} bytes",
            status=400,
        )

    pdf_loader = PDFLoader(documents_path=settings.DOCUMENTS_PATH)

    try:
        contents = upload_file.read()
        base_name, ext = os.path.splitext(original_filename)
        safe_filename = original_filename
        counter = 1
        while os.path.exists(os.path.join(settings.DOCUMENTS_PATH, safe_filename)):
            safe_filename = f"{base_name}_{counter}{ext}"
            counter += 1

        saved_file_path = pdf_loader.save_pdf(contents, safe_filename)
    except OSError as exc:
        return _error_response(f"Failed to save PDF: {str(exc)}", status=500)

    indexing_strategy = _resolve_upload_indexing_strategy()
    if (
        indexing_strategy == INDEXING_STRATEGY_FULL_REBUILD
        and settings.UPLOAD_INDEXING_ASYNC
    ):
        state = _enqueue_full_rebuild(uploaded_filename=safe_filename)
        return JsonResponse(
            {
                "success": True,
                "message": "File uploaded. Full reindex is running in background.",
                "filename": safe_filename,
                "saved_path": saved_file_path,
                "indexing_mode": INDEXING_STRATEGY_FULL_REBUILD,
                "indexing_status": state["status"],
            },
            status=202,
        )

    try:
        if indexing_strategy == INDEXING_STRATEGY_FULL_REBUILD:
            rt = load_runtime_embedding_settings()
            index_stats = index_pdf_directory(
                data_source_dir=settings.DOCUMENTS_PATH,
                chunk_size=settings.CHUNK_SIZE,
                index_path=settings.FAISS_INDEX_PATH,
                model_name=rt["model_id"],
                clear_existing=True,
            )
        elif indexing_strategy == INDEXING_STRATEGY_APPEND:
            index_stats = index_pdf_file(
                pdf_path=saved_file_path,
                chunk_size=settings.CHUNK_SIZE,
                model_name=load_runtime_embedding_settings()["model_id"],
                clear_existing=False,
            )
        else:
            return _error_response(
                f"Invalid indexing strategy: {indexing_strategy}",
                status=500,
            )
    except PDFIndexingError as exc:
        return _error_response(str(exc), status=400)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to process embeddings: {str(exc)}",
            status=500,
        )
    _invalidate_index_dependent_caches()

    return JsonResponse(
        {
            "success": True,
            "message": "PDF uploaded and indexed successfully",
            "filename": safe_filename,
            "saved_path": saved_file_path,
            "indexing_mode": indexing_strategy,
            "indexing_status": INDEXING_STATUS_COMPLETED,
            "chunks_created": index_stats["chunks_created"],
            "total_chunks_in_index": index_stats["total_chunks_in_index"],
        }
    )


@require_http_methods(["GET"])
def list_files(request: HttpRequest) -> JsonResponse:
    from datetime import datetime, timezone

    doc_path = Path(settings.DOCUMENTS_PATH)
    files = []
    if doc_path.exists():
        for f in doc_path.glob("*.pdf"):
            stats = f.stat()
            files.append(
                {
                    "name": f.name,
                    "size": stats.st_size,
                    "created_at": datetime.fromtimestamp(
                        stats.st_ctime, tz=timezone.utc
                    ).isoformat(),
                }
            )
    return JsonResponse(
        {"files": sorted(files, key=lambda x: x["created_at"], reverse=True)}
    )


@require_http_methods(["GET"])
def list_documents(request: HttpRequest) -> JsonResponse:
    upload_dir = os.path.join(str(django_settings.MEDIA_ROOT), "data_source")
    if not os.path.exists(upload_dir):
        return JsonResponse({"files": []})

    files = sorted(
        [
            filename
            for filename in os.listdir(upload_dir)
            if filename.lower().endswith(".pdf")
        ]
    )
    return JsonResponse({"files": files})


@csrf_exempt
@require_http_methods(["POST"])
def delete_document(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    filename = str(payload.get("filename") or "").strip()
    if not filename:
        return _error_response("Filename is required", status=400)

    upload_dir = os.path.join(str(django_settings.MEDIA_ROOT), "data_source")
    file_path = os.path.join(upload_dir, filename)
    if not os.path.exists(file_path):
        return _error_response("File not found", status=404)

    try:
        os.remove(file_path)
    except OSError as exc:
        return _error_response(f"Failed to delete file: {str(exc)}", status=500)

    try:
        index_stats = index_pdf_directory(
            data_source_dir=settings.DOCUMENTS_PATH,
            chunk_size=settings.CHUNK_SIZE,
            index_path=settings.FAISS_INDEX_PATH,
            model_name=load_runtime_embedding_settings()["model_id"],
            clear_existing=True,
        )
    except PDFIndexingError as exc:
        return _error_response(str(exc), status=400)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to rebuild embeddings after delete: {str(exc)}",
            status=500,
        )
    _invalidate_index_dependent_caches()

    return JsonResponse(
        {
            "success": True,
            "message": "Document deleted and index rebuilt successfully",
            "filename": filename,
            "chunks_created": index_stats["chunks_created"],
            "total_chunks_in_index": index_stats["total_chunks_in_index"],
        }
    )


@csrf_exempt
@require_http_methods(["POST"])
def summarize_doc(request: HttpRequest) -> JsonResponse:
    from app.services.local_rag import (
        build_context_from_sources,
        generate_with_local_llm,
        retrieve_with_faiss,
    )

    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    filename = payload.get("filename")
    if not filename:
        return _error_response("Filename is required", status=400)

    query = (
        f"Please summarize the core content of document {filename}, and list the "
        "3 most important knowledge points."
    )

    try:
        retrieved_sources = retrieve_with_faiss(query=query, top_k=6)
        target = str(filename).lower()
        filtered = [
            s for s in retrieved_sources if target in str(s.get("source", "")).lower()
        ]

        if not filtered:
            filtered = retrieved_sources

        context = build_context_from_sources(filtered)
        summary = generate_with_local_llm(query=query, context=context)

        return JsonResponse({"summary": summary, "filename": filename})
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Summary failed: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_podcast(request: HttpRequest) -> JsonResponse:
    return JsonResponse(
        {
            "success": True,
            "message": "Podcast generation is a placeholder. Mock audio returned.",
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        }
    )
