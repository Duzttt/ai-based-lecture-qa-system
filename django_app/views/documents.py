import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from django.conf import settings as django_settings
from django.http import HttpRequest, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from ollama import Client as OllamaClient

from app.config import settings
from app.services.local_rag import (
    build_context_from_sources,
    generate_with_local_qwen,
    retrieve_with_faiss,
)
from app.services.pdf_indexing import PDFIndexingError, index_pdf_directory

from ._helpers import _error_response, _get_json_body, _load_rag_config


@require_http_methods(["GET"])
def list_files(request: HttpRequest) -> JsonResponse:
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
            model_name=settings.EMBEDDING_MODEL,
            clear_existing=True,
        )
    except PDFIndexingError as exc:
        return _error_response(str(exc), status=400)
    except Exception as exc:  # noqa: BLE001
        return _error_response(
            f"Failed to rebuild embeddings after delete: {str(exc)}",
            status=500,
        )

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
def compare_documents(request: HttpRequest) -> JsonResponse:
    try:
        payload = _get_json_body(request)
    except ValueError as exc:
        return _error_response(str(exc), status=400)

    query = str(payload.get("query") or "").strip()
    sources = payload.get("sources")

    if not query:
        return _error_response("Query cannot be empty", status=400)

    if not sources or not isinstance(sources, list):
        return _error_response("Sources must be a list of document names", status=400)

    if len(sources) < 2:
        return _error_response(
            "At least 2 documents required for comparison", status=400
        )

    if len(sources) > 3:
        return _error_response(
            "Maximum 3 documents can be compared at once", status=400
        )

    rag_config = _load_rag_config()
    top_k = rag_config.get("top_k", 3)
    llm_model = rag_config.get("llm_model", settings.LOCAL_QWEN_MODEL)
    temperature = rag_config.get("temperature", 0.7)

    results: List[Dict[str, Any]] = []

    for source in sources:
        try:
            retrieved = retrieve_with_faiss(
                query=query,
                top_k=top_k,
                source_filter=[source],
            )
            context = build_context_from_sources(retrieved)

            if not context.strip():
                results.append(
                    {
                        "source": source,
                        "answer": "No relevant content found in this document.",
                        "success": True,
                    }
                )
                continue

            system_prompt = (
                "You are a rigorous academic teaching assistant. Please answer the question "
                "based strictly on the provided reference material. If evidence is insufficient, "
                "say so clearly."
            )
            user_prompt = f"Reference material:\n{context}\n\nQuestion: {query}"

            ollama_client = OllamaClient(
                host=settings.LOCAL_QWEN_BASE_URL,
                timeout=settings.LOCAL_QWEN_TIMEOUT_SECONDS,
            )
            model_response = ollama_client.chat(
                model=llm_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                stream=False,
                keep_alive=settings.LOCAL_QWEN_KEEP_ALIVE,
                options={"temperature": temperature},
            )
            answer = str(model_response.get("message", {}).get("content", "")).strip()
            if not answer:
                answer = "Empty response from model."

            results.append(
                {
                    "source": source,
                    "answer": answer,
                    "success": True,
                }
            )

        except Exception as exc:  # noqa: BLE001
            results.append(
                {
                    "source": source,
                    "answer": f"Error: {str(exc)}",
                    "success": False,
                }
            )

    common_points, different_points = analyze_differences(
        [r["answer"] for r in results if r["success"]]
    )

    return JsonResponse(
        {
            "results": results,
            "analysis": {
                "common": common_points,
                "different": different_points,
            },
        }
    )


def analyze_differences(answers: List[str]) -> tuple[List[str], List[str]]:
    """
    Analyze differences between multiple answers.
    Returns (common_points, different_points).
    """
    if len(answers) < 2:
        return [], []

    import re

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


@csrf_exempt
@require_http_methods(["POST"])
def summarize_doc(request: HttpRequest) -> JsonResponse:
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
        # Attempt to filter by filename (case-insensitive and partial match to handle UUID prefixes)
        target = str(filename).lower()
        filtered = [
            s for s in retrieved_sources if target in str(s.get("source", "")).lower()
        ]

        if not filtered:
            filtered = retrieved_sources

        context = build_context_from_sources(filtered)
        summary = generate_with_local_qwen(query=query, context=context)

        return JsonResponse({"summary": summary, "filename": filename})
    except Exception as exc:  # noqa: BLE001
        return _error_response(f"Summary failed: {str(exc)}", status=500)


@csrf_exempt
@require_http_methods(["POST"])
def generate_podcast(request: HttpRequest) -> JsonResponse:
    # Placeholder for podcast generation logic
    # In a real implementation, this would generate a dialogue script and then use TTS.
    return JsonResponse(
        {
            "success": True,
            "message": "Podcast generation is a placeholder. Mock audio returned.",
            "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        }
    )
