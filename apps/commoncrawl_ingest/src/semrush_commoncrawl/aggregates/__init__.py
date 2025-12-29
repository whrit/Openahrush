"""
Aggregate materialization for Common Crawl data.

This module provides background jobs to build aggregate tables
from raw edges after ingestion completes.

Aggregates built:
- Referring domains (refdomains): Groups edges by (target_domain, source_domain)
  to count backlinks per referring domain with first/last seen tracking.
- Anchor text distribution: Groups edges by (target_domain, anchor) to count
  occurrences of each anchor text.

Usage:
    from semrush_commoncrawl.aggregates import AggregateBuilder, AggregateResult

    builder = AggregateBuilder(db_session)
    result = await builder.build_all("CC-MAIN-2024-10")
    print(f"Built {result.refdomains_count} refdomains, {result.anchors_count} anchors")
"""

from semrush_commoncrawl.aggregates.anchors import AnchorsAggregator
from semrush_commoncrawl.aggregates.builder import AggregateBuilder, AggregateResult
from semrush_commoncrawl.aggregates.refdomains import RefDomainsAggregator

__all__ = [
    "AggregateBuilder",
    "AggregateResult",
    "AnchorsAggregator",
    "RefDomainsAggregator",
]
