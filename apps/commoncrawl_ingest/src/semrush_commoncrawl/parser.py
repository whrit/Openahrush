"""
WAT record parser for Common Crawl ingestion.

Parses WAT WARC format records and extracts link edges with
URL normalization, anchor text extraction, and rel flag parsing.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from semrush_seo.url import extract_domain, normalize_url

# SEO-relevant rel values to track
SEO_REL_VALUES = {"nofollow", "ugc", "sponsored"}

# Non-HTTP schemes to skip
SKIP_SCHEMES = {"mailto", "tel", "javascript", "data", "ftp", "file"}


@dataclass(frozen=True, slots=True)
class Edge:
    """
    Represents a link edge extracted from Common Crawl data.

    An edge represents a hyperlink from a source page to a target URL,
    including metadata like anchor text and rel flags.

    Attributes:
        source_url: Normalized URL of the source page.
        source_domain: Registered domain of the source page.
        target_url: Normalized URL of the linked target.
        target_domain: Registered domain of the target.
        anchor_text: Link anchor text (may be empty).
        rel_flags: Set of SEO-relevant rel values (nofollow, ugc, sponsored).
    """

    source_url: str
    source_domain: str
    target_url: str
    target_domain: str
    anchor_text: str = ""
    rel_flags: frozenset[str] = field(default_factory=frozenset)

    def __post_init__(self) -> None:
        """Convert rel_flags to frozenset if needed."""
        if isinstance(self.rel_flags, set):
            object.__setattr__(self, "rel_flags", frozenset(self.rel_flags))


def parse_rel_flags(rel: str | None) -> set[str]:
    """
    Parse rel attribute value into a set of SEO-relevant flags.

    Extracts and normalizes rel values, keeping only SEO-relevant
    values (nofollow, ugc, sponsored).

    Args:
        rel: The rel attribute value (space-separated values).

    Returns:
        Set of normalized, SEO-relevant rel values.

    Examples:
        >>> parse_rel_flags("nofollow ugc")
        {'nofollow', 'ugc'}

        >>> parse_rel_flags("noreferrer noopener")
        set()
    """
    if not rel:
        return set()

    values = rel.lower().split()
    return {v for v in values if v in SEO_REL_VALUES}


def _normalize_target_url(url: str, source_url: str) -> str | None:
    """
    Normalize a target URL, resolving relative URLs.

    Args:
        url: The target URL (may be relative).
        source_url: The source page URL for resolving relative URLs.

    Returns:
        Normalized absolute URL, or None if invalid/non-HTTP.
    """
    if not url:
        return None

    url = url.strip()

    # Check for non-HTTP schemes
    url_lower = url.lower()
    for scheme in SKIP_SCHEMES:
        if url_lower.startswith(f"{scheme}:"):
            return None

    # Handle relative URLs
    if url.startswith("/"):
        # Absolute path - resolve against source
        try:
            parsed_source = urlparse(source_url)
            if not parsed_source.scheme or not parsed_source.netloc:
                return None
            url = f"{parsed_source.scheme}://{parsed_source.netloc}{url}"
        except Exception:
            return None
    elif not url_lower.startswith(("http://", "https://", "//")):
        # Relative path - skip for now (complex resolution)
        return None

    # Normalize the URL
    try:
        return normalize_url(url, remove_fragments=True)
    except ValueError:
        return None


def _extract_links_from_record(record: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract link data from a WAT record JSON structure.

    Args:
        record: Parsed WAT record JSON.

    Returns:
        List of link dictionaries with url, text, rel fields.
    """
    try:
        envelope = record.get("Envelope", {})
        payload = envelope.get("Payload-Metadata", {})
        http_response = payload.get("HTTP-Response-Metadata", {})
        html_metadata = http_response.get("HTML-Metadata", {})
        return html_metadata.get("Links", [])
    except (KeyError, TypeError, AttributeError):
        return []


def _extract_source_url(record: dict[str, Any]) -> str | None:
    """
    Extract the source URL from a WAT record.

    Args:
        record: Parsed WAT record JSON.

    Returns:
        Source URL or None if not found.
    """
    try:
        envelope = record.get("Envelope", {})
        warc_header = envelope.get("WARC-Header-Metadata", {})
        return warc_header.get("WARC-Target-URI")
    except (KeyError, TypeError, AttributeError):
        return None


def parse_wat_records(content: bytes) -> Iterator[Edge]:
    """
    Parse WAT file content and extract link edges.

    Parses the WARC format to extract JSON metadata records,
    then extracts links from each record, normalizing URLs and
    parsing rel flags.

    Args:
        content: Raw WAT file content (decompressed).

    Yields:
        Edge objects for each external link found.

    Note:
        - Skips relative/internal links (same domain as source)
        - Skips non-HTTP URLs (mailto, javascript, etc.)
        - Normalizes URLs (lowercase, remove fragments, etc.)
    """
    if not content:
        return

    # Split content into WARC records
    # WAT files contain WARC headers followed by JSON payloads
    content_str = content.decode("utf-8", errors="replace")

    # Pattern to find JSON payloads in WARC records
    # WARC records are separated by \r\n\r\n
    records = re.split(r"\r?\n\r?\n", content_str)

    for record_text in records:
        record_text = record_text.strip()
        if not record_text:
            continue

        # Skip WARC headers, look for JSON content
        if record_text.startswith("WARC/"):
            continue

        # Try to parse as JSON
        if not record_text.startswith("{"):
            continue

        try:
            record = json.loads(record_text)
        except json.JSONDecodeError:
            continue

        # Extract source URL
        source_url = _extract_source_url(record)
        if not source_url:
            continue

        # Normalize source URL
        try:
            normalized_source = normalize_url(source_url, remove_fragments=True)
            source_domain = extract_domain(source_url)
        except ValueError:
            continue

        if not source_domain:
            continue

        # Extract links
        links = _extract_links_from_record(record)

        for link in links:
            if not isinstance(link, dict):
                continue

            # Get target URL
            target_url = link.get("url")
            if not target_url:
                continue

            # Normalize target URL
            normalized_target = _normalize_target_url(target_url, normalized_source)
            if not normalized_target:
                continue

            # Extract target domain
            try:
                target_domain = extract_domain(normalized_target)
            except Exception:
                continue

            if not target_domain:
                continue

            # Skip internal links (same domain as source)
            if target_domain.lower() == source_domain.lower():
                continue

            # Extract anchor text
            anchor_text = link.get("text", "") or ""
            if isinstance(anchor_text, str):
                anchor_text = anchor_text.strip()
            else:
                anchor_text = ""

            # Parse rel flags
            rel = link.get("rel")
            rel_flags = parse_rel_flags(rel)

            yield Edge(
                source_url=normalized_source,
                source_domain=source_domain,
                target_url=normalized_target,
                target_domain=target_domain,
                anchor_text=anchor_text,
                rel_flags=frozenset(rel_flags),
            )
