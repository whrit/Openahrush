"""
Query logging utilities for development and performance monitoring.

Provides:
- Query logging for development debugging
- Slow query detection with configurable thresholds
- N+1 query pattern detection
- Query pattern normalization for analysis

Usage:
    from semrush_core.db_utils.query_log import QueryLogger, create_query_logger

    # Create logger from environment
    logger = create_query_logger()

    # Log a query with timing
    async with logger.timed_query("SELECT * FROM users WHERE id = $1"):
        result = await session.execute(query)

    # Or manually log
    logger.log_query("SELECT * FROM users", duration_ms=5.2)
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

# Logger for query output
_query_logger = logging.getLogger("semrush.database.queries")


@dataclass
class QueryLogger:
    """
    Logger for database queries with slow query detection.

    Attributes:
        enabled: Whether query logging is enabled.
        slow_query_threshold_ms: Queries slower than this are flagged.
        log_level: Logging level for normal queries.
    """

    enabled: bool = False
    slow_query_threshold_ms: float = 100.0
    log_level: int = logging.DEBUG

    def log_query(self, query: str, duration_ms: float) -> None:
        """
        Log a query execution.

        Args:
            query: SQL query string.
            duration_ms: Query execution time in milliseconds.
        """
        if not self.enabled:
            return

        # Truncate very long queries for readability
        display_query = query[:500] + "..." if len(query) > 500 else query

        if duration_ms > self.slow_query_threshold_ms:
            _query_logger.warning(
                "[SLOW QUERY] %.2fms: %s",
                duration_ms,
                display_query,
            )
        else:
            _query_logger.log(
                self.log_level,
                "[QUERY] %.2fms: %s",
                duration_ms,
                display_query,
            )

    @asynccontextmanager
    async def timed_query(self, query: str) -> AsyncGenerator[None, None]:
        """
        Context manager to time and log a query execution.

        Args:
            query: SQL query string to log.

        Yields:
            None. The query execution should happen within the context.

        Example:
            async with logger.timed_query("SELECT * FROM users"):
                result = await session.execute(stmt)
        """
        start_time = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self.log_query(query, elapsed_ms)


@dataclass
class SlowQueryDetector:
    """
    Tracks query performance and detects slow queries.

    Useful for monitoring query performance in development and testing.

    Attributes:
        threshold_ms: Queries slower than this are considered slow.
    """

    threshold_ms: float = 100.0
    _slow_count: int = field(default=0, init=False)
    _total_count: int = field(default=0, init=False)
    _total_time_ms: float = field(default=0.0, init=False)

    def is_slow(self, duration_ms: float) -> bool:
        """
        Check if a query duration exceeds the slow threshold.

        Args:
            duration_ms: Query execution time in milliseconds.

        Returns:
            True if the query is considered slow.
        """
        return duration_ms > self.threshold_ms

    def record_query(self, duration_ms: float) -> None:
        """
        Record a query execution for statistics.

        Args:
            duration_ms: Query execution time in milliseconds.
        """
        self._total_count += 1
        self._total_time_ms += duration_ms
        if self.is_slow(duration_ms):
            self._slow_count += 1

    @property
    def slow_query_count(self) -> int:
        """Number of slow queries recorded."""
        return self._slow_count

    @property
    def total_query_count(self) -> int:
        """Total number of queries recorded."""
        return self._total_count

    @property
    def total_time_ms(self) -> float:
        """Total time spent in queries (milliseconds)."""
        return self._total_time_ms

    @property
    def average_time_ms(self) -> float:
        """Average query time (milliseconds)."""
        if self._total_count == 0:
            return 0.0
        return self._total_time_ms / self._total_count

    def reset(self) -> None:
        """Reset all statistics."""
        self._slow_count = 0
        self._total_count = 0
        self._total_time_ms = 0.0


@dataclass
class N1QueryDetector:
    """
    Detects potential N+1 query patterns.

    N+1 queries occur when:
    1. A query fetches N parent records
    2. Then N separate queries fetch related child records

    This detector identifies when similar query patterns are executed
    repeatedly, which is a common sign of N+1 issues.

    Attributes:
        threshold: Number of similar queries before triggering a warning.
    """

    threshold: int = 5
    _pattern_counts: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _pattern_examples: dict[str, str] = field(default_factory=dict)

    def record_query(self, query: str) -> None:
        """
        Record a query and check for N+1 patterns.

        Args:
            query: SQL query string.
        """
        pattern = normalize_query_pattern(query)
        self._pattern_counts[pattern] += 1
        if pattern not in self._pattern_examples:
            self._pattern_examples[pattern] = query

    def get_warnings(self) -> list[str]:
        """
        Get warnings for detected N+1 patterns.

        Returns:
            List of warning messages for patterns that exceed the threshold.
        """
        warnings = []
        for pattern, count in self._pattern_counts.items():
            if count > self.threshold:
                example = self._pattern_examples.get(pattern, pattern)
                warnings.append(
                    f"Potential N+1 query detected: Pattern executed {count} times. "
                    f"Example: {example[:200]}"
                )
        return warnings

    def reset(self) -> None:
        """Reset all recorded patterns."""
        self._pattern_counts.clear()
        self._pattern_examples.clear()


# Regex patterns for query normalization
_UUID_PATTERN = re.compile(
    r"'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'",
    re.IGNORECASE,
)
_STRING_LITERAL_PATTERN = re.compile(r"'[^']*'")
_NUMERIC_PATTERN = re.compile(r"\b\d+\b")
_PARAM_PLACEHOLDER_PATTERN = re.compile(r"\$\d+")


def normalize_query_pattern(query: str) -> str:
    """
    Normalize a query to a pattern for comparison.

    Replaces:
    - UUIDs with <UUID>
    - String literals with ?
    - Numeric literals with ?
    - Parameter placeholders with ?

    This allows detecting when the same query pattern is executed
    with different parameter values.

    Args:
        query: SQL query string.

    Returns:
        Normalized query pattern.

    Example:
        >>> normalize_query_pattern("SELECT * FROM users WHERE id = '550e8400-...'")
        "SELECT * FROM users WHERE id = ?"
    """
    # Normalize in a specific order to handle edge cases
    result = query

    # Replace UUIDs first (before general string literals)
    result = _UUID_PATTERN.sub("?", result)

    # Replace remaining string literals
    result = _STRING_LITERAL_PATTERN.sub("?", result)

    # Replace numeric literals
    result = _NUMERIC_PATTERN.sub("?", result)

    # Replace parameter placeholders ($1, $2, etc.)
    result = _PARAM_PLACEHOLDER_PATTERN.sub("?", result)

    # Normalize whitespace
    result = " ".join(result.split())

    return result


def create_query_logger() -> QueryLogger:
    """
    Create a QueryLogger configured from environment variables.

    Environment variables:
        QUERY_LOG_ENABLED: "true" to enable (default: false)
        QUERY_LOG_SLOW_THRESHOLD_MS: Slow query threshold (default: 100)
        QUERY_LOG_LEVEL: Logging level (default: DEBUG)

    Returns:
        Configured QueryLogger instance.
    """
    enabled = os.getenv("QUERY_LOG_ENABLED", "").lower() in ("true", "1", "yes")
    threshold = float(os.getenv("QUERY_LOG_SLOW_THRESHOLD_MS", "100"))
    log_level_str = os.getenv("QUERY_LOG_LEVEL", "DEBUG").upper()
    log_level = getattr(logging, log_level_str, logging.DEBUG)

    return QueryLogger(
        enabled=enabled,
        slow_query_threshold_ms=threshold,
        log_level=log_level,
    )


def setup_query_logging(enabled: bool = True, slow_threshold_ms: float = 100.0) -> None:
    """
    Configure the query logging handler.

    Sets up a handler for the semrush.database.queries logger.

    Args:
        enabled: Whether to enable query logging.
        slow_threshold_ms: Threshold for slow query warnings.
    """
    if not enabled:
        return

    # Configure the query logger
    _query_logger.setLevel(logging.DEBUG)

    # Add a handler if none exists
    if not _query_logger.handlers:
        handler = logging.StreamHandler()
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        handler.setFormatter(formatter)
        _query_logger.addHandler(handler)


@dataclass
class QueryStats:
    """
    Aggregated query statistics for performance analysis.
    """

    total_queries: int = 0
    total_time_ms: float = 0.0
    slow_queries: int = 0
    queries_by_pattern: dict[str, int] = field(default_factory=lambda: defaultdict(int))

    def record(
        self,
        query: str,
        duration_ms: float,
        slow_threshold_ms: float = 100.0,
    ) -> None:
        """Record a query execution."""
        self.total_queries += 1
        self.total_time_ms += duration_ms
        if duration_ms > slow_threshold_ms:
            self.slow_queries += 1

        pattern = normalize_query_pattern(query)
        self.queries_by_pattern[pattern] += 1

    def get_summary(self) -> dict[str, float | int]:
        """Get a summary of query statistics."""
        return {
            "total_queries": self.total_queries,
            "total_time_ms": self.total_time_ms,
            "average_time_ms": self.total_time_ms / max(1, self.total_queries),
            "slow_queries": self.slow_queries,
            "unique_patterns": len(self.queries_by_pattern),
        }
