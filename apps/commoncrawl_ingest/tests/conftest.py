"""
Pytest fixtures for Common Crawl ingestion tests.

Provides sample WAT content, mock storage, and common test utilities.
"""

from __future__ import annotations

import gzip
import json
import uuid
from dataclasses import dataclass, field
from typing import Any

import pytest


@pytest.fixture
def sample_wat_paths() -> list[str]:
    """Sample WAT file paths from a Common Crawl snapshot."""
    return [
        "crawl-data/CC-MAIN-2024-10/segments/1707947473000.0/wat/CC-MAIN-20240209-00000.warc.wat.gz",
        "crawl-data/CC-MAIN-2024-10/segments/1707947473000.0/wat/CC-MAIN-20240209-00001.warc.wat.gz",
        "crawl-data/CC-MAIN-2024-10/segments/1707947473000.0/wat/CC-MAIN-20240209-00002.warc.wat.gz",
    ]


@pytest.fixture
def sample_wat_paths_gzipped(sample_wat_paths: list[str]) -> bytes:
    """Gzipped WAT paths content as would be returned from S3."""
    content = "\n".join(sample_wat_paths)
    return gzip.compress(content.encode("utf-8"))


@pytest.fixture
def sample_wat_record() -> dict[str, Any]:
    """Sample WAT record JSON structure with links."""
    return {
        "Envelope": {
            "WARC-Header-Metadata": {
                "WARC-Type": "metadata",
                "WARC-Target-URI": "https://source-site.com/page",
                "WARC-Date": "2024-02-09T12:00:00Z",
            },
            "Payload-Metadata": {
                "HTTP-Response-Metadata": {
                    "Headers": {
                        "Content-Type": "text/html; charset=utf-8",
                    },
                    "HTML-Metadata": {
                        "Head": {
                            "Title": "Source Page Title",
                        },
                        "Links": [
                            {
                                "url": "https://target-site.com/page1",
                                "path": "A@/href",
                                "text": "Link to Target 1",
                            },
                            {
                                "url": "https://target-site.com/page2#section",
                                "path": "A@/href",
                                "text": "Link to Target 2",
                                "rel": "nofollow",
                            },
                            {
                                "url": "https://another-site.com/",
                                "path": "A@/href",
                                "text": "External Link",
                                "rel": "sponsored ugc",
                            },
                            {
                                "url": "/internal/page",
                                "path": "A@/href",
                                "text": "Internal Link",
                            },
                        ],
                    },
                },
            },
        },
    }


@pytest.fixture
def sample_wat_content(sample_wat_record: dict[str, Any]) -> bytes:
    """Sample WAT file content (multiple WARC records)."""
    # WAT files contain WARC headers followed by JSON metadata
    warc_header = (
        "WARC/1.0\r\n"
        "WARC-Type: metadata\r\n"
        "WARC-Date: 2024-02-09T12:00:00Z\r\n"
        "WARC-Target-URI: https://source-site.com/page\r\n"
        "WARC-Record-ID: <urn:uuid:12345678-1234-1234-1234-123456789abc>\r\n"
        "Content-Type: application/json\r\n"
        f"Content-Length: {len(json.dumps(sample_wat_record))}\r\n"
        "\r\n"
    )
    record = warc_header + json.dumps(sample_wat_record) + "\r\n\r\n"
    return record.encode("utf-8")


@pytest.fixture
def sample_wat_content_gzipped(sample_wat_content: bytes) -> bytes:
    """Gzipped WAT content as would be returned from S3."""
    return gzip.compress(sample_wat_content)


@pytest.fixture
def sample_snapshot_id() -> str:
    """Sample Common Crawl snapshot ID."""
    return "CC-MAIN-2024-10"


@dataclass
class MockEdgeStorage:
    """Mock storage for edges during testing."""

    edges: list[Any] = field(default_factory=list)
    batch_size: int = 1000
    insert_count: int = 0

    async def insert_edges(self, edges: list[Any]) -> int:
        """Insert edges into storage."""
        self.edges.extend(edges)
        self.insert_count += 1
        return len(edges)

    async def get_edge_count(self) -> int:
        """Get total edge count."""
        return len(self.edges)


@pytest.fixture
def mock_edge_storage() -> MockEdgeStorage:
    """Create mock edge storage for testing."""
    return MockEdgeStorage()


@pytest.fixture
def sample_project_id() -> uuid.UUID:
    """Sample project ID for testing."""
    return uuid.uuid4()


# =============================================================================
# Aggregate testing fixtures
# =============================================================================


@pytest.fixture
def sample_target_domain() -> str:
    """Create a sample target domain for testing."""
    return "example.com"


@pytest.fixture
def sample_edges_for_aggregation(
    sample_snapshot_id: str, sample_target_domain: str
) -> list[dict[str, Any]]:
    """
    Create sample edge data for testing aggregations.

    Creates 5 edges from 4 different source domains:
    - source1.com: 2 edges (should have backlink_count=2)
    - source2.com: 1 edge
    - source3.com: 1 edge (empty anchor)
    - source4.com: 1 edge (null anchor)

    Returns:
        List of edge records simulating commoncrawl_edges table data.
    """
    from datetime import UTC, datetime

    base_time = datetime(2024, 3, 15, 12, 0, 0, tzinfo=UTC)
    return [
        {
            "id": uuid.uuid4(),
            "snapshot_id": sample_snapshot_id,
            "source_url": "https://blog.source1.com/article1",
            "source_domain": "source1.com",
            "target_url": f"https://{sample_target_domain}/page1",
            "target_domain": sample_target_domain,
            "anchor": "Example Link",
            "discovered_at": base_time,
        },
        {
            "id": uuid.uuid4(),
            "snapshot_id": sample_snapshot_id,
            "source_url": "https://www.source1.com/page2",
            "source_domain": "source1.com",
            "target_url": f"https://{sample_target_domain}/page2",
            "target_domain": sample_target_domain,
            "anchor": "  Example Link  ",  # Has whitespace to test trimming
            "discovered_at": datetime(2024, 3, 10, 8, 0, 0, tzinfo=UTC),
        },
        {
            "id": uuid.uuid4(),
            "snapshot_id": sample_snapshot_id,
            "source_url": "https://source2.com/links",
            "source_domain": "source2.com",
            "target_url": f"https://{sample_target_domain}/page1",
            "target_domain": sample_target_domain,
            "anchor": "Another Anchor",
            "discovered_at": base_time,
        },
        {
            "id": uuid.uuid4(),
            "snapshot_id": sample_snapshot_id,
            "source_url": "https://source3.com/blog",
            "source_domain": "source3.com",
            "target_url": f"https://{sample_target_domain}/page3",
            "target_domain": sample_target_domain,
            "anchor": "",  # Empty anchor - should be skipped in anchor aggregation
            "discovered_at": base_time,
        },
        {
            "id": uuid.uuid4(),
            "snapshot_id": sample_snapshot_id,
            "source_url": "https://source4.com/page",
            "source_domain": "source4.com",
            "target_url": f"https://{sample_target_domain}/page4",
            "target_domain": sample_target_domain,
            "anchor": None,  # Null anchor - should be skipped in anchor aggregation
            "discovered_at": base_time,
        },
    ]


@pytest.fixture
def sample_snapshot_record(sample_snapshot_id: str) -> dict[str, Any]:
    """
    Create sample snapshot metadata for testing.

    Returns:
        Dictionary representing a commoncrawl_snapshot record.
    """
    from datetime import UTC, datetime

    return {
        "id": uuid.uuid4(),
        "snapshot_id": sample_snapshot_id,
        "status": "ingested",
        "ingested_at": datetime.now(UTC),
        "edges_count": 5,
        "refdomains_count": None,
        "anchors_count": None,
        "aggregates_built_at": None,
    }


@pytest.fixture
def mock_db_session() -> Any:
    """
    Create a mock database session for isolated testing.

    Returns:
        AsyncMock configured as a database session.
    """
    from unittest.mock import AsyncMock, MagicMock

    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.close = AsyncMock()
    session.flush = AsyncMock()
    return session
