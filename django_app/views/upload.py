import os

from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from app.config import settings
from app.services.pdf_indexing import PDFIndexingError, index_pdf_directory, index_pdf_file

from ._helpers import (
    INDEXING_STATUS_COMPLETED,
    INDEXING_STRATEGY_APPEND,
    INDEXING_STRATEGY_FULL_REBUILD,
    _enqueue_full_rebuild,
    _error_response,
    _get_upload_indexing_state,
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
    if file_ext not in settings.ALLOWED_EXTENSIONS:
        return _error_response(
            f"Invalid file type. Allowed types: {settings.ALLOWED_EXTENSIONS}",
            status=400,
        )

    if upload_file.size > settings.MAX_UPLOAD_SIZE:
        return _error_response(
            f"File too large. Maximum size: {settings.MAX_UPLOAD_SIZE} bytes",
            status=400,
        )

    try:
        contents = upload_file.read()
        base_name, ext = os.path.splitext(original_filename)
        safe_filename = original_filename
        counter = 1
        while os.path.exists(os.path.join(settings.DOCUMENTS_PATH, safe_filename)):
            safe_filename = f"{base_name}_{counter}{ext}"
            counter += 1

        file_path = os.path.join(settings.DOCUMENTS_PATH, safe_filename)
        with open(file_path, "wb") as f:
            f.write(contents)
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
            index_stats = index_pdf_directory(
                data_source_dir=settings.DOCUMENTS_PATH,
                chunk_size=settings.CHUNK_SIZE,
                index_path=settings.FAISS_INDEX_PATH,
                model_name=settings.EMBEDDING_MODEL,
                clear_existing=True,
            )
        elif indexing_strategy == INDEXING_STRATEGY_APPEND:
            index_stats = index_pdf_file(
                pdf_path=saved_file_path,
                chunk_size=settings.CHUNK_SIZE,
                model_name=settings.EMBEDDING_MODEL,
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
