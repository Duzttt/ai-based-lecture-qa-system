"""
Dense Retriever implementation using FAISS for vector search.

This module provides dense vector retrieval using sentence transformers
and FAISS for efficient similarity search.
"""

from typing import Any, Dict, List, Tuple

import numpy as np

try:
    import faiss
except ImportError:
    raise ImportError("Please install faiss-cpu: pip install faiss-cpu")

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "Please install sentence-transformers: pip install sentence-transformers"
    )


class DenseRetrieverError(Exception):
    """Custom exception for DenseRetriever errors."""

    pass


class DenseRetriever:
    """
    Vector retriever using FAISS for efficient similarity search.

    Uses sentence transformers to encode documents and queries into dense vectors,
    then uses FAISS for efficient nearest neighbor search with cosine similarity.

    Attributes:
        documents: List of document dictionaries
        embedder: SentenceTransformer model instance
        index: FAISS index for vector search
        doc_map: Mapping from FAISS index to document ID
        embeddings: Stored document embeddings
    """

    def __init__(
        self,
        documents: List[Dict[str, Any]],
        embedder: SentenceTransformer = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
    ):
        """
        Build vector index.

        Args:
            documents: List[Dict] - Document list containing id, text
                Example: [{"id": "doc1", "text": "Document content"}, ...]
            embedder: SentenceTransformer model instance (optional, auto-loaded if not provided)
            model_name: Model name (only used when embedder is None)
        """
        if not documents:
            raise DenseRetrieverError("Documents list cannot be empty")

        self.documents = documents
        self.doc_map: Dict[int, str] = {}  # FAISS index -> doc_id
        self.embeddings: np.ndarray = None
        self.index: faiss.Index = None

        # Initialize embedder
        if embedder is not None:
            self.embedder = embedder
        else:
            try:
                self.embedder = SentenceTransformer(model_name)
            except Exception as e:
                raise DenseRetrieverError(f"Failed to load embedding model: {str(e)}")

        self._build_index()

    def _get_embedding_dimension(self) -> int:
        """Get embedding dimension from the model."""
        dim = self.embedder.get_sentence_embedding_dimension()
        if dim is None:
            raise DenseRetrieverError("Could not determine embedding dimension")
        return dim

    def _build_index(self) -> None:
        """
        Build FAISS vector index.

        1. Generate all document vectors
        2. Normalize vectors (for cosine similarity)
        3. Build FAISS index (IndexFlatIP for inner product = cosine similarity on normalized vectors)
        """
        try:
            # Extract texts and build document map
            texts = []
            for idx, doc in enumerate(self.documents):
                text = doc.get("text", "")
                if text and str(text).strip():
                    texts.append(str(text).strip())
                    self.doc_map[len(texts) - 1] = doc.get("id", f"doc_{idx}")

            if not texts:
                raise DenseRetrieverError("No valid documents to index")

            # Generate embeddings for all documents
            embeddings = self.embedder.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            # Normalize embeddings for cosine similarity
            # Using L2 normalization makes inner product equivalent to cosine similarity
            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1  # Avoid division by zero
            self.embeddings = embeddings / norms

            # Build FAISS index with Inner Product (equivalent to cosine similarity on normalized vectors)
            embedding_dim = self._get_embedding_dimension()
            self.index = faiss.IndexFlatIP(embedding_dim)
            self.index.add(self.embeddings.astype("float32"))

        except Exception as e:
            raise DenseRetrieverError(f"Failed to build dense index: {str(e)}") from e

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Vector search.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            List[(doc_id, score)] - Sorted by similarity score in descending order
                Score range: [0, 1] (1 means identical)
        """
        if self.index is None or self.index.ntotal == 0:
            raise DenseRetrieverError("Dense index not initialized")

        if not query or not query.strip():
            return []

        try:
            # Encode query
            query_embedding = self.embedder.encode(
                [query],
                show_progress_bar=False,
                convert_to_numpy=True,
            )[0]

            # Normalize query vector
            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                query_embedding = query_embedding / norm

            # Search FAISS index
            k = min(top_k, self.index.ntotal)
            scores, indices = self.index.search(
                query_embedding.reshape(1, -1).astype("float32"), k
            )

            # Build results
            results: List[Tuple[str, float]] = []
            for score, idx in zip(scores[0], indices[0]):
                if idx >= 0 and idx in self.doc_map:
                    doc_id = self.doc_map[idx]
                    # FAISS IndexFlatIP returns inner product, which equals cosine similarity for normalized vectors
                    results.append((doc_id, float(score)))

            return results

        except Exception as e:
            raise DenseRetrieverError(f"Search failed: {str(e)}") from e

    def search_with_indices(
        self, query: str, top_k: int = 20
    ) -> Tuple[List[int], List[float]]:
        """
        Vector search returning raw indices.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            (List[doc_index], List[score]) - Document indices in the original list and scores
        """
        if self.index is None or self.index.ntotal == 0:
            raise DenseRetrieverError("Dense index not initialized")

        if not query or not query.strip():
            return [], []

        try:
            # Encode and normalize query
            query_embedding = self.embedder.encode(
                [query],
                show_progress_bar=False,
                convert_to_numpy=True,
            )[0]

            norm = np.linalg.norm(query_embedding)
            if norm > 0:
                query_embedding = query_embedding / norm

            # Search
            k = min(top_k, self.index.ntotal)
            scores, indices = self.index.search(
                query_embedding.reshape(1, -1).astype("float32"), k
            )

            return indices[0].tolist(), scores[0].tolist()

        except Exception as e:
            raise DenseRetrieverError(f"Search failed: {str(e)}") from e

    def get_document_count(self) -> int:
        """
        Get the number of documents in the index.

        Returns:
            int: Number of documents
        """
        return self.index.ntotal if self.index else 0

    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """
        Rebuild the index.

        Args:
            documents: New document list
        """
        self.documents = documents
        self.doc_map = {}
        self.embeddings = None
        self.index = None
        self._build_index()

    def add_documents(self, new_documents: List[Dict[str, Any]]) -> None:
        """
        Add new documents to the existing index.

        Args:
            new_documents: Documents to add
        """
        if not new_documents:
            return

        try:
            # Extract texts
            texts = []
            start_idx = len(self.doc_map)
            for doc in new_documents:
                text = doc.get("text", "")
                if text and str(text).strip():
                    texts.append(str(text).strip())
                    self.doc_map[len(self.doc_map)] = doc.get(
                        "id", f"doc_{len(self.doc_map)}"
                    )

            if not texts:
                return

            # Generate and normalize embeddings
            embeddings = self.embedder.encode(
                texts,
                show_progress_bar=False,
                convert_to_numpy=True,
            )

            norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
            norms[norms == 0] = 1
            normalized_embeddings = embeddings / norms

            # Add to FAISS index
            self.index.add(normalized_embeddings.astype("float32"))

            # Store embeddings
            if self.embeddings is not None:
                self.embeddings = np.vstack([self.embeddings, normalized_embeddings])
            else:
                self.embeddings = normalized_embeddings

        except Exception as e:
            raise DenseRetrieverError(f"Failed to add documents: {str(e)}") from e
