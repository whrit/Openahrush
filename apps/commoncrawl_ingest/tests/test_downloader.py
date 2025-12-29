"""
TDD tests for the WAT file downloader.

Tests cover:
- Fetching WAT paths from S3
- Streaming WAT file downloads
- Handling gzip decompression
- Error handling for network failures
"""

from __future__ import annotations

import gzip
from typing import TYPE_CHECKING

import httpx
import pytest
import respx

if TYPE_CHECKING:
    pass


# ============================================================================
# Tests for fetch_wat_paths
# ============================================================================


class TestFetchWatPaths:
    """Tests for fetching WAT file paths from Common Crawl S3."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_wat_paths_returns_list_of_paths(
        self,
        sample_wat_paths: list[str],
        sample_wat_paths_gzipped: bytes,
        sample_snapshot_id: str,
    ) -> None:
        """fetch_wat_paths should return a list of WAT file paths."""
        from semrush_commoncrawl.downloader import fetch_wat_paths

        # Mock the wat.paths.gz endpoint
        url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(url).mock(return_value=httpx.Response(200, content=sample_wat_paths_gzipped))

        paths = await fetch_wat_paths(sample_snapshot_id)

        assert paths == sample_wat_paths
        assert len(paths) == 3
        assert all(path.endswith(".warc.wat.gz") for path in paths)

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_wat_paths_handles_empty_response(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """fetch_wat_paths should return empty list for empty response."""
        from semrush_commoncrawl.downloader import fetch_wat_paths

        url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        empty_gzipped = gzip.compress(b"")
        respx.get(url).mock(return_value=httpx.Response(200, content=empty_gzipped))

        paths = await fetch_wat_paths(sample_snapshot_id)

        assert paths == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_wat_paths_raises_on_http_error(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """fetch_wat_paths should raise on HTTP errors."""
        from semrush_commoncrawl.downloader import DownloadError, fetch_wat_paths

        url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(url).mock(return_value=httpx.Response(404))

        with pytest.raises(DownloadError, match="Failed to fetch WAT paths"):
            await fetch_wat_paths(sample_snapshot_id)

    @pytest.mark.asyncio
    @respx.mock
    async def test_fetch_wat_paths_filters_empty_lines(
        self,
        sample_snapshot_id: str,
    ) -> None:
        """fetch_wat_paths should filter out empty lines."""
        from semrush_commoncrawl.downloader import fetch_wat_paths

        content = "path1.warc.wat.gz\n\npath2.warc.wat.gz\n\n\n"
        gzipped = gzip.compress(content.encode("utf-8"))

        url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(url).mock(return_value=httpx.Response(200, content=gzipped))

        paths = await fetch_wat_paths(sample_snapshot_id)

        assert paths == ["path1.warc.wat.gz", "path2.warc.wat.gz"]


# ============================================================================
# Tests for download_wat_file
# ============================================================================


class TestDownloadWatFile:
    """Tests for streaming WAT file downloads."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_wat_file_streams_content(
        self,
        sample_wat_content: bytes,
        sample_wat_content_gzipped: bytes,
    ) -> None:
        """download_wat_file should stream decompressed content."""
        from semrush_commoncrawl.downloader import download_wat_file

        path = "crawl-data/CC-MAIN-2024-10/segments/123/wat/file.warc.wat.gz"
        url = f"https://data.commoncrawl.org/{path}"
        respx.get(url).mock(return_value=httpx.Response(200, content=sample_wat_content_gzipped))

        chunks: list[bytes] = []
        async for chunk in download_wat_file(path):
            chunks.append(chunk)

        # Combine chunks and verify content matches
        content = b"".join(chunks)
        assert sample_wat_content in content or content == sample_wat_content

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_wat_file_handles_large_files(self) -> None:
        """download_wat_file should handle large files by streaming."""
        from semrush_commoncrawl.downloader import download_wat_file

        # Create a large content (simulated)
        large_content = b"x" * 10000
        gzipped = gzip.compress(large_content)

        path = "crawl-data/CC-MAIN-2024-10/segments/123/wat/large.warc.wat.gz"
        url = f"https://data.commoncrawl.org/{path}"
        respx.get(url).mock(return_value=httpx.Response(200, content=gzipped))

        chunks: list[bytes] = []
        async for chunk in download_wat_file(path):
            chunks.append(chunk)

        content = b"".join(chunks)
        assert content == large_content

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_wat_file_raises_on_http_error(self) -> None:
        """download_wat_file should raise on HTTP errors."""
        from semrush_commoncrawl.downloader import DownloadError, download_wat_file

        path = "crawl-data/CC-MAIN-2024-10/segments/123/wat/missing.warc.wat.gz"
        url = f"https://data.commoncrawl.org/{path}"
        respx.get(url).mock(return_value=httpx.Response(404))

        with pytest.raises(DownloadError, match="Failed to download WAT file"):
            async for _ in download_wat_file(path):
                pass

    @pytest.mark.asyncio
    @respx.mock
    async def test_download_wat_file_uses_base_url(self) -> None:
        """download_wat_file should use configurable base URL."""
        from semrush_commoncrawl.downloader import download_wat_file

        content = gzip.compress(b"test content")
        path = "crawl-data/test.warc.wat.gz"
        custom_base = "https://custom-mirror.example.com/"
        url = f"{custom_base}{path}"
        respx.get(url).mock(return_value=httpx.Response(200, content=content))

        chunks: list[bytes] = []
        async for chunk in download_wat_file(path, base_url=custom_base):
            chunks.append(chunk)

        assert b"".join(chunks) == b"test content"


# ============================================================================
# Tests for WatDownloader class (if implemented)
# ============================================================================


class TestWatDownloader:
    """Tests for the WatDownloader class with concurrent downloads."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_downloader_respects_concurrency_limit(
        self,
        sample_wat_paths: list[str],
        sample_wat_paths_gzipped: bytes,
        sample_wat_content_gzipped: bytes,
        sample_snapshot_id: str,
    ) -> None:
        """WatDownloader should respect concurrency limits."""
        from semrush_commoncrawl.downloader import WatDownloader

        # Mock paths endpoint
        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(
            return_value=httpx.Response(200, content=sample_wat_paths_gzipped)
        )

        # Mock file downloads
        for path in sample_wat_paths:
            url = f"https://data.commoncrawl.org/{path}"
            respx.get(url).mock(
                return_value=httpx.Response(200, content=sample_wat_content_gzipped)
            )

        downloader = WatDownloader(concurrency=2)
        files_processed = 0

        async for path, _content in downloader.download_all(sample_snapshot_id, limit=3):
            files_processed += 1
            assert path in sample_wat_paths

        assert files_processed == 3

    @pytest.mark.asyncio
    @respx.mock
    async def test_downloader_handles_partial_failures(
        self,
        sample_wat_paths_gzipped: bytes,
        sample_wat_content_gzipped: bytes,
        sample_snapshot_id: str,
    ) -> None:
        """WatDownloader should continue on partial failures."""
        from semrush_commoncrawl.downloader import WatDownloader

        paths = [
            "crawl-data/CC-MAIN-2024-10/good.warc.wat.gz",
            "crawl-data/CC-MAIN-2024-10/bad.warc.wat.gz",
            "crawl-data/CC-MAIN-2024-10/good2.warc.wat.gz",
        ]
        paths_content = gzip.compress("\n".join(paths).encode("utf-8"))

        # Mock paths endpoint
        paths_url = f"https://data.commoncrawl.org/crawl-data/{sample_snapshot_id}/wat.paths.gz"
        respx.get(paths_url).mock(return_value=httpx.Response(200, content=paths_content))

        # Mock file downloads - one fails
        respx.get("https://data.commoncrawl.org/" + paths[0]).mock(
            return_value=httpx.Response(200, content=sample_wat_content_gzipped)
        )
        respx.get("https://data.commoncrawl.org/" + paths[1]).mock(
            return_value=httpx.Response(500)  # This one fails
        )
        respx.get("https://data.commoncrawl.org/" + paths[2]).mock(
            return_value=httpx.Response(200, content=sample_wat_content_gzipped)
        )

        downloader = WatDownloader(concurrency=1, skip_errors=True)
        successful_paths: list[str] = []

        async for path, _ in downloader.download_all(sample_snapshot_id):
            successful_paths.append(path)

        # Should have processed 2 out of 3 (skipping the failed one)
        assert len(successful_paths) == 2
        assert paths[1] not in successful_paths
