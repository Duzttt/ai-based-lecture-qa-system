"""
Retrieval Evaluator for measuring retrieval performance.

This module provides comprehensive evaluation metrics for retrieval systems:
- Recall @k: Fraction of relevant documents retrieved in top-k
- Precision @k: Fraction of retrieved documents that are relevant
- MRR (Mean Reciprocal Rank): Average of reciprocal ranks
- NDCG @k: Normalized Discounted Cumulative Gain
"""

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class RetrievalEvaluatorError(Exception):
    """Custom exception for RetrievalEvaluator errors."""

    pass


@dataclass
class EvaluationResult:
    """Stores evaluation metrics for a single query."""

    query_id: str
    recall_at_1: float = 0.0
    recall_at_3: float = 0.0
    recall_at_5: float = 0.0
    recall_at_10: float = 0.0
    precision_at_1: float = 0.0
    precision_at_3: float = 0.0
    precision_at_5: float = 0.0
    precision_at_10: float = 0.0
    reciprocal_rank: float = 0.0
    ndcg_at_5: float = 0.0
    ndcg_at_10: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """Convert to dictionary."""
        return {
            "query_id": self.query_id,
            "recall_at_1": self.recall_at_1,
            "recall_at_3": self.recall_at_3,
            "recall_at_5": self.recall_at_5,
            "recall_at_10": self.recall_at_10,
            "precision_at_1": self.precision_at_1,
            "precision_at_3": self.precision_at_3,
            "precision_at_5": self.precision_at_5,
            "precision_at_10": self.precision_at_10,
            "reciprocal_rank": self.reciprocal_rank,
            "ndcg_at_5": self.ndcg_at_5,
            "ndcg_at_10": self.ndcg_at_10,
        }


@dataclass
class AggregateMetrics:
    """Aggregate metrics across all queries."""

    num_queries: int = 0
    avg_recall_at_1: float = 0.0
    avg_recall_at_3: float = 0.0
    avg_recall_at_5: float = 0.0
    avg_recall_at_10: float = 0.0
    avg_precision_at_1: float = 0.0
    avg_precision_at_3: float = 0.0
    avg_precision_at_5: float = 0.0
    avg_precision_at_10: float = 0.0
    mrr: float = 0.0  # Mean Reciprocal Rank
    avg_ndcg_at_5: float = 0.0
    avg_ndcg_at_10: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "num_queries": self.num_queries,
            "recall_at_1": round(self.avg_recall_at_1, 4),
            "recall_at_3": round(self.avg_recall_at_3, 4),
            "recall_at_5": round(self.avg_recall_at_5, 4),
            "recall_at_10": round(self.avg_recall_at_10, 4),
            "precision_at_1": round(self.avg_precision_at_1, 4),
            "precision_at_3": round(self.avg_precision_at_3, 4),
            "precision_at_5": round(self.avg_precision_at_5, 4),
            "precision_at_10": round(self.avg_precision_at_10, 4),
            "mrr": round(self.mrr, 4),
            "ndcg_at_5": round(self.avg_ndcg_at_5, 4),
            "ndcg_at_10": round(self.avg_ndcg_at_10, 4),
        }


class RetrievalEvaluator:
    """
    Retrieval Evaluator.

    Computes standard information retrieval metrics:
    - Recall @k: What fraction of relevant documents were retrieved?
    - Precision @k: What fraction of retrieved documents are relevant?
    - MRR: How high in the ranking does the first relevant document appear?
    - NDCG @k: How good is the ranking considering relevance positions?

    Attributes:
        test_queries: List of test queries with expected relevant documents
        relevant_docs: Mapping from query_id to list of relevant doc_ids
    """

    def __init__(
        self,
        test_queries: List[Dict[str, Any]],
        relevant_docs: Optional[Dict[str, List[str]]] = None,
    ):
        """
        Initialize the evaluator.

        Args:
            test_queries: List[Dict] - each containing query, expected_doc_ids
                Example: [
                    {"id": "q1", "query": "What is machine learning", "expected_doc_ids": ["doc1", "doc2"]},
                    ...
                ]
            relevant_docs: Dict - query_id -> [relevant_doc_ids]
                (Optional if expected_doc_ids is already in test_queries)
        """
        self.test_queries = test_queries

        # Build relevant_docs mapping
        if relevant_docs is not None:
            self.relevant_docs = relevant_docs
        else:
            self.relevant_docs = {}
            for q in test_queries:
                query_id = q.get("id", f"q_{id(q)}")
                expected = q.get("expected_doc_ids", [])
                self.relevant_docs[query_id] = expected

    def evaluate(
        self,
        retriever: Any,
        top_k: int = 10,
    ) -> Tuple[AggregateMetrics, List[EvaluationResult]]:
        """
        Evaluate retriever performance.

        Computes:
        - Recall @k (k=1,3,5,10)
        - Precision @k
        - MRR (Mean Reciprocal Rank)
        - NDCG @k

        Args:
            retriever: Retriever instance, must have retrieve(query, top_k) method
                retrieve should return List[Dict], each Dict containing 'id' key
            top_k: Maximum number of retrieval results

        Returns:
            (AggregateMetrics, List[EvaluationResult]) - Aggregate metrics and detailed results per query
        """
        if not self.test_queries:
            raise RetrievalEvaluatorError("No test queries provided")

        results: List[EvaluationResult] = []

        for query_data in self.test_queries:
            query_id = query_data.get("id", f"q_{id(query_data)}")
            query_text = query_data.get("query", "")
            relevant_doc_ids = set(
                query_data.get("expected_doc_ids", self.relevant_docs.get(query_id, []))
            )

            if not relevant_doc_ids:
                continue  # Skip queries with no relevant documents

            # Perform retrieval
            try:
                retrieved = retriever.retrieve(query_text, top_k=top_k)
                retrieved_ids = [doc.get("id") for doc in retrieved if doc.get("id")]
            except Exception as e:
                raise RetrievalEvaluatorError(
                    f"Retrieval failed for query {query_id}: {str(e)}"
                )

            # Compute metrics
            result = self._compute_metrics(query_id, retrieved_ids, relevant_doc_ids)
            results.append(result)

        # Compute aggregate metrics
        aggregate = self._aggregate_metrics(results)

        return aggregate, results

    def _compute_metrics(
        self,
        query_id: str,
        retrieved_ids: List[str],
        relevant_doc_ids: set,
    ) -> EvaluationResult:
        """
        Compute all metrics for a single query.

        Args:
            query_id: Query ID
            retrieved_ids: List of retrieved document IDs (in ranking order)
            relevant_doc_ids: Set of relevant document IDs

        Returns:
            EvaluationResult: Result containing all metrics
        """
        result = EvaluationResult(query_id=query_id)

        # Compute relevance for each retrieved document
        relevances = [
            1 if doc_id in relevant_doc_ids else 0 for doc_id in retrieved_ids
        ]

        # Total relevant documents
        total_relevant = len(relevant_doc_ids)

        if total_relevant == 0:
            return result

        # Recall @k and Precision @k
        for k in [1, 3, 5, 10]:
            k_relevances = relevances[:k]
            k_relevant_count = sum(k_relevances)

            # Recall @k
            recall = k_relevant_count / total_relevant
            if k == 1:
                result.recall_at_1 = recall
            elif k == 3:
                result.recall_at_3 = recall
            elif k == 5:
                result.recall_at_5 = recall
            elif k == 10:
                result.recall_at_10 = recall

            # Precision @k
            precision = k_relevant_count / k if k > 0 else 0
            if k == 1:
                result.precision_at_1 = precision
            elif k == 3:
                result.precision_at_3 = precision
            elif k == 5:
                result.precision_at_5 = precision
            elif k == 10:
                result.precision_at_10 = precision

        # Reciprocal Rank (RR)
        # Find the rank of the first relevant document
        first_relevant_rank = None
        for rank, rel in enumerate(relevances, start=1):
            if rel == 1:
                first_relevant_rank = rank
                break

        if first_relevant_rank is not None:
            result.reciprocal_rank = 1.0 / first_relevant_rank
        else:
            result.reciprocal_rank = 0.0

        # NDCG @k
        result.ndcg_at_5 = self._compute_ndcg(relevances, total_relevant, k=5)
        result.ndcg_at_10 = self._compute_ndcg(relevances, total_relevant, k=10)

        return result

    def _compute_ndcg(
        self,
        relevances: List[int],
        total_relevant: int,
        k: int = 5,
    ) -> float:
        """
        Compute NDCG @k (Normalized Discounted Cumulative Gain).

        NDCG measures ranking quality by considering:
        - Relevance of documents
        - Position in the ranking (higher positions weighted more)

        Formula:
        - DCG @k = Σ (2^rel_i - 1) / log2(i + 1)
        - IDCG @k = Ideal DCG (perfect ranking)
        - NDCG @k = DCG @k / IDCG @k

        Args:
            relevances: List of relevance labels (1 for relevant, 0 for not)
            total_relevant: Total number of relevant documents
            k: Cut-off point

        Returns:
            float: NDCG @k score (0 to 1)
        """
        k_relevances = relevances[:k]

        # Compute DCG
        dcg = 0.0
        for i, rel in enumerate(k_relevances, start=1):
            dcg += (2**rel - 1) / math.log2(i + 1)

        # Compute IDCG (ideal DCG - all relevant docs at top)
        ideal_rels = [1] * min(total_relevant, k) + [0] * max(0, k - total_relevant)
        idcg = 0.0
        for i, rel in enumerate(ideal_rels, start=1):
            idcg += (2**rel - 1) / math.log2(i + 1)

        # Normalize
        if idcg == 0:
            return 0.0

        return dcg / idcg

    def _aggregate_metrics(
        self,
        results: List[EvaluationResult],
    ) -> AggregateMetrics:
        """
        Aggregate metrics across all queries.

        Args:
            results: List of EvaluationResult

        Returns:
            AggregateMetrics: Average metrics
        """
        if not results:
            return AggregateMetrics(num_queries=0)

        n = len(results)

        aggregate = AggregateMetrics(
            num_queries=n,
            avg_recall_at_1=sum(r.recall_at_1 for r in results) / n,
            avg_recall_at_3=sum(r.recall_at_3 for r in results) / n,
            avg_recall_at_5=sum(r.recall_at_5 for r in results) / n,
            avg_recall_at_10=sum(r.recall_at_10 for r in results) / n,
            avg_precision_at_1=sum(r.precision_at_1 for r in results) / n,
            avg_precision_at_3=sum(r.precision_at_3 for r in results) / n,
            avg_precision_at_5=sum(r.precision_at_5 for r in results) / n,
            avg_precision_at_10=sum(r.precision_at_10 for r in results) / n,
            mrr=sum(r.reciprocal_rank for r in results) / n,
            avg_ndcg_at_5=sum(r.ndcg_at_5 for r in results) / n,
            avg_ndcg_at_10=sum(r.ndcg_at_10 for r in results) / n,
        )

        return aggregate

    def compare(
        self,
        retrievers: Dict[str, Any],
        top_k: int = 10,
    ) -> Dict[str, AggregateMetrics]:
        """
        Compare multiple retrievers' performance.

        Args:
            retrievers: Dict[name, retriever] - Multiple retriever instances
            top_k: Maximum number of retrieval results

        Returns:
            Dict[retriever_name, AggregateMetrics] - Metrics for each retriever
        """
        results: Dict[str, AggregateMetrics] = {}

        for name, retriever in retrievers.items():
            aggregate, _ = self.evaluate(retriever, top_k=top_k)
            results[name] = aggregate

        return results

    def generate_report(
        self,
        aggregate: AggregateMetrics,
        results: List[EvaluationResult],
    ) -> str:
        """
        Generate evaluation report.

        Args:
            aggregate: Aggregate metrics
            results: Detailed results per query

        Returns:
            str: Formatted evaluation report
        """
        lines = [
            "=" * 60,
            "RETRIEVAL EVALUATION REPORT",
            "=" * 60,
            "",
            f"Number of queries: {aggregate.num_queries}",
            "",
            "AGGREGATE METRICS:",
            "-" * 40,
            f"Recall @1:     {aggregate.avg_recall_at_1:.4f}",
            f"Recall @3:     {aggregate.avg_recall_at_3:.4f}",
            f"Recall @5:     {aggregate.avg_recall_at_5:.4f}",
            f"Recall @10:    {aggregate.avg_recall_at_10:.4f}",
            "",
            f"Precision @1:  {aggregate.avg_precision_at_1:.4f}",
            f"Precision @3:  {aggregate.avg_precision_at_3:.4f}",
            f"Precision @5:  {aggregate.avg_precision_at_5:.4f}",
            f"Precision @10: {aggregate.avg_precision_at_10:.4f}",
            "",
            f"MRR:           {aggregate.mrr:.4f}",
            f"NDCG @5:       {aggregate.avg_ndcg_at_5:.4f}",
            f"NDCG @10:      {aggregate.avg_ndcg_at_10:.4f}",
            "",
            "=" * 60,
        ]

        return "\n".join(lines)
