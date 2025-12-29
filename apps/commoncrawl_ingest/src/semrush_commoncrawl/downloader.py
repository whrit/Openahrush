"""
WAT file downloader for Common Crawl ingestion.

Handles fetching WAT paths and streaming WAT file downloads from
Common Crawl's S3 bucket with gzip decompression support.
"""

from __future__ import annotations

import asyncio
import gzip
from collections.abc import AsyncIterator
from dataclasses import dataclass, field

import httpx

# Base URL for Common Crawl data
COMMONCRAWL_BASE_URL = "https://data.commoncrawl.org/"


class DownloadError(Exception):
    """Exception raised when a download operation fails."""

    pass


async def fetch_wat_paths(
    snapshot_id: str,
    *,
    base_url: str = COMMONCRAWL_BASE_URL,
    timeout: float = 60.0,
) -> list[str]:
    """
    Fetch the list of WAT file paths for a Common Crawl snapshot.

    Retrieves the wat.paths.gz file from Common Crawl's S3 bucket,
    decompresses it, and returns a list of WAT file paths.

    Args:
        snapshot_id: Common Crawl snapshot ID (e.g., "CC-MAIN-2024-10").
        base_url: Base URL for Common Crawl data.
        timeout: Request timeout in seconds.

    Returns:
        List of WAT file paths (relative to base_url).

    Raises:
        DownloadError: If the HTTP request fails.
    """
    url = f"{base_url}crawl-data/{snapshot_id}/wat.paths.gz"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DownloadError(
                f"Failed to fetch WAT paths for {snapshot_id}: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DownloadError(
                f"Failed to fetch WAT paths for {snapshot_id}: {e}"
            ) from e

    # Decompress and parse paths
    try:
        content = gzip.decompress(response.content)
        paths = content.decode("utf-8").strip().split("\n")
        # Filter out empty lines
        return [p.strip() for p in paths if p.strip()]
    except Exception as e:
        raise DownloadError(f"Failed to decompress WAT paths: {e}") from e


async def download_wat_file(
    path: str,
    *,
    base_url: str = COMMONCRAWL_BASE_URL,
    timeout: float = 300.0,
    chunk_size: int = 65536,
) -> AsyncIterator[bytes]:
    """
    Stream and decompress a WAT file from Common Crawl.

    Downloads a gzipped WAT file and yields decompressed content in chunks.

    Args:
        path: WAT file path relative to base_url.
        base_url: Base URL for Common Crawl data.
        timeout: Request timeout in seconds.
        chunk_size: Size of chunks to yield.

    Yields:
        Decompressed content chunks.

    Raises:
        DownloadError: If the HTTP request fails.
    """
    url = f"{base_url}{path}"

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            response = await client.get(url)
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise DownloadError(
                f"Failed to download WAT file {path}: HTTP {e.response.status_code}"
            ) from e
        except httpx.RequestError as e:
            raise DownloadError(f"Failed to download WAT file {path}: {e}") from e

    # Decompress the content
    try:
        decompressed = gzip.decompress(response.content)
    except Exception as e:
        raise DownloadError(f"Failed to decompress WAT file {path}: {e}") from e

    # Yield in chunks
    for i in range(0, len(decompressed), chunk_size):
        yield decompressed[i : i + chunk_size]


@dataclass
class WatDownloader:
    """
    Concurrent WAT file downloader with configurable concurrency.

    Provides a higher-level interface for downloading multiple WAT files
    with controlled concurrency and error handling.

    Attributes:
        concurrency: Maximum number of concurrent downloads.
        base_url: Base URL for Common Crawl data.
        timeout: Request timeout in seconds.
        skip_errors: Whether to continue on individual file download errors.
        errors: List of errors encountered during downloads (when skip_errors=True).
    """

    concurrency: int = 4
    base_url: str = COMMONCRAWL_BASE_URL
    timeout: float = 300.0
    skip_errors: bool = False
    errors: list[str] = field(default_factory=list)

    async def download_all(
        self,
        snapshot_id: str,
        limit: int | None = None,
    ) -> AsyncIterator[tuple[str, bytes]]:
        """
        Download all WAT files for a snapshot.

        Fetches the list of WAT paths and downloads them with controlled
        concurrency, yielding (path, content) tuples.

        Args:
            snapshot_id: Common Crawl snapshot ID.
            limit: Optional limit on number of files to download.

        Yields:
            Tuples of (path, decompressed_content).

        Raises:
            DownloadError: If fetching paths fails or if a file download
                fails and skip_errors is False.
        """
        # Fetch paths
        paths = await fetch_wat_paths(
            snapshot_id, base_url=self.base_url, timeout=self.timeout
        )

        if limit is not None:
            paths = paths[:limit]

        # Create semaphore for concurrency control
        semaphore = asyncio.Semaphore(self.concurrency)

        async def download_with_semaphore(
            path: str,
        ) -> tuple[str, bytes | None, Exception | None]:
            """Download a single file with semaphore."""
            async with semaphore:
                try:
                    chunks: list[bytes] = []
                    async for chunk in download_wat_file(
                        path, base_url=self.base_url, timeout=self.timeout
                    ):
                        chunks.append(chunk)
                    return (path, b"".join(chunks), None)
                except Exception as e:
                    return (path, None, e)

        # Download files concurrently
        tasks = [download_with_semaphore(path) for path in paths]

        for coro in asyncio.as_completed(tasks):
            path, content, error = await coro
            if error is not None:
                error_msg = f"Failed to download {path}: {error}"
                if not self.skip_errors:
                    raise DownloadError(error_msg) from error
                # Record error and skip this file
                self.errors.append(error_msg)
                continue
            if content is not None:
                yield (path, content)
