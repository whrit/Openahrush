"""
TDD tests for the ingestion orchestrator.

Tests cover:
- IngestionOrchestrator class
- IngestSpec and IngestionResult dataclasses
- Coordination of download -> parse -> filter -> store
- Progress tracking
- Error handling
"""

from __future__ import annotations

import gzip
import json
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

import httpx
import pytest
import respx

if TYPE_CHECKING:
    pass


# ============================================================================
# Tests for IngestSpec dataclass
# ============================================================================


class TestIngestSpec:
    """Tests for the IngestSpec configuration dataclass."""

    def test_ingest_spec_has_required_fields(self) -> None:
        """IngestSpec should have target_domains, sample_rate, max_edges, max_files."""
        from semrush_commoncrawl.orchestrator import IngestSpec

        spec = IngestSpec(
            target_domains=["example.com"],
            sample_rate=0.5,
            max_edges=1000,
            max_files=10,
        )

        assert spec.target_domains == ["example.com"]
        assert spec.sample_rate == 0.5
        assert spec.max_edges == 1000
        assert spec.max_files == 10

    def test_ingest_spec_has_sensible_defaults(self) -> None:
        """IngestSpec should have sensible defaults."""
        from semrush_commoncrawl.orchestrator import IngestSpec

        spec = IngestSpec()

        assert spec.target_domains is None  # No domain filtering by default
        assert spec.sample_rate == 1.0  # No sampling by default
        assert spec.max_edges is None  # No edge limit by default
        assert spec.max_files is None  # No file limit by default

    def test_ingest_spec_validates_sample_rate(self) -> None:
        """IngestSpec should validate sample_rate is between 0 and 1."""
        from semrush_commoncrawl.orchestrator import IngestSpec

        with pytest.raises(ValueError):
            IngestSpec(sample_rate=1.5)

        with pytest.raises(ValueError):
            IngestSpec(sample_rate=-0.1)


# ============================================================================
# Tests for IngestionResult dataclass
# ============================================================================


class TestIngestionResult:
    """Tests for the IngestionResult dataclass."""

    def test_ingestion_result_has_required_fields(self) -> None:
        """IngestionResult should have edges_ingested, files_processed, errors."""
        from semrush_commoncrawl.orchestrator import IngestionResult

        result = IngestionResult(
            edges_ingested=1000,
            files_processed=5,
            errors=["Error 1", "Error 2"],
        )

        assert result.edges_ingested == 1000
        assert result.files_processed == 5
        assert result.errors == ["Error 1", "Error 2"]

    def test_ingestion_result_has_default_empty_errors(self) -> None:
        """IngestionResult should default to empty errors list."""
        from semrush_commoncrawl.orchestrator import IngestionResult

        result = IngestionResult(edges_ingested=100, files_processed=1)

        assert result.errors == []

    def test_ingestion_result_has_success_property(self) -> None:
        """IngestionResult should have success property based on errors."""
        from semrush_commoncrawl.orchestrator import IngestionResult

        success_result = IngestionResult(edges_ingested=100, files_processed=1)
        assert success_result.success is True

        error_result = IngestionResult(
            edges_ingested=100, files_processed=1, errors=["Something went wrong"]
        )
        assert error_result.success is False


# ============================================================================
# Tests for IngestionOrchestrator initialization
# ============================================================================


class TestIngestionOrchestratorInit:
    """Tests for IngestionOrchestrator initialization."""

    def test_orchestrator_requires_storage(self) -> None:
        """IngestionOrchestrator should require a storage backend."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()

        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        assert orchestrator.storage is storage

    def test_orchestrator_accepts_settings(self) -> None:
        """IngestionOrchestrator should accept IngestionSettings."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings(batch_size=500, concurrency=4)

        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        assert orchestrator.settings.batch_size == 500
        assert orchestrator.settings.concurrency == 4


# ============================================================================
# Tests for IngestionOrchestrator.ingest_snapshot
# ============================================================================


class TestIngestionOrchestratorIngest:
    """Tests for the ingest_snapshot method."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_returns_result(
        self,
        sample_wat_paths: list[str],
        sample_wat_paths_gzipped: bytes,
        sample_wat_content_gzipped: bytes,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should return an IngestionResult."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionResult,
            IngestionSettings,
            IngestSpec,
        )

        # Mock HTTP requests
        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(
            return_value=httpx.Response(200, content=sample_wat_paths_gzipped)
        )

        for path in sample_wat_paths:
            url = f"https://data.commoncrawl.org/{path}"
            respx.get(url).mock(
                return_value=httpx.Response(200, content=sample_wat_content_gzipped)
            )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec(max_files=1)
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        assert isinstance(result, IngestionResult)
        assert result.files_processed >= 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_coordinates_components(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should coordinate download -> parse -> filter -> store."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        # Create WAT content with a known link
        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://source.com/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": [
                                {
                                    "url": "https://target.com/linked-page",
                                    "path": "A@/href",
                                    "text": "Click here",
                                },
                            ],
                        },
                    },
                },
            },
        }
        json_content = json.dumps(record)
        warc_content = (
            f"WARC/1.0\r\n"
            f"WARC-Type: metadata\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            f"\r\n"
            f"{json_content}\r\n\r\n"
        ).encode()
        gzipped_content = gzip.compress(warc_content)

        paths = ["crawl-data/test.warc.wat.gz"]
        paths_gzipped = gzip.compress("\n".join(paths).encode("utf-8"))

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_gzipped))
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=gzipped_content)
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec(target_domains=["target.com"])
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        # Should have stored edges
        assert result.edges_ingested >= 1
        assert len(storage.edges) >= 1

        # Verify edge content
        edge = storage.edges[0]
        assert edge.target_domain == "target.com"

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_respects_max_files(
        self,
        sample_wat_paths: list[str],
        sample_wat_paths_gzipped: bytes,
        sample_wat_content_gzipped: bytes,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should respect max_files limit."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(
            return_value=httpx.Response(200, content=sample_wat_paths_gzipped)
        )

        for path in sample_wat_paths:
            url = f"https://data.commoncrawl.org/{path}"
            respx.get(url).mock(
                return_value=httpx.Response(200, content=sample_wat_content_gzipped)
            )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec(max_files=2)  # Only process 2 files
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        assert result.files_processed == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_respects_max_edges(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should respect max_edges limit."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        # Create WAT content with many links
        links = [
            {
                "url": f"https://target{i}.com/page",
                "path": "A@/href",
                "text": f"Link {i}",
            }
            for i in range(100)
        ]
        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://source.com/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": links,
                        },
                    },
                },
            },
        }
        json_content = json.dumps(record)
        warc_content = (
            f"WARC/1.0\r\n"
            f"WARC-Type: metadata\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            f"\r\n"
            f"{json_content}\r\n\r\n"
        ).encode()
        gzipped_content = gzip.compress(warc_content)

        paths = ["crawl-data/test.warc.wat.gz"]
        paths_gzipped = gzip.compress("\n".join(paths).encode("utf-8"))

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_gzipped))
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=gzipped_content)
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec(max_edges=10)  # Only store 10 edges
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        assert result.edges_ingested == 10
        assert len(storage.edges) == 10

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_applies_domain_filter(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should apply domain filtering."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        # Create WAT content with mixed target domains
        links = [
            {"url": "https://target.com/page1", "path": "A@/href", "text": "Target 1"},
            {"url": "https://other.com/page1", "path": "A@/href", "text": "Other 1"},
            {"url": "https://target.com/page2", "path": "A@/href", "text": "Target 2"},
            {"url": "https://different.com/page1", "path": "A@/href", "text": "Different"},
        ]
        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://source.com/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": links,
                        },
                    },
                },
            },
        }
        json_content = json.dumps(record)
        warc_content = (
            f"WARC/1.0\r\n"
            f"WARC-Type: metadata\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            f"\r\n"
            f"{json_content}\r\n\r\n"
        ).encode()
        gzipped_content = gzip.compress(warc_content)

        paths = ["crawl-data/test.warc.wat.gz"]
        paths_gzipped = gzip.compress("\n".join(paths).encode("utf-8"))

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_gzipped))
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=gzipped_content)
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec(target_domains=["target.com"])
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        # Should only have edges targeting target.com
        assert result.edges_ingested == 2
        assert all(e.target_domain == "target.com" for e in storage.edges)


# ============================================================================
# Tests for progress tracking
# ============================================================================


class TestIngestionOrchestratorProgress:
    """Tests for progress tracking during ingestion."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_tracks_progress(
        self,
        sample_wat_paths: list[str],
        sample_wat_paths_gzipped: bytes,
        sample_wat_content_gzipped: bytes,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should track progress during processing."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(
            return_value=httpx.Response(200, content=sample_wat_paths_gzipped)
        )

        for path in sample_wat_paths:
            url = f"https://data.commoncrawl.org/{path}"
            respx.get(url).mock(
                return_value=httpx.Response(200, content=sample_wat_content_gzipped)
            )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        progress_updates: list[dict] = []

        def on_progress(update: dict) -> None:
            progress_updates.append(update)

        spec = IngestSpec(max_files=2)
        await orchestrator.ingest_snapshot(sample_snapshot_id, spec, on_progress=on_progress)

        # Should have received progress updates
        assert len(progress_updates) >= 2

    @pytest.mark.asyncio
    async def test_orchestrator_has_current_progress_property(self) -> None:
        """IngestionOrchestrator should expose current progress."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        progress = orchestrator.current_progress

        assert progress.files_processed == 0
        assert progress.edges_ingested == 0
        assert progress.is_running is False


# ============================================================================
# Tests for error handling
# ============================================================================


class TestIngestionOrchestratorErrorHandling:
    """Tests for error handling during ingestion."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_handles_download_errors(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should handle download errors gracefully."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        paths = [
            "crawl-data/good.warc.wat.gz",
            "crawl-data/bad.warc.wat.gz",
        ]
        paths_gzipped = gzip.compress("\n".join(paths).encode("utf-8"))

        # Create a valid WAT file
        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://source.com/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": [
                                {
                                    "url": "https://target.com/page",
                                    "path": "A@/href",
                                    "text": "Link",
                                },
                            ],
                        },
                    },
                },
            },
        }
        json_content = json.dumps(record)
        warc_content = (
            f"WARC/1.0\r\n"
            f"WARC-Type: metadata\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            f"\r\n"
            f"{json_content}\r\n\r\n"
        ).encode()
        good_content = gzip.compress(warc_content)

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_gzipped))
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=good_content)
        )
        respx.get("https://data.commoncrawl.org/" + paths[1]).mock(
            return_value=httpx.Response(500)  # This one fails
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec()
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        # Should have processed at least one file
        assert result.files_processed >= 1
        # Should have recorded the error
        assert len(result.errors) >= 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_handles_parse_errors(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should handle parse errors gracefully."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        paths = ["crawl-data/malformed.warc.wat.gz"]
        paths_gzipped = gzip.compress("\n".join(paths).encode("utf-8"))

        # Create malformed WAT content
        malformed_content = gzip.compress(b"{ invalid json content")

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_gzipped))
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=malformed_content)
        )

        storage = MockEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec()
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        # Should complete without raising
        assert result.files_processed == 1
        assert result.edges_ingested == 0

    @pytest.mark.asyncio
    @respx.mock
    async def test_ingest_snapshot_handles_storage_errors(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """ingest_snapshot should handle storage errors gracefully."""
        from semrush_commoncrawl.orchestrator import (
            IngestionOrchestrator,
            IngestionSettings,
            IngestSpec,
        )

        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://source.com/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": [
                                {
                                    "url": "https://target.com/page",
                                    "path": "A@/href",
                                    "text": "Link",
                                },
                            ],
                        },
                    },
                },
            },
        }
        json_content = json.dumps(record)
        warc_content = (
            f"WARC/1.0\r\n"
            f"WARC-Type: metadata\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            f"\r\n"
            f"{json_content}\r\n\r\n"
        ).encode()
        gzipped_content = gzip.compress(warc_content)

        paths = ["crawl-data/test.warc.wat.gz"]
        paths_gzipped = gzip.compress("\n".join(paths).encode("utf-8"))

        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_gzipped))
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=gzipped_content)
        )

        # Create failing storage
        storage = FailingEdgeStorage()
        settings = IngestionSettings()
        orchestrator = IngestionOrchestrator(storage=storage, settings=settings)

        spec = IngestSpec()
        result = await orchestrator.ingest_snapshot(sample_snapshot_id, spec)

        # Should complete but with errors
        assert len(result.errors) >= 1


# ============================================================================
# Mock implementations for testing
# ============================================================================


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


@dataclass
class FailingEdgeStorage:
    """Mock storage that fails on insert."""

    async def insert_edges(self, edges: list[Any]) -> int:
        """Fail to insert edges."""
        raise RuntimeError("Storage failure")

    async def get_edge_count(self) -> int:
        """Get edge count."""
        return 0
