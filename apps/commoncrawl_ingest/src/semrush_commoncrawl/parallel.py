"""
Parallel WAT file processing with concurrency control.

Provides parallel download and processing of WAT files with
configurable concurrency limits and error handling.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any


@dataclass
class ProcessingResult:
    """
    Result of processing a single WAT file.

    Attributes:
        path: WAT file path.
        success: Whether processing succeeded.
        edges_count: Number of edges extracted (0 on failure).
        content: Raw content for further processing (optional).
        error: Error message if processing failed.
    """

    path: str
    success: bool
    edges_count: int = 0
    content: bytes | None = None
    error: str | None = None


async def process_wat_files_parallel(
    paths: list[str],
    download_fn: Callable[[str], Any],
    concurrency: int = 4,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> AsyncIterator[ProcessingResult]:
    """
    Process WAT files in parallel with controlled concurrency.

    Downloads and yields results for WAT files using a semaphore
    to limit concurrent operations.

    Args:
        paths: List of WAT file paths to process.
        download_fn: Async function to download a file by path.
        concurrency: Maximum concurrent downloads.
        on_progress: Optional callback for progress updates.

    Yields:
        ProcessingResult for each file as it completes.
    """
    semaphore = asyncio.Semaphore(concurrency)

    async def download_with_semaphore(
        path: str,
    ) -> ProcessingResult:
        async with semaphore:
            try:
                content = await download_fn(path)
                # Count edges for progress tracking
                edges_count = content.count(b"https://") if content else 0
                result = ProcessingResult(
                    path=path,
                    success=True,
                    edges_count=edges_count,
                    content=content,
                )
                if on_progress:
                    on_progress({"path": path, "edges_count": edges_count})
                return result
            except Exception as e:
                result = ProcessingResult(
                    path=path,
                    success=False,
                    error=str(e),
                )
                if on_progress:
                    on_progress({"path": path, "edges_count": 0, "error": str(e)})
                return result

    tasks = [download_with_semaphore(path) for path in paths]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        yield result
