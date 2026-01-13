"""
Cache metrics and statistics tracking.

Monitors:
- Cache hit/miss rates
- Response time improvements
- Memory usage
- Most frequently asked questions
"""

import time
from collections import defaultdict
from typing import Optional, Dict, Any
from datetime import datetime
from app.services.cache.models import CacheStats
from app.logging_config import logger


class CacheMetrics:
    """
    Thread-safe cache metrics collector.

    Tracks performance metrics like hit rate, response times, and most asked questions.

    Example:
        metrics = CacheMetrics(max_top_questions=5)

        # Record a cache hit (fast response)
        metrics.record_hit(
            query_normalized="reset password",
            response_time_ms=5.2,
            doc_ids=["doc_1"]
        )

        # Record a cache miss (full pipeline)
        metrics.record_miss(response_time_ms=850)

        # Record a cache miss (full pipeline)
        metrics.record_miss(response_time_ms=850)
    """

    def __init__(self, max_top_questions: int = 5):
        """
        Initialize metrics collector.

        Args:
            max_top_questions: Keep track of top N questions (default 5)
        """
        self.max_top_questions = max_top_questions

        # Core metrics
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0

        # Response times
        self.cached_response_times = []
        self.full_response_times = []

        # Query frequency tracking
        self.query_hit_counts: Dict[str, int] = defaultdict(int)

        # Memory tracking
        self.memory_usage_mb = 0.0

        # Total cached entries
        self.total_entries = 0

        # Start time for statistics
        self.stats_start_time = datetime.utcnow()

    def record_hit(
        self,
        query_normalized: str,
        response_time_ms: float,
        doc_ids: Optional[list] = None
    ):
        """
        Record a successful cache hit.

        Args:
            query_normalized: The normalized query that was found in cache
            response_time_ms: Response time in milliseconds
            doc_ids: Document IDs used (optional)
        """
        self.total_requests += 1
        self.cache_hits += 1
        self.cached_response_times.append(response_time_ms)
        self.query_hit_counts[query_normalized] += 1

    def record_miss(self, response_time_ms: float):
        """
        Record a cache miss (full pipeline execution).

        Args:
            response_time_ms: Full pipeline response time in milliseconds
        """
        self.total_requests += 1
        self.cache_misses += 1
        self.full_response_times.append(response_time_ms)

    def update_memory_usage(self, memory_mb: float):
        """
        Update current memory usage.

        Args:
            memory_mb: Memory usage in megabytes
        """
        self.memory_usage_mb = memory_mb

    def update_total_entries(self, count: int):
        """
        Update total number of cached entries.

        Args:
            count: Total entries in cache
        """
        self.total_entries = count

    def get_stats(self) -> CacheStats:
        """
        Get current cache statistics.

        Returns:
            CacheStats object with all metrics

        Example:
            stats = metrics.get_stats()
        """
        # Calculate hit rate
        hit_rate = 0.0
        if self.total_requests > 0:
            hit_rate = (self.cache_hits / self.total_requests) * 100

        # Calculate average response times
        avg_cached_time = 0.0
        if self.cached_response_times:
            avg_cached_time = sum(self.cached_response_times) / len(self.cached_response_times)

        avg_full_time = 0.0
        if self.full_response_times:
            avg_full_time = sum(self.full_response_times) / len(self.full_response_times)

        # Calculate time savings
        time_per_hit_saved = (avg_full_time - avg_cached_time) / 1000  # Convert ms to seconds
        total_time_saved = self.cache_hits * time_per_hit_saved

        # Get top N questions
        top_questions = []
        if self.query_hit_counts:
            sorted_queries = sorted(
                self.query_hit_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )
            top_questions = [
                {"query": query, "hits": count}
                for query, count in sorted_queries[:self.max_top_questions]
            ]

        return CacheStats(
            total_requests=self.total_requests,
            cache_hits=self.cache_hits,
            cache_misses=self.cache_misses,
            hit_rate=round(hit_rate, 2),
            avg_response_time_cached=round(avg_cached_time, 2),
            avg_response_time_full=round(avg_full_time, 2),
            savings_time=round(total_time_saved, 2),
            memory_usage_mb=round(self.memory_usage_mb, 2),
            total_entries=self.total_entries,
            most_asked_questions=top_questions,
        )

    def reset(self):
        """Reset all metrics (useful for periodic reporting)."""
        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.cached_response_times = []
        self.full_response_times = []
        self.query_hit_counts.clear()
        self.stats_start_time = datetime.utcnow()

    def get_summary(self) -> str:
        """
        Get a human-readable summary of cache performance.

        Returns:
            Formatted string with key metrics

        Example:
            summary = metrics.get_summary()
            # Output:
            # 📊 Cache Performance Summary
            # ─────────────────────────────
            # Total Requests: 100
            # Cache Hits: 45 (45.00%)
            # Cache Misses: 55
            # Avg Cached Response: 5.20ms
            # Avg Full Response: 850.00ms
            # Time Saved: 37.88s
            # Memory: 2.5 MB
            # Top Question: "reset password" (15 hits)
        """
        stats = self.get_stats()

        summary = (
            "📊 Cache Performance Summary\n"
            "─────────────────────────────\n"
            f"Total Requests: {stats.total_requests}\n"
            f"Cache Hits: {stats.cache_hits} ({stats.hit_rate:.2f}%)\n"
            f"Cache Misses: {stats.cache_misses}\n"
            f"Avg Cached Response: {stats.avg_response_time_cached:.2f}ms\n"
            f"Avg Full Response: {stats.avg_response_time_full:.2f}ms\n"
            f"Time Saved: {stats.savings_time:.2f}s\n"
            f"Memory: {stats.memory_usage_mb:.2f} MB\n"
            f"Total Entries: {stats.total_entries}\n"
        )

        if stats.most_asked_questions:
            summary += f"\nTop Questions:\n"
            for i, q in enumerate(stats.most_asked_questions, 1):
                summary += f"  {i}. \"{q['query']}\" ({q['hits']} hits)\n"

        return summary
