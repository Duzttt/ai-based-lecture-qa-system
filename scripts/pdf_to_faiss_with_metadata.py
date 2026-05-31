import glob
import sys
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.services.pdf_chunking import chunk_pdf_with_metadata  # noqa: E402


DEFAULT_DATA_SOURCE_DIR = Path("data_source")
DEFAULT_INDEX_PATH = Path("data/faiss_index/index.faiss")
DEFAULT_CHUNKS_PATH = Path("data/faiss_index/chunks.npy")
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_CHUNK_SIZE = 500


def _parse_args():
    parser = ArgumentParser(
        description=(
            "Read all PDFs from data_source/, chunk with metadata, embed, "
            "and append vectors to FAISS index + chunks.npy."
        )
    )
    parser.add_argument(
        "--data-source-dir",
        type=Path,
        default=DEFAULT_DATA_SOURCE_DIR,
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        default=DEFAULT_INDEX_PATH,
    )
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=DEFAULT_CHUNKS_PATH,
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=DEFAULT_MODEL_NAME,
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=DEFAULT_CHUNK_SIZE,
    )
    return parser.parse_args()


def _normalize_existing_chunks(existing: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for item in existing:
        if isinstance(item, dict):
            text = str(item.get("text", "")).strip()
            source = str(item.get("source", "unknown")).strip() or "unknown"
            page_raw = item.get("page")
            if isinstance(page_raw, (int, np.integer)):
                page = int(page_raw)
            elif isinstance(page_raw, str) and page_raw.strip().isdigit():
                page = int(page_raw.strip())
            else:
                page = None
            if text:
                normalized.append({"text": text, "source": source, "page": page})
            continue

        if isinstance(item, str):
            text = item.strip()
            if text:
                normalized.append({"text": text, "source": "unknown", "page": None})
            continue

        text = str(item).strip()
        if text:
            normalized.append({"text": text, "source": "unknown", "page": None})

    return normalized


def _load_existing_chunks(chunks_path: Path) -> List[Dict[str, Any]]:
    if not chunks_path.exists():
        return []

    loaded = np.load(str(chunks_path), allow_pickle=True).tolist()
    if not isinstance(loaded, list):
        loaded = [loaded]

    return _normalize_existing_chunks(loaded)


def _build_or_load_index(index_path: Path, embedding_dim: int):
    index_path.parent.mkdir(parents=True, exist_ok=True)
    if index_path.exists():
        index = faiss.read_index(str(index_path))
        if index.d != embedding_dim:
            raise ValueError(
                "Embedding dimension mismatch with existing index: "
                f"index.d={index.d}, embeddings.d={embedding_dim}"
            )
        return index

    return faiss.IndexFlatIP(embedding_dim)


def main():
    args = _parse_args()

    if not args.data_source_dir.exists():
        raise FileNotFoundError(
            f"Data source folder not found: {args.data_source_dir.resolve()}"
        )

    pattern = str(args.data_source_dir / "*.pdf")
    pdf_files = sorted(glob.glob(pattern))
    if not pdf_files:
        raise FileNotFoundError(
            f"No PDF files found in folder: {args.data_source_dir.resolve()}"
        )

    all_chunk_dicts: List[Dict[str, Any]] = []
    processed_pdf_count = 0

    for pdf_file in pdf_files:
        pdf_path = Path(pdf_file)
        chunk_records = chunk_pdf_with_metadata(
            pdf_path=str(pdf_path),
            chunk_size=args.chunk_size,
            overlap=100,
            source_name=pdf_path.name,
        )
        if not chunk_records:
            continue

        processed_pdf_count += 1
        all_chunk_dicts.extend(chunk_records)

    if not all_chunk_dicts:
        raise ValueError("No valid text chunks generated from the given PDFs.")

    model = SentenceTransformer(args.model_name)
    chunk_texts = [item["text"] for item in all_chunk_dicts]
    embeddings = model.encode(chunk_texts, show_progress_bar=False)
    embeddings = np.asarray(embeddings, dtype="float32")
    # L2-normalize so inner product = cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1, norms)
    embeddings = embeddings / norms

    if embeddings.ndim != 2 or embeddings.shape[0] != len(all_chunk_dicts):
        raise ValueError("Embedding output shape is invalid for the generated chunks.")

    index = _build_or_load_index(args.index_path, embedding_dim=int(embeddings.shape[1]))
    index.add(embeddings)
    faiss.write_index(index, str(args.index_path))

    existing_chunks = _load_existing_chunks(args.chunks_path)
    merged_chunks = existing_chunks + all_chunk_dicts
    args.chunks_path.parent.mkdir(parents=True, exist_ok=True)
    np.save(str(args.chunks_path), np.array(merged_chunks, dtype=object))

    print(f"Processed PDF files: {processed_pdf_count}")
    print(f"Generated chunks with metadata: {len(all_chunk_dicts)}")
    print(f"Total chunks stored in chunks.npy: {len(merged_chunks)}")


if __name__ == "__main__":
    main()
