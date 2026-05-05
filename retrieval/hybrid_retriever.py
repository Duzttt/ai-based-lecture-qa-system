"""
Hybrid Retriever implementation combining BM25 and Dense Retrieval.

This module provides a hybrid search approach that leverages both:
- BM25: Keyword-based matching (lexical similarity)
- Dense Retrieval: Semantic matching using vector embeddings

The combination improves recall by capturing both exact term matches and semantic relationships.
"""

from typing import Any, Dict, List, Optional, Tuple
from enum import Enum

import numpy as np

from .bm25_index import BM25Index
from .dense_retriever import DenseRetriever

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    raise ImportError(
        "Please install sentence-transformers: pip install sentence-transformers"
    )


class FusionMethod(str, Enum):
    """Fusion method for combining BM25 and dense retrieval results."""

    RRF = "rrf"  # Reciprocal Rank Fusion
    WEIGHTED = "weighted"  # Weighted score fusion


class HybridRetrieverError(Exception):
    """Custom exception for HybridRetriever errors."""

    pass


class HybridRetriever:
    """
    Hybrid retriever combining BM25 and vector retrieval.

    Combines the strengths of:
    - BM25: Excellent for exact keyword matching, term frequency importance
    - Dense Retrieval: Captures semantic similarity, handles synonyms and paraphrases

    Attributes:
        documents: List of document dictionaries
        bm25_index: BM25Index instance
        dense_retriever: DenseRetriever instance
        fusion_method: Method for combining results
        doc_store: Document content storage by ID
    """

    def __init__(
        self,
        documents: List[Dict[str, Any]],
        embedder: SentenceTransformer = None,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        fusion_method: FusionMethod = FusionMethod.RRF,
    ):
        """
        Initialize both retrievers.

        Args:
            documents: List[Dict] - Each document contains id, text, metadata
                Example: [{"id": "doc1", "text": "Document content", "metadata": {...}}, ...]
            embedder: SentenceTransformer model instance (optional)
            model_name: Model name (only used when embedder is None)
            fusion_method: Fusion method ('rrf' or 'weighted')
        """
        if not documents:
            raise HybridRetrieverError("Documents list cannot be empty")

        self.documents = documents
        self.fusion_method = fusion_method
        self.doc_store: Dict[str, Dict[str, Any]] = {}

        # Build document store for quick lookup
        for doc in documents:
            doc_id = doc.get("id", f"doc_{id(doc)}")
            self.doc_store[doc_id] = doc

        # Initialize BM25 index
        try:
            self.bm25_index = BM25Index(documents)
        except Exception as e:
            raise HybridRetrieverError(f"Failed to initialize BM25: {str(e)}") from e

        # Initialize Dense retriever
        try:
            self.dense_retriever = DenseRetriever(
                documents=documents,
                embedder=embedder,
                model_name=model_name,
            )
        except Exception as e:
            raise HybridRetrieverError(
                f"Failed to initialize Dense Retriever: {str(e)}"
            ) from e

    def retrieve(
        self,
        query: str,
        top_k: int = 10,
        fusion_method: Optional[FusionMethod] = None,
        bm25_top_k: int = 20,
        dense_top_k: int = 20,
        rrf_k: int = 60,
        alpha: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        Main hybrid retrieval method.

        Args:
            query: User query string
            top_k: Number of results to return
            fusion_method: Override default fusion method ('rrf' or 'weighted')
            bm25_top_k: Number of BM25 candidates
            dense_top_k: Number of dense retrieval candidates
            rrf_k: RRF constant (default 60)
            alpha: Dense retrieval weight (only for weighted fusion, 0.3 means dense 30%, BM25 70%)

        Returns:
            List[Dict] - Each result contains id, text, score, source, metadata
        """
        if not query or not query.strip():
            return []

        # Use provided fusion method or default
        method = fusion_method if fusion_method else self.fusion_method

        # 1. BM25 retrieval
        bm25_results = self.bm25_index.search(query, top_k=bm25_top_k)

        # 2. Dense retrieval
        dense_results = self.dense_retriever.search(query, top_k=dense_top_k)

        # 3. Fuse results
        if method == FusionMethod.RRF:
            fused_scores = self.fusion_rrf(bm25_results, dense_results, k=rrf_k)
        else:  # WEIGHTED
            fused_scores = self.fusion_weighted(
                bm25_results, dense_results, alpha=alpha
            )

        # 4. Sort and return top_k
        sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

        # Build final results with document content
        final_results: List[Dict[str, Any]] = []
        for doc_id, score in sorted_results[:top_k]:
            if doc_id in self.doc_store:
                doc = self.doc_store[doc_id]
                final_results.append(
                    {
                        "id": doc_id,
                        "text": doc.get("text", ""),
                        "score": score,
                        "source": doc.get("source", "unknown"),
                        "metadata": doc.get("metadata", {}),
                    }
                )

        return final_results

    def fusion_rrf(
        self,
        bm25_results: List[Tuple[str, float]],
        dense_results: List[Tuple[str, float]],
        k: int = 60,
    ) -> Dict[str, float]:
        """
        Reciprocal Rank Fusion.

        RRF formula: score(d) = Σ 1/(k + rank(d))

        Where:
        - rank(d) is the position of document d in each result list
        - k is a constant that controls the influence of lower-ranked results
        - Higher k gives more weight to lower-ranked results

        Args:
            bm25_results: List[(doc_id, score)] from BM25
            dense_results: List[(doc_id, score)] from Dense Retriever
            k: RRF constant (default 60)

        Returns:
            Dict[doc_id, fused_score]
        """
        fused_scores: Dict[str, float] = {}

        # Process BM25 results
        for rank, (doc_id, _) in enumerate(bm25_results, start=1):
            rrf_score = 1.0 / (k + rank)
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + rrf_score

        # Process Dense results
        for rank, (doc_id, _) in enumerate(dense_results, start=1):
            rrf_score = 1.0 / (k + rank)
            fused_scores[doc_id] = fused_scores.get(doc_id, 0.0) + rrf_score

        return fused_scores

    def fusion_weighted(
        self,
        bm25_results: List[Tuple[str, float]],
        dense_results: List[Tuple[str, float]],
        alpha: float = 0.3,
    ) -> Dict[str, float]:
        """
        Weighted fusion.

        Formula: score = alpha * norm(dense_score) + (1-alpha) * norm(bm25_score)

        Where:
        - alpha controls the weight of dense retrieval (0.3 = 30% dense, 70% BM25)
        - Scores are normalized to [0, 1] before fusion

        Args:
            bm25_results: List[(doc_id, score)] from BM25
            dense_results: List[(doc_id, score)] from Dense Retriever
            alpha: Dense retrieval weight (0.3 means dense 30%, BM25 70%)

        Returns:
            Dict[doc_id, fused_score]
        """
        # Collect all scores for normalization
        all_bm25_scores = [score for _, score in bm25_results]
        all_dense_scores = [score for _, score in dense_results]

        # Normalize scores to [0, 1]
        bm25_normalized = self._normalize_scores(bm25_results)
        dense_normalized = self._normalize_scores(dense_results)

        # Build fused scores
        fused_scores: Dict[str, float] = {}

        # Add BM25 results
        for doc_id, norm_score in bm25_normalized.items():
            fused_scores[doc_id] = (1 - alpha) * norm_score

        # Add/merge Dense results
        for doc_id, norm_score in dense_normalized.items():
            if doc_id in fused_scores:
                # Document appears in both results - add weighted dense score
                fused_scores[doc_id] += alpha * norm_score
            else:
                # Document only in dense results
                fused_scores[doc_id] = alpha * norm_score

        return fused_scores

    def _normalize_scores(self, results: List[Tuple[str, float]]) -> Dict[str, float]:
        """
        Normalize scores to [0, 1] range.

        Uses min-max normalization: norm(score) = (score - min) / (max - min)

        Args:
            results: List[(doc_id, score)]

        Returns:
            Dict[doc_id, normalized_score]
        """
        if not results:
            return {}

        scores = [score for _, score in results]
        min_score = min(scores)
        max_score = max(scores)

        # Handle edge case where all scores are the same
        if max_score == min_score:
            if max_score == 0:
                return {doc_id: 0.0 for doc_id, _ in results}
            return {doc_id: 1.0 for doc_id, _ in results}

        range_score = max_score - min_score
        return {doc_id: (score - min_score) / range_score for doc_id, score in results}

    def retrieve_with_scores(
        self,
        query: str,
        top_k: int = 10,
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Retrieve and return detailed score information.

        Args:
            query: Query string
            top_k: Number of results to return

        Returns:
            Dict with keys:
                - 'results': List of result documents
                - 'bm25_scores': Dict of BM25 scores
                - 'dense_scores': Dict of dense scores
                - 'fused_scores': Dict of fused scores
        """
        if not query or not query.strip():
            return {
                "results": [],
                "bm25_scores": {},
                "dense_scores": {},
                "fused_scores": {},
            }

        # Get individual retrieval results
        bm25_results = self.bm25_index.search(query, top_k=20)
        dense_results = self.dense_retriever.search(query, top_k=20)

        # Convert to dicts for easier access
        bm25_scores = {doc_id: score for doc_id, score in bm25_results}
        dense_scores = {doc_id: score for doc_id, score in dense_results}

        # Fuse scores
        if self.fusion_method == FusionMethod.RRF:
            fused_scores = self.fusion_rrf(bm25_results, dense_results)
        else:
            fused_scores = self.fusion_weighted(bm25_results, dense_results)

        # Sort and get top_k
        sorted_results = sorted(fused_scores.items(), key=lambda x: x[1], reverse=True)

        # Build final results
        results: List[Dict[str, Any]] = []
        for doc_id, score in sorted_results[:top_k]:
            if doc_id in self.doc_store:
                doc = self.doc_store[doc_id]
                results.append(
                    {
                        "id": doc_id,
                        "text": doc.get("text", ""),
                        "score": score,
                        "bm25_score": bm25_scores.get(doc_id, 0.0),
                        "dense_score": dense_scores.get(doc_id, 0.0),
                        "source": doc.get("source", "unknown"),
                        "metadata": doc.get("metadata", {}),
                    }
                )

        return {
            "results": results,
            "bm25_scores": bm25_scores,
            "dense_scores": dense_scores,
            "fused_scores": fused_scores,
        }

    def get_document_count(self) -> int:
        """
        Get the number of documents in the index.

        Returns:
            int: Number of documents
        """
        return len(self.documents)

    def refresh(self, documents: List[Dict[str, Any]]) -> None:
        """
        Rebuild the index.

        Args:
            documents: New document list
        """
        self.documents = documents
        self.doc_store = {}
        for doc in documents:
            doc_id = doc.get("id", f"doc_{id(doc)}")
            self.doc_store[doc_id] = doc

        self.bm25_index.refresh(documents)
        self.dense_retriever.refresh(documents)
