from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

from app.config import settings
from app.services.embedding import EmbeddingError, EmbeddingService
from app.services.pdf_chunking import _normalize_path_arg, chunk_pdf_with_metadata, read_pdf_text
from app.services.vector_store import VectorStore, VectorStoreError


class PDFIndexingError(Exception):
    pass


def _validate_embeddings(embeddings: np.ndarray, chunks: List[Dict[str, Any]]) -> int:
    if embeddings.size == 0:
        raise PDFIndexingError("Embedding result is empty")

    if embeddings.ndim != 2:
        raise PDFIndexingError("Embedding result should be a 2D matrix")

    if embeddings.shape[0] != len(chunks):
        raise PDFIndexingError("Embedding rows must match number of chunks")

    return int(embeddings.shape[1])


def index_pdf_file(
    pdf_path: str,
    chunk_size: int = 500,
    index_path: Optional[str] = None,
    model_name: Optional[str] = None,
    clear_existing: bool = False,
) -> Dict[str, int]:
    """
    Read PDF -> split into chunks -> embed -> store vectors in FAISS.

    Returns stats useful for API response / logging.
    """
    cleaned_pdf_path = _normalize_path_arg(pdf_path)
    try:
        text = read_pdf_text(cleaned_pdf_path)
    except FileNotFoundError as exc:
        raise PDFIndexingError(str(exc)) from exc
    except OSError as exc:
        raise PDFIndexingError(
            f"Failed to read PDF '{cleaned_pdf_path}': {str(exc)}"
        ) from exc
    if not text.strip():
        raise PDFIndexingError("No text extracted from PDF")

    source_name = Path(cleaned_pdf_path).name
    chunk_records = chunk_pdf_with_metadata(
        pdf_path=cleaned_pdf_path,
        chunk_size=chunk_size,
        source_name=source_name,
    )
    if not chunk_records:
        raise PDFIndexingError("No chunks created from text")

    embedding_service = EmbeddingService(
        model_name=model_name or settings.EMBEDDING_MODEL
    )

    try:
        chunk_texts = [chunk["text"] for chunk in chunk_records]
        embeddings = embedding_service.embed_texts(chunk_texts)
        embedding_dim = _validate_embeddings(embeddings, chunk_records)
    except EmbeddingError as exc:
        raise PDFIndexingError(str(exc)) from exc

    vector_store = VectorStore(
        index_path=index_path or settings.FAISS_INDEX_PATH,
        embedding_dim=embedding_dim,
    )

    if clear_existing:
        vector_store.clear()

    if (
        vector_store.index is not None
        and vector_store.index.ntotal > 0
        and vector_store.index.d != embedding_dim
    ):
        raise PDFIndexingError(
            "Embedding dimension mismatch with existing FAISS index. "
            "Use clear_existing=True or use the same embedding model."
        )

    try:
        vector_store.add_embeddings(embeddings, chunk_records)
        vector_store.save()
    except VectorStoreError as exc:
        raise PDFIndexingError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise PDFIndexingError(f"Failed to store embeddings: {str(exc)}") from exc

    return {
        "total_chars": len(text),
        "chunks_created": len(chunk_records),
        "total_chunks_in_index": vector_store.get_total_chunks(),
    }


def index_pdf_directory(
    data_source_dir: str,
    chunk_size: int = 500,
    index_path: Optional[str] = None,
    model_name: Optional[str] = None,
    clear_existing: bool = True,
) -> Dict[str, int]:
    """
    Index all PDF files in a directory.

    For "full rebuild", use clear_existing=True so the first PDF resets the index.
    """
    cleaned_dir_path = _normalize_path_arg(data_source_dir)
    source_dir = Path(cleaned_dir_path)
    if not source_dir.exists() or not source_dir.is_dir():
        raise PDFIndexingError(f"Data source directory not found: {cleaned_dir_path}")

    pdf_files = sorted(
        [
            item
            for item in source_dir.iterdir()
            if item.is_file() and item.suffix.lower() == ".pdf"
        ]
    )
    if not pdf_files:
        raise PDFIndexingError(f"No PDF files found in data source: {cleaned_dir_path}")

    total_chars = 0
    total_chunks_created = 0
    total_chunks_in_index = 0

    for idx, pdf_file in enumerate(pdf_files):
        stats = index_pdf_file(
            pdf_path=str(pdf_file),
            chunk_size=chunk_size,
            index_path=index_path,
            model_name=model_name,
            clear_existing=clear_existing and idx == 0,
        )
        total_chars += stats["total_chars"]
        total_chunks_created += stats["chunks_created"]
        total_chunks_in_index = stats["total_chunks_in_index"]

    return {
        "processed_pdfs": len(pdf_files),
        "total_chars": total_chars,
        "chunks_created": total_chunks_created,
        "total_chunks_in_index": total_chunks_in_index,
    }
