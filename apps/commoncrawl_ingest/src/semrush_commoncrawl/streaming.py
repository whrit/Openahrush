"""
Streaming WAT parser for memory-efficient edge extraction.

Provides async generators for streaming WAT content parsing
without loading entire files into memory.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from urllib.parse import urlparse

from semrush_commoncrawl.storage.base import Edge


def _extract_domain(url: str) -> str:
    """Extract domain from URL."""
    try:
        parsed = urlparse(url)
        domain = parsed.netloc
        if domain.startswith("www."):
            domain = domain[4:]
        return domain
    except Exception:
        return ""


def _parse_warc_records(content: bytes) -> list[dict]:
    """Parse WARC records from WAT content."""
    records = []
    text = content.decode("utf-8", errors="ignore")

    # Split by WARC record boundaries
    parts = re.split(r"WARC/1\.0[\r\n]+", text)

    for part in parts[1:]:  # Skip empty first part
        # Find JSON payload after headers
        header_end = part.find("\r\n\r\n")
        if header_end == -1:
            header_end = part.find("\n\n")
        if header_end == -1:
            continue

        payload = part[header_end:].strip()
        if not payload:
            continue

        # Extract JSON object
        try:
            # Find start of JSON
            json_start = payload.find("{")
            if json_start == -1:
                continue
            # Find matching end brace
            brace_count = 0
            json_end = json_start
            for i, c in enumerate(payload[json_start:]):
                if c == "{":
                    brace_count += 1
                elif c == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = json_start + i + 1
                        break

            json_str = payload[json_start:json_end]
            record = json.loads(json_str)
            records.append(record)
        except (json.JSONDecodeError, ValueError):
            continue

    return records


def _extract_edges_from_record(record: dict, snapshot_id: str = "") -> list[Edge]:
    """Extract edges from a parsed WAT record."""
    edges: list[Edge] = []

    try:
        envelope = record.get("Envelope", {})
        warc_header = envelope.get("WARC-Header-Metadata", {})
        payload_meta = envelope.get("Payload-Metadata", {})

        source_url = warc_header.get("WARC-Target-URI", "")
        if not source_url:
            return edges

        source_domain = _extract_domain(source_url)
        if not source_domain:
            return edges

        http_meta = payload_meta.get("HTTP-Response-Metadata", {})
        html_meta = http_meta.get("HTML-Metadata", {})
        links = html_meta.get("Links", [])

        for link in links:
            target_url = link.get("url", "")
            if not target_url or not target_url.startswith("http"):
                continue

            target_domain = _extract_domain(target_url)
            if not target_domain:
                continue

            # Skip same-domain links
            if target_domain == source_domain:
                continue

            anchor = link.get("text", "") or link.get("title", "")
            rel_str = link.get("rel", "")
            rel_flags = rel_str.split() if rel_str else None

            edge = Edge(
                snapshot_id=snapshot_id,
                source_url=source_url,
                source_domain=source_domain,
                target_url=target_url,
                target_domain=target_domain,
                anchor=anchor if anchor else None,
                rel_flags=rel_flags,
            )
            edges.append(edge)

    except Exception:
        pass

    return edges


async def stream_parse_wat(content: bytes, snapshot_id: str = "") -> AsyncIterator[Edge]:
    """
    Parse WAT content and yield edges asynchronously.

    Memory-efficient streaming parser that yields edges one at a time.

    Args:
        content: Raw WAT file content (decompressed).
        snapshot_id: Common Crawl snapshot ID for edge metadata.

    Yields:
        Edge objects extracted from the WAT content.
    """
    if not content:
        return

    records = _parse_warc_records(content)

    for record in records:
        edges = _extract_edges_from_record(record, snapshot_id)
        for edge in edges:
            yield edge


async def stream_parse_wat_batched(
    content: bytes, batch_size: int = 1000, snapshot_id: str = ""
) -> AsyncIterator[list[Edge]]:
    """
    Parse WAT content and yield batches of edges.

    Groups edges into batches for efficient bulk processing.

    Args:
        content: Raw WAT file content (decompressed).
        batch_size: Number of edges per batch.
        snapshot_id: Common Crawl snapshot ID for edge metadata.

    Yields:
        Lists of Edge objects in batches.
    """
    batch: list[Edge] = []

    async for edge in stream_parse_wat(content, snapshot_id):
        batch.append(edge)
        if len(batch) >= batch_size:
            yield batch
            batch = []

    if batch:
        yield batch
