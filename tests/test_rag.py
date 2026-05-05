from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Dict, List

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

QUERY = "what is the summary of the lecture 2 pdf"
SYSTEM_INSTRUCTION = "You are a rigorous academic teaching assistant. Please answer the questions based on the following reference materials."


def parse_args():
    parser = ArgumentParser(
        description=(
            "Load FAISS + chunks, retrieve Top-3 for a fixed query, "
            "then call local Ollama model with streaming output."
        )
    )
    parser.add_argument(
        "--index-path",
        type=Path,
        default=Path("data/faiss_index/index.faiss"),
    )
    parser.add_argument(
        "--chunks-path",
        type=Path,
        default=Path("data/faiss_index/chunks.npy"),
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default="sentence-transformers/all-MiniLM-L6-v2",
    )
    parser.add_argument(
        "--ollama-model",
        type=str,
        default="qwen2.5:3b",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=3,
    )
    return parser.parse_args()


def normalize_chunk(item: Any) -> Dict[str, Any]:
    if isinstance(item, dict):
        return {
            "text": str(item.get("text", "")),
            "source": str(item.get("source", "unknown")) or "unknown",
            "page": item.get("page"),
        }
    if isinstance(item, str):
        return {"text": item, "source": "unknown", "page": None}
    return {"text": str(item), "source": "unknown", "page": None}


def build_context(grounded_results: List[Dict[str, Any]]) -> str:
    context_blocks: List[str] = []
    for item in grounded_results:
        rank = item["rank"]
        source = item["source"]
        page = item.get("page")
        page_label = page if page is not None else "unknown"
        text = item["text"]
        context_blocks.append(
            f"[S{rank}] Source file: {source}, Page: {page_label}\n{text}"
        )
    return "\n\n".join(context_blocks)


def main():
    args = parse_args()

    try:
        import ollama
    except ImportError as exc:
        raise SystemExit(
            "Missing dependency: ollama. Install with: pip install ollama"
        ) from exc

    if not args.index_path.exists():
        raise FileNotFoundError(f"index.faiss not found: {args.index_path}")
    if not args.chunks_path.exists():
        raise FileNotFoundError(f"chunks.npy not found: {args.chunks_path}")

    index = faiss.read_index(str(args.index_path))
    chunks_raw = np.load(str(args.chunks_path), allow_pickle=True).tolist()
    if not isinstance(chunks_raw, list):
        chunks_raw = [chunks_raw]
    chunks = [normalize_chunk(item) for item in chunks_raw]

    if index.ntotal == 0:
        raise ValueError("FAISS index is empty.")

    model = SentenceTransformer(args.embedding_model)
    query_vector = model.encode([QUERY], show_progress_bar=False)
    query_vector = np.asarray(query_vector, dtype="float32")

    if query_vector.shape[1] != index.d:
        raise ValueError(
            "Embedding dimension mismatch: "
            f"query dim={query_vector.shape[1]}, index dim={index.d}"
        )

    top_k = max(1, min(args.top_k, index.ntotal))
    distances, indices = index.search(query_vector, top_k)

    grounded_results: List[Dict[str, Any]] = []
    for rank, (chunk_idx, distance) in enumerate(
        zip(indices[0], distances[0]),
        start=1,
    ):
        if chunk_idx < 0 or chunk_idx >= len(chunks):
            continue
        chunk = chunks[chunk_idx]
        grounded_results.append(
            {
                "rank": rank,
                "index": int(chunk_idx),
                "distance": float(distance),
                "text": chunk["text"],
                "source": chunk["source"],
                "page": chunk.get("page"),
            }
        )

    if not grounded_results:
        raise ValueError("No valid retrieval results were found.")

    context = build_context(grounded_results)

    print("=== Retrieval Top-3 ===")
    for item in grounded_results:
        print(
            f"[S{item['rank']}] index={item['index']} "
            f"distance={item['distance']:.6f} source={item['source']} page={item.get('page')}"
        )
    print("\n=== Streaming Answer ===")

    user_prompt = f"Reference materials:\n{context}\n\nUser question: {QUERY}"
    stream = ollama.chat(
        model=args.ollama_model,
        messages=[
            {"role": "system", "content": SYSTEM_INSTRUCTION},
            {"role": "user", "content": user_prompt},
        ],
        stream=True,
    )

    for chunk in stream:
        token = chunk.get("message", {}).get("content", "")
        if token:
            print(token, end="", flush=True)

    print()


if __name__ == "__main__":
    main()
