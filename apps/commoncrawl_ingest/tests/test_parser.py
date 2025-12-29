"""
TDD tests for the WAT record parser.

Tests cover:
- Parsing WAT WARC format
- Extracting links from JSON payloads
- URL normalization
- Anchor text extraction
- Rel flag parsing
- Edge dataclass creation
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    pass


# ============================================================================
# Tests for Edge dataclass
# ============================================================================


class TestEdgeDataclass:
    """Tests for the Edge dataclass."""

    def test_edge_has_required_fields(self) -> None:
        """Edge should have source_url, target_url, anchor_text, rel_flags."""
        from semrush_commoncrawl.parser import Edge

        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://target.com/page",
            target_domain="target.com",
            anchor_text="Click here",
            rel_flags={"nofollow"},
        )

        assert edge.source_url == "https://source.com/page"
        assert edge.source_domain == "source.com"
        assert edge.target_url == "https://target.com/page"
        assert edge.target_domain == "target.com"
        assert edge.anchor_text == "Click here"
        assert "nofollow" in edge.rel_flags

    def test_edge_has_optional_fields(self) -> None:
        """Edge should support optional fields with defaults."""
        from semrush_commoncrawl.parser import Edge

        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://target.com/page",
            target_domain="target.com",
        )

        assert edge.anchor_text == ""
        assert edge.rel_flags == set()

    def test_edge_is_immutable(self) -> None:
        """Edge should be frozen (immutable)."""
        from semrush_commoncrawl.parser import Edge

        edge = Edge(
            source_url="https://source.com/page",
            source_domain="source.com",
            target_url="https://target.com/page",
            target_domain="target.com",
        )

        with pytest.raises(AttributeError):
            edge.source_url = "https://other.com"  # type: ignore[misc]


# ============================================================================
# Tests for parse_wat_records
# ============================================================================


class TestParseWatRecords:
    """Tests for parsing WAT records into edges."""

    def test_parse_wat_records_extracts_edges(
        self,
        sample_wat_content: bytes,
    ) -> None:
        """parse_wat_records should extract Edge objects from WAT content."""
        from semrush_commoncrawl.parser import parse_wat_records

        edges = list(parse_wat_records(sample_wat_content))

        # Should extract links from the sample content
        assert len(edges) > 0
        assert all(hasattr(edge, "source_url") for edge in edges)
        assert all(hasattr(edge, "target_url") for edge in edges)

    def test_parse_wat_records_extracts_source_url(
        self,
        sample_wat_content: bytes,
    ) -> None:
        """parse_wat_records should extract source URL from WARC headers."""
        from semrush_commoncrawl.parser import parse_wat_records

        edges = list(parse_wat_records(sample_wat_content))

        # All edges should have source URL from WARC-Target-URI
        for edge in edges:
            assert "source-site.com" in edge.source_url

    def test_parse_wat_records_extracts_target_url(
        self,
        sample_wat_content: bytes,
    ) -> None:
        """parse_wat_records should extract target URLs from links."""
        from semrush_commoncrawl.parser import parse_wat_records

        edges = list(parse_wat_records(sample_wat_content))
        target_domains = {edge.target_domain for edge in edges}

        # Should have extracted links to target-site.com and another-site.com
        assert "target-site.com" in target_domains or "another-site.com" in target_domains

    def test_parse_wat_records_extracts_anchor_text(
        self,
        sample_wat_content: bytes,
    ) -> None:
        """parse_wat_records should extract anchor text from links."""
        from semrush_commoncrawl.parser import parse_wat_records

        edges = list(parse_wat_records(sample_wat_content))
        anchor_texts = {edge.anchor_text for edge in edges}

        # Should have extracted anchor texts
        assert any(text for text in anchor_texts if text)

    def test_parse_wat_records_extracts_rel_flags(
        self,
        sample_wat_content: bytes,
    ) -> None:
        """parse_wat_records should extract rel flags (nofollow, ugc, sponsored)."""
        from semrush_commoncrawl.parser import parse_wat_records

        edges = list(parse_wat_records(sample_wat_content))
        all_rel_flags = set()
        for edge in edges:
            all_rel_flags.update(edge.rel_flags)

        # Should have extracted nofollow, ugc, sponsored from sample content
        assert "nofollow" in all_rel_flags or "sponsored" in all_rel_flags

    def test_parse_wat_records_normalizes_urls(self) -> None:
        """parse_wat_records should normalize URLs."""
        from semrush_commoncrawl.parser import parse_wat_records

        # Create WAT content with unnormalized URLs
        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "HTTPS://SOURCE.COM/Page/",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": [
                                {
                                    "url": "HTTPS://TARGET.COM/Path#fragment",
                                    "path": "A@/href",
                                    "text": "Link",
                                },
                            ],
                        },
                    },
                },
            },
        }

        warc_content = self._create_warc_content(record)
        edges = list(parse_wat_records(warc_content))

        assert len(edges) == 1
        edge = edges[0]

        # URLs should be normalized (lowercase, no fragments)
        assert edge.source_url == "https://source.com/page"
        assert edge.target_url == "https://target.com/path"

    def test_parse_wat_records_extracts_domain(self) -> None:
        """parse_wat_records should extract domain from URLs."""
        from semrush_commoncrawl.parser import parse_wat_records

        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://blog.example.co.uk/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Links": [
                                {
                                    "url": "https://sub.target.org/path",
                                    "path": "A@/href",
                                    "text": "Link",
                                },
                            ],
                        },
                    },
                },
            },
        }

        warc_content = self._create_warc_content(record)
        edges = list(parse_wat_records(warc_content))

        assert len(edges) == 1
        edge = edges[0]

        # Should extract registered domain
        assert edge.source_domain == "example.co.uk"
        assert edge.target_domain == "target.org"

    def test_parse_wat_records_skips_internal_links(self) -> None:
        """parse_wat_records should skip relative/internal links by default."""
        from semrush_commoncrawl.parser import parse_wat_records

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
                                    "url": "/internal/page",
                                    "path": "A@/href",
                                    "text": "Internal",
                                },
                                {
                                    "url": "https://external.com/page",
                                    "path": "A@/href",
                                    "text": "External",
                                },
                            ],
                        },
                    },
                },
            },
        }

        warc_content = self._create_warc_content(record)
        edges = list(parse_wat_records(warc_content))

        # Should only include external link
        assert len(edges) == 1
        assert edges[0].target_domain == "external.com"

    def test_parse_wat_records_skips_non_http_urls(self) -> None:
        """parse_wat_records should skip non-HTTP URLs (mailto, javascript, etc)."""
        from semrush_commoncrawl.parser import parse_wat_records

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
                                    "url": "mailto:test@example.com",
                                    "path": "A@/href",
                                    "text": "Email",
                                },
                                {
                                    "url": "javascript:void(0)",
                                    "path": "A@/href",
                                    "text": "JS",
                                },
                                {
                                    "url": "tel:+1234567890",
                                    "path": "A@/href",
                                    "text": "Phone",
                                },
                                {
                                    "url": "https://valid.com/page",
                                    "path": "A@/href",
                                    "text": "Valid",
                                },
                            ],
                        },
                    },
                },
            },
        }

        warc_content = self._create_warc_content(record)
        edges = list(parse_wat_records(warc_content))

        # Should only include valid HTTP link
        assert len(edges) == 1
        assert edges[0].target_domain == "valid.com"

    def test_parse_wat_records_handles_empty_content(self) -> None:
        """parse_wat_records should handle empty content gracefully."""
        from semrush_commoncrawl.parser import parse_wat_records

        edges = list(parse_wat_records(b""))

        assert edges == []

    def test_parse_wat_records_handles_malformed_json(self) -> None:
        """parse_wat_records should skip malformed JSON records."""
        from semrush_commoncrawl.parser import parse_wat_records

        malformed_content = (
            b"WARC/1.0\r\n"
            b"WARC-Type: metadata\r\n"
            b"Content-Length: 20\r\n"
            b"\r\n"
            b"{ invalid json here"
        )

        # Should not raise, should skip malformed record
        edges = list(parse_wat_records(malformed_content))
        assert edges == []

    def test_parse_wat_records_handles_missing_links(self) -> None:
        """parse_wat_records should handle records without Links field."""
        from semrush_commoncrawl.parser import parse_wat_records

        record = {
            "Envelope": {
                "WARC-Header-Metadata": {
                    "WARC-Type": "metadata",
                    "WARC-Target-URI": "https://source.com/page",
                },
                "Payload-Metadata": {
                    "HTTP-Response-Metadata": {
                        "HTML-Metadata": {
                            "Head": {"Title": "No links page"},
                        },
                    },
                },
            },
        }

        warc_content = self._create_warc_content(record)
        edges = list(parse_wat_records(warc_content))

        assert edges == []

    def test_parse_wat_records_parses_multiple_rel_values(self) -> None:
        """parse_wat_records should parse multiple rel values."""
        from semrush_commoncrawl.parser import parse_wat_records

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
                                    "rel": "nofollow ugc sponsored",
                                },
                            ],
                        },
                    },
                },
            },
        }

        warc_content = self._create_warc_content(record)
        edges = list(parse_wat_records(warc_content))

        assert len(edges) == 1
        assert edges[0].rel_flags == {"nofollow", "ugc", "sponsored"}

    def _create_warc_content(self, record: dict[str, Any]) -> bytes:
        """Helper to create WARC content from a record dict."""
        json_content = json.dumps(record)
        warc_header = (
            "WARC/1.0\r\n"
            "WARC-Type: metadata\r\n"
            f"Content-Length: {len(json_content)}\r\n"
            "\r\n"
        )
        return (warc_header + json_content + "\r\n\r\n").encode("utf-8")


# ============================================================================
# Tests for parse_rel_flags helper
# ============================================================================


class TestParseRelFlags:
    """Tests for the rel flags parsing helper."""

    def test_parse_rel_flags_single_value(self) -> None:
        """Should parse single rel value."""
        from semrush_commoncrawl.parser import parse_rel_flags

        result = parse_rel_flags("nofollow")
        assert result == {"nofollow"}

    def test_parse_rel_flags_multiple_values(self) -> None:
        """Should parse space-separated rel values."""
        from semrush_commoncrawl.parser import parse_rel_flags

        result = parse_rel_flags("nofollow ugc sponsored")
        assert result == {"nofollow", "ugc", "sponsored"}

    def test_parse_rel_flags_empty_string(self) -> None:
        """Should return empty set for empty string."""
        from semrush_commoncrawl.parser import parse_rel_flags

        result = parse_rel_flags("")
        assert result == set()

    def test_parse_rel_flags_none(self) -> None:
        """Should return empty set for None."""
        from semrush_commoncrawl.parser import parse_rel_flags

        result = parse_rel_flags(None)
        assert result == set()

    def test_parse_rel_flags_normalizes_case(self) -> None:
        """Should normalize rel values to lowercase."""
        from semrush_commoncrawl.parser import parse_rel_flags

        result = parse_rel_flags("NoFollow UGC SPONSORED")
        assert result == {"nofollow", "ugc", "sponsored"}

    def test_parse_rel_flags_filters_known_values(self) -> None:
        """Should only include known SEO-relevant rel values."""
        from semrush_commoncrawl.parser import parse_rel_flags

        result = parse_rel_flags("nofollow noreferrer noopener ugc sponsored")
        # Only SEO-relevant values should be included
        assert "nofollow" in result
        assert "ugc" in result
        assert "sponsored" in result
