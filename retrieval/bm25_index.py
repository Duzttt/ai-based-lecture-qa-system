"""
BM25 Index implementation with tokenization support.

This module provides BM25 (Best Matching 25) full-text search capabilities.
"""

import re
from typing import Any, Dict, List, Tuple

try:
    from rank_bm25 import BM25Okapi
except ImportError as e:
    raise ImportError("Please install rank-bm25: pip install rank-bm25") from e


class BM25IndexError(Exception):
    """Custom exception for BM25Index errors."""

    pass


class BM25Index:
    """
    BM25 index with tokenization support.

    BM25 (Best Matching 25) is a ranking function used in information retrieval
    that estimates the relevance of documents to a given search query.

    Attributes:
        documents: List of document dictionaries with id and text
        tokenized_docs: List of tokenized documents for BM25
        bm25: BM25Okapi instance for scoring
        doc_map: Mapping from BM25 index to document ID
    """

    def __init__(self, documents: List[Dict[str, Any]]):
        """
        Build BM25 index.

        Args:
            documents: List[Dict] - Each document contains id, text
                Example: [{"id": "doc1", "text": "This is document content"}, ...]
        """
        if not documents:
            raise BM25IndexError("Documents list cannot be empty")

        self.documents = documents
        self.tokenized_docs: List[List[str]] = []
        self.bm25: BM25Okapi = None
        self.doc_map: Dict[int, str] = {}  # BM25 index -> doc_id

        self._build_index()

    def _tokenize_chinese(self, text: str) -> List[str]:
        """
        Tokenize text by splitting on whitespace and punctuation.

        Handles mixed Chinese/English text by splitting on word boundaries.

        Args:
            text: Input text to tokenize

        Returns:
            List of tokens
        """
        if not text or not text.strip():
            return []

        text = text.strip().lower()

        # Split on whitespace and punctuation, keeping sequences of word characters
        # This handles mixed Chinese/English: Chinese characters become individual tokens,
        # English words stay together
        tokens = re.findall(r"\w+", text)

        # Filter out empty tokens
        tokens = [t for t in tokens if t]

        return tokens

    def _build_index(self) -> None:
        """
        Build BM25 index.

        1. Tokenize documents
        2. Build rank_bm25 index
        """
        try:
            for idx, doc in enumerate(self.documents):
                text = doc.get("text", "")
                if not text:
                    continue

                tokens = self._tokenize_chinese(text)
                if tokens:
                    self.tokenized_docs.append(tokens)
                    self.doc_map[len(self.tokenized_docs) - 1] = doc.get(
                        "id", f"doc_{idx}"
                    )

            if not self.tokenized_docs:
                raise BM25IndexError("No valid documents to index")

            # Build BM25 index using Okapi variant
            self.bm25 = BM25Okapi(self.tokenized_docs)

        except Exception as e:
            raise BM25IndexError(f"Failed to build BM25 index: {str(e)}") from e

    def search(self, query: str, top_k: int = 20) -> List[Tuple[str, float]]:
        """
        Search BM25 index.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            List[(doc_id, score)] - Sorted by BM25 score in descending order
        """
        if not self.bm25:
            raise BM25IndexError("BM25 index not initialized")

        if not query or not query.strip():
            return []

        try:
            # Tokenize query using same method as documents
            query_tokens = self._tokenize_chinese(query)

            if not query_tokens:
                return []

            # Get BM25 scores for all documents
            scores = self.bm25.get_scores(query_tokens)

            # Get top_k indices
            top_indices = sorted(
                range(len(scores)), key=lambda i: scores[i], reverse=True
            )[:top_k]

            # Filter out zero scores and build results
            results: List[Tuple[str, float]] = []
            for idx in top_indices:
                if scores[idx] > 0 and idx in self.doc_map:
                    doc_id = self.doc_map[idx]
                    results.append((doc_id, float(scores[idx])))

            return results

        except Exception as e:
            raise BM25IndexError(f"Search failed: {str(e)}") from e

    def get_scores(self, query: str) -> Dict[str, float]:
        """
        Get BM25 scores for all documents.

        Args:
            query: Query string

        Returns:
            Dict[doc_id, score] - Scores for all documents
        """
        if not self.bm25:
            raise BM25IndexError("BM25 index not initialized")

        query_tokens = self._tokenize_chinese(query)
        scores = self.bm25.get_scores(query_tokens)

        return {
            self.doc_map[idx]: float(scores[idx])
            for idx in range(len(scores))
            if idx in self.doc_map
        }

    def get_document_count(self) -> int:
        """
        Get the number of documents in the index.

        Returns:
            int: Number of documents
        """
        return len(self.tokenized_docs)

    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """
        Rebuild the index.

        Args:
            documents: New document list
        """
        self.documents = documents
        self.tokenized_docs = []
        self.doc_map = {}
        self.bm25 = None
        self._build_index()
