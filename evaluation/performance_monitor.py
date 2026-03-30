"""
Performance Monitor for real-time retrieval system monitoring.

This module provides tools for tracking and analyzing retrieval performance:
- Query latency tracking (average, p95, p99)
- Cache hit rate monitoring
- Component timing (BM25, dense retrieval, fusion)
- Performance reporting and alerting
"""

import statistics
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


@dataclass
class QueryRecord:
    """Records performance data for a single query."""

    query_id: str
    query_text: str
    timestamp: datetime
    total_latency_ms: float
    bm25_latency_ms: float = 0.0
    dense_latency_ms: float = 0.0
    fusion_latency_ms: float = 0.0
    cache_hit: bool = False
    num_results: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PerformanceMetrics:
    """Aggregated performance metrics."""

    total_queries: int = 0
    avg_latency_ms: float = 0.0
    p50_latency_ms: float = 0.0
    p95_latency_ms: float = 0.0
    p99_latency_ms: float = 0.0
    min_latency_ms: float = 0.0
    max_latency_ms: float = 0.0
    cache_hit_rate: float = 0.0
    avg_bm25_latency_ms: float = 0.0
    avg_dense_latency_ms: float = 0.0
    avg_fusion_latency_ms: float = 0.0
    queries_per_second: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_queries": self.total_queries,
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "p50_latency_ms": round(self.p50_latency_ms, 2),
            "p95_latency_ms": round(self.p95_latency_ms, 2),
            "p99_latency_ms": round(self.p99_latency_ms, 2),
            "min_latency_ms": round(self.min_latency_ms, 2),
            "max_latency_ms": round(self.max_latency_ms, 2),
            "cache_hit_rate": round(self.cache_hit_rate, 4),
            "avg_bm25_latency_ms": round(self.avg_bm25_latency_ms, 2),
            "avg_dense_latency_ms": round(self.avg_dense_latency_ms, 2),
            "avg_fusion_latency_ms": round(self.avg_fusion_latency_ms, 2),
            "queries_per_second": round(self.queries_per_second, 2),
        }


class PerformanceMonitorError(Exception):
    """Custom exception for PerformanceMonitor errors."""

    pass


class PerformanceMonitor:
    """
    Real-time performance monitoring.

    Tracks and analyzes retrieval system performance:
    - Query latency (total and per-component)
    - Cache hit rates
    - Throughput (queries per second)
    - Percentile statistics (p50, p95, p99)

    Attributes:
        records: List of query performance records
        cache_stats: Cache hit/miss statistics
        start_time: Monitor start time
    """

    def __init__(self, window_size: int = 1000):
        """
        Initialize the performance monitor.

        Args:
            window_size: Number of recent queries to keep for rolling statistics
        """
        self.window_size = window_size
        self.records: List[QueryRecord] = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.start_time = datetime.now()
        self._query_counter = 0

        # Component timing accumulators
        self.bm25_times: List[float] = []
        self.dense_times: List[float] = []
        self.fusion_times: List[float] = []

    def record_query(
        self,
        query: str,
        latency: float,
        cache_hit: bool = False,
        bm25_latency: float = 0.0,
        dense_latency: float = 0.0,
        fusion_latency: float = 0.0,
        num_results: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> QueryRecord:
        """
        Record query performance.

        Args:
            query: Query text
            latency: Total latency in milliseconds
            cache_hit: Whether cache hit
            bm25_latency: BM25 retrieval latency in milliseconds
            dense_latency: Dense retrieval latency in milliseconds
            fusion_latency: Fusion latency in milliseconds
            num_results: Number of returned results
            metadata: Additional metadata

        Returns:
            QueryRecord: The created record
        """
        self._query_counter += 1

        record = QueryRecord(
            query_id=f"q_{self._query_counter}",
            query_text=query,
            timestamp=datetime.now(),
            total_latency_ms=latency,
            bm25_latency_ms=bm25_latency,
            dense_latency_ms=dense_latency,
            fusion_latency_ms=fusion_latency,
            cache_hit=cache_hit,
            num_results=num_results,
            metadata=metadata or {},
        )

        self.records.append(record)

        # Update cache stats
        if cache_hit:
            self.cache_hits += 1
        else:
            self.cache_misses += 1

        # Update component timings
        if bm25_latency > 0:
            self.bm25_times.append(bm25_latency)
        if dense_latency > 0:
            self.dense_times.append(dense_latency)
        if fusion_latency > 0:
            self.fusion_times.append(fusion_latency)

        # Maintain window size
        if len(self.records) > self.window_size:
            # Remove oldest record's component times
            removed = self.records.pop(0)
            # Note: For simplicity, we don't remove from component lists
            # In production, you might want a more sophisticated approach

        return record

    def time_query(
        self,
        query_func: Callable[[str], Any],
        query: str,
        track_components: bool = True,
    ) -> Tuple[Any, QueryRecord]:
        """
        Time query execution.

        Decorator-style method to automatically time a query execution.

        Args:
            query_func: Function that executes the query (takes query string)
            query: Query text to execute
            track_components: Whether to track component timings

        Returns:
            (result, QueryRecord) - Query result and performance record
        """
        start_time = time.perf_counter()

        # For component tracking, we'd need to wrap the retriever
        # This is a simplified version
        result = query_func(query)

        end_time = time.perf_counter()
        total_latency_ms = (end_time - start_time) * 1000

        # Estimate component breakdown if tracking
        bm25_latency = dense_latency = fusion_latency = 0.0
        if track_components and hasattr(query_func, "component_times"):
            times = query_func.component_times  # type: ignore
            bm25_latency = times.get("bm25", 0.0) * 1000
            dense_latency = times.get("dense", 0.0) * 1000
            fusion_latency = times.get("fusion", 0.0) * 1000

        record = self.record_query(
            query=query,
            latency=total_latency_ms,
            cache_hit=False,  # Would need to track this separately
            bm25_latency=bm25_latency,
            dense_latency=dense_latency,
            fusion_latency=fusion_latency,
            num_results=len(result) if isinstance(result, list) else 0,
        )

        return result, record

    def get_metrics(self) -> PerformanceMetrics:
        """
        Get current performance metrics.

        Returns:
            PerformanceMetrics: Aggregated performance metrics
        """
        if not self.records:
            return PerformanceMetrics(total_queries=0)

        latencies = [r.total_latency_ms for r in self.records]
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        # Calculate percentiles
        p50_idx = int(n * 0.50)
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)

        # Cache hit rate
        total_cache_ops = self.cache_hits + self.cache_misses
        cache_hit_rate = (
            self.cache_hits / total_cache_ops if total_cache_ops > 0 else 0.0
        )

        # Time span for QPS calculation
        time_span = (datetime.now() - self.start_time).total_seconds()
        qps = n / time_span if time_span > 0 else 0.0

        # Component averages
        avg_bm25 = statistics.mean(self.bm25_times) if self.bm25_times else 0.0
        avg_dense = statistics.mean(self.dense_times) if self.dense_times else 0.0
        avg_fusion = statistics.mean(self.fusion_times) if self.fusion_times else 0.0

        return PerformanceMetrics(
            total_queries=n,
            avg_latency_ms=statistics.mean(latencies),
            p50_latency_ms=sorted_latencies[p50_idx] if n > 0 else 0.0,
            p95_latency_ms=sorted_latencies[p95_idx] if n > 0 else 0.0,
            p99_latency_ms=sorted_latencies[p99_idx] if n > 0 else 0.0,
            min_latency_ms=min(latencies),
            max_latency_ms=max(latencies),
            cache_hit_rate=cache_hit_rate,
            avg_bm25_latency_ms=avg_bm25,
            avg_dense_latency_ms=avg_dense,
            avg_fusion_latency_ms=avg_fusion,
            queries_per_second=qps,
        )

    def get_report(self) -> str:
        """
        Generate performance report.

        Returns:
            str: Formatted performance report
        """
        metrics = self.get_metrics()

        lines = [
            "=" * 60,
            "PERFORMANCE MONITORING REPORT",
            "=" * 60,
            "",
            f"Monitoring period: {self.start_time.strftime('%Y-%m-%d %H:%M:%S')} - now",
            f"Total queries: {metrics.total_queries}",
            "",
            "LATENCY STATISTICS:",
            "-" * 40,
            f"Average:     {metrics.avg_latency_ms:.2f} ms",
            f"P50 (Median): {metrics.p50_latency_ms:.2f} ms",
            f"P95:         {metrics.p95_latency_ms:.2f} ms",
            f"P99:         {metrics.p99_latency_ms:.2f} ms",
            f"Min:         {metrics.min_latency_ms:.2f} ms",
            f"Max:         {metrics.max_latency_ms:.2f} ms",
            "",
            "COMPONENT BREAKDOWN:",
            "-" * 40,
            f"BM25 (avg):  {metrics.avg_bm25_latency_ms:.2f} ms",
            f"Dense (avg): {metrics.avg_dense_latency_ms:.2f} ms",
            f"Fusion (avg): {metrics.avg_fusion_latency_ms:.2f} ms",
            "",
            "CACHE & THROUGHPUT:",
            "-" * 40,
            f"Cache hit rate: {metrics.cache_hit_rate * 100:.1f}%",
            f"Throughput: {metrics.queries_per_second:.2f} queries/sec",
            "",
            "=" * 60,
        ]

        return "\n".join(lines)

    def get_latency_summary(self) -> Dict[str, float]:
        """
        Get latency summary.

        Returns:
            Dict[str, float]: Latency statistics dictionary
        """
        metrics = self.get_metrics()
        return metrics.to_dict()

    def check_latency_threshold(
        self,
        threshold_ms: float = 200.0,
        percentile: float = 0.95,
    ) -> bool:
        """
        Check if latency exceeds threshold.

        Args:
            threshold_ms: Latency threshold in milliseconds
            percentile: Percentile (0.95 = p95)

        Returns:
            bool: True if latency exceeds threshold
        """
        if not self.records:
            return False

        latencies = [r.total_latency_ms for r in self.records]
        sorted_latencies = sorted(latencies)
        n = len(sorted_latencies)

        idx = int(n * percentile)
        percentile_latency = sorted_latencies[idx] if n > 0 else 0.0

        return percentile_latency > threshold_ms

    def reset(self) -> None:
        """Reset monitor statistics."""
        self.records = []
        self.cache_hits = 0
        self.cache_misses = 0
        self.start_time = datetime.now()
        self._query_counter = 0
        self.bm25_times = []
        self.dense_times = []
        self.fusion_times = []


class LatencyTracker:
    """
    Context manager for tracking latency of code blocks.

    Usage:
        with LatencyTracker() as tracker:
            # Execute code
            result = expensive_operation()

        print(f"Operation took {tracker.elapsed_ms:.2f} ms")
    """

    def __init__(self):
        self.start_time: float = 0.0
        self.end_time: float = 0.0
        self.elapsed_ms: float = 0.0

    def __enter__(self) -> "LatencyTracker":
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.end_time = time.perf_counter()
        self.elapsed_ms = (self.end_time - self.start_time) * 1000


class ComponentTimer:
    """
    Timer for tracking multiple components within a query.

    Usage:
        timer = ComponentTimer()

        with timer.track("bm25"):
            bm25_results = bm25_search(query)

        with timer.track("dense"):
            dense_results = dense_search(query)

        with timer.track("fusion"):
            final_results = fuse(bm25_results, dense_results)

        print(timer.get_times())  # {'bm25': 10.5, 'dense': 25.3, 'fusion': 5.2}
    """

    def __init__(self):
        self.times: Dict[str, float] = {}
        self._current_component: Optional[str] = None
        self._start_time: float = 0.0

    def track(self, component: str) -> "_ComponentTimerContext":
        """
        Track a component's execution time.

        Args:
            component: Component name

        Returns:
            Context manager for timing
        """
        return _ComponentTimerContext(self, component)

    def get_times(self) -> Dict[str, float]:
        """Get all component times."""
        return self.times.copy()

    def _start(self, component: str) -> None:
        self._current_component = component
        self._start_time = time.perf_counter()

    def _stop(self) -> None:
        if self._current_component:
            elapsed = (time.perf_counter() - self._start_time) * 1000
            self.times[self._current_component] = (
                self.times.get(self._current_component, 0.0) + elapsed
            )
        self._current_component = None


class _ComponentTimerContext:
    """Context manager for component timing."""

    def __init__(self, timer: ComponentTimer, component: str):
        self.timer = timer
        self.component = component

    def __enter__(self) -> "_ComponentTimerContext":
        self.timer._start(self.component)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.timer._stop()
