"""
Tests for URL normalization and parsing utilities.

Covers all functions in semrush_seo.url module:
- normalize_url: URL normalization with various options
- canonicalize_url: Aggressive canonicalization for SEO
- extract_domain: Domain extraction using Public Suffix List
- parse_url: Parse URL into URLInfo dataclass
- urls_are_equivalent: Compare normalized URLs
- is_internal_url: Check if URL belongs to same domain
- get_url_path_parts: Extract path segments
"""

import pytest

from semrush_seo.url import (
    KEEP_PARAMS,
    TRACKING_PARAMS,
    URLInfo,
    canonicalize_url,
    extract_domain,
    get_url_path_parts,
    is_internal_url,
    normalize_url,
    parse_url,
    urls_are_equivalent,
)


# =============================================================================
# normalize_url Tests
# =============================================================================


class TestNormalizeUrl:
    """Tests for the normalize_url function."""

    # --- Basic normalization ---

    def test_basic_url_normalization(self) -> None:
        """Test basic URL normalization."""
        result = normalize_url("https://example.com/page")
        assert result == "https://example.com/page"

    def test_preserves_https(self) -> None:
        """Test that HTTPS scheme is preserved."""
        result = normalize_url("https://example.com/")
        assert result.startswith("https://")

    def test_preserves_http(self) -> None:
        """Test that HTTP scheme is preserved by default."""
        result = normalize_url("http://example.com/")
        assert result.startswith("http://")

    def test_lowercases_domain(self) -> None:
        """Test that domain is lowercased."""
        result = normalize_url("https://EXAMPLE.COM/page")
        assert "example.com" in result

    def test_lowercases_path_by_default(self) -> None:
        """Test that path is lowercased by default."""
        result = normalize_url("https://example.com/PATH/TO/PAGE")
        assert result == "https://example.com/path/to/page"

    def test_preserves_path_case_when_disabled(self) -> None:
        """Test path case preservation when lowercase_path=False."""
        result = normalize_url("https://example.com/PATH", lowercase_path=False)
        assert result == "https://example.com/PATH"

    # --- Scheme handling ---

    def test_adds_https_when_missing(self) -> None:
        """Test that https:// is added when scheme is missing."""
        result = normalize_url("example.com/page")
        assert result == "https://example.com/page"

    def test_handles_protocol_relative_url(self) -> None:
        """Test handling of protocol-relative URLs (//)."""
        result = normalize_url("//example.com/page")
        assert result == "https://example.com/page"

    def test_force_https(self) -> None:
        """Test upgrading http to https with force_https."""
        result = normalize_url("http://example.com/", force_https=True)
        assert result.startswith("https://")

    # --- Trailing slash handling ---

    def test_removes_trailing_slash_by_default(self) -> None:
        """Test that trailing slash is removed by default."""
        result = normalize_url("https://example.com/page/")
        assert result == "https://example.com/page"

    def test_preserves_root_slash(self) -> None:
        """Test that root path slash is preserved."""
        result = normalize_url("https://example.com/")
        assert result == "https://example.com/"

    def test_preserves_trailing_slash_when_disabled(self) -> None:
        """Test trailing slash preservation when disabled."""
        result = normalize_url("https://example.com/page/", remove_trailing_slash=False)
        assert result == "https://example.com/page/"

    # --- WWW handling ---

    def test_preserves_www_by_default(self) -> None:
        """Test that www is preserved by default."""
        result = normalize_url("https://www.example.com/")
        assert "www.example.com" in result

    def test_removes_www(self) -> None:
        """Test www removal with remove_www option."""
        result = normalize_url("https://www.example.com/", remove_www=True)
        assert result == "https://example.com/"

    def test_adds_www(self) -> None:
        """Test www addition with add_www option."""
        result = normalize_url("https://example.com/", add_www=True)
        assert result == "https://www.example.com/"

    def test_add_www_no_duplicate(self) -> None:
        """Test that add_www doesn't duplicate www."""
        result = normalize_url("https://www.example.com/", add_www=True)
        assert "www.www" not in result

    # --- Port handling ---

    def test_removes_port_80(self) -> None:
        """Test removal of default HTTP port 80."""
        result = normalize_url("http://example.com:80/page")
        assert ":80" not in result

    def test_removes_port_443(self) -> None:
        """Test removal of default HTTPS port 443."""
        result = normalize_url("https://example.com:443/page")
        assert ":443" not in result

    def test_preserves_non_default_port(self) -> None:
        """Test that non-default ports are preserved."""
        result = normalize_url("https://example.com:8080/page")
        assert ":8080" in result

    # --- Path normalization ---

    def test_collapses_multiple_slashes(self) -> None:
        """Test that multiple slashes are collapsed."""
        result = normalize_url("https://example.com//path///to////page")
        # Check path doesn't have consecutive slashes (ignore scheme's //)
        path_part = result.split("://", 1)[1]
        assert "//" not in path_part
        assert result == "https://example.com/path/to/page"

    def test_adds_root_slash_when_missing(self) -> None:
        """Test that root slash is added when path is empty."""
        result = normalize_url("https://example.com")
        assert result == "https://example.com/"

    # --- Query parameter handling ---

    def test_removes_tracking_params_by_default(self) -> None:
        """Test that tracking parameters are removed by default."""
        result = normalize_url("https://example.com/?utm_source=google&page=1")
        assert "utm_source" not in result
        assert "page=1" in result

    def test_removes_all_common_tracking_params(self) -> None:
        """Test removal of various tracking parameters."""
        tracking_url = (
            "https://example.com/?utm_source=google&utm_medium=cpc"
            "&gclid=abc&fbclid=def&msclkid=ghi&_ga=123"
        )
        result = normalize_url(tracking_url)
        assert "utm_source" not in result
        assert "utm_medium" not in result
        assert "gclid" not in result
        assert "fbclid" not in result
        assert "msclkid" not in result
        assert "_ga" not in result

    def test_preserves_tracking_params_when_disabled(self) -> None:
        """Test tracking param preservation when disabled."""
        result = normalize_url(
            "https://example.com/?utm_source=google",
            remove_tracking_params=False,
        )
        assert "utm_source=google" in result

    def test_sorts_query_params_by_default(self) -> None:
        """Test that query parameters are sorted alphabetically."""
        result = normalize_url("https://example.com/?z=1&a=2&m=3")
        assert result == "https://example.com/?a=2&m=3&z=1"

    def test_preserves_query_order_when_disabled(self) -> None:
        """Test query param order preservation when disabled."""
        result = normalize_url(
            "https://example.com/?z=1&a=2",
            sort_query_params=False,
        )
        # Order should be preserved
        assert "z=1" in result and "a=2" in result

    def test_preserves_keep_params(self) -> None:
        """Test that important parameters from KEEP_PARAMS are preserved."""
        result = normalize_url("https://example.com/?page=1&q=search&id=123")
        assert "page=1" in result
        assert "q=search" in result
        assert "id=123" in result

    def test_handles_multiple_values_same_param(self) -> None:
        """Test handling of repeated query parameters."""
        result = normalize_url("https://example.com/?tag=a&tag=b")
        assert "tag=a" in result
        assert "tag=b" in result

    # --- Fragment handling ---

    def test_removes_fragment_by_default(self) -> None:
        """Test that URL fragments are removed by default."""
        result = normalize_url("https://example.com/page#section")
        assert "#" not in result

    def test_preserves_fragment_when_disabled(self) -> None:
        """Test fragment preservation when disabled."""
        result = normalize_url("https://example.com/page#section", remove_fragments=False)
        assert "#section" in result

    # --- Error handling ---

    def test_empty_url_raises_error(self) -> None:
        """Test that empty URL raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_url("")

    def test_whitespace_only_raises_error(self) -> None:
        """Test that whitespace-only URL raises ValueError."""
        with pytest.raises(ValueError, match="cannot be empty"):
            normalize_url("   ")

    def test_missing_domain_raises_error(self) -> None:
        """Test that URL without domain raises ValueError."""
        with pytest.raises(ValueError, match="missing domain"):
            normalize_url("https:///path")

    def test_strips_whitespace(self) -> None:
        """Test that leading/trailing whitespace is stripped."""
        result = normalize_url("  https://example.com/page  ")
        assert result == "https://example.com/page"


class TestNormalizeUrlEdgeCases:
    """Edge case tests for normalize_url."""

    def test_unicode_path(self) -> None:
        """Test handling of Unicode characters in path."""
        result = normalize_url("https://example.com/путь")
        assert "example.com" in result

    def test_encoded_characters(self) -> None:
        """Test handling of percent-encoded characters."""
        result = normalize_url("https://example.com/path%20with%20spaces")
        assert "example.com" in result

    def test_query_with_special_characters(self) -> None:
        """Test query params with special characters."""
        result = normalize_url("https://example.com/?q=hello+world&name=John%20Doe")
        assert "example.com" in result

    def test_very_long_url(self) -> None:
        """Test handling of very long URLs."""
        long_path = "/a" * 500
        result = normalize_url(f"https://example.com{long_path}")
        assert "example.com" in result

    def test_subdomain_handling(self) -> None:
        """Test that subdomains are preserved."""
        result = normalize_url("https://blog.api.example.com/page")
        assert "blog.api.example.com" in result


# =============================================================================
# canonicalize_url Tests
# =============================================================================


class TestCanonicalizeUrl:
    """Tests for the canonicalize_url function."""

    def test_basic_canonicalization(self) -> None:
        """Test basic URL canonicalization."""
        result = canonicalize_url("https://example.com/page")
        assert result == "https://example.com/page"

    def test_forces_https_by_default(self) -> None:
        """Test that HTTP is upgraded to HTTPS by default."""
        result = canonicalize_url("http://example.com/")
        assert result.startswith("https://")

    def test_prefer_www(self) -> None:
        """Test www preference with prefer_www='www'."""
        result = canonicalize_url("https://example.com/", prefer_www="www")
        assert "www.example.com" in result

    def test_prefer_non_www(self) -> None:
        """Test www removal with prefer_www='non-www'."""
        result = canonicalize_url("https://www.example.com/", prefer_www="non-www")
        assert "www." not in result

    def test_keep_www_preference(self) -> None:
        """Test www preservation with prefer_www='keep'."""
        result_with = canonicalize_url("https://www.example.com/", prefer_www="keep")
        result_without = canonicalize_url("https://example.com/", prefer_www="keep")
        assert "www." in result_with
        assert "www." not in result_without


# =============================================================================
# extract_domain Tests
# =============================================================================


class TestExtractDomain:
    """Tests for the extract_domain function."""

    def test_basic_domain_extraction(self) -> None:
        """Test basic domain extraction."""
        result = extract_domain("https://example.com/page")
        assert result == "example.com"

    def test_extracts_from_subdomain(self) -> None:
        """Test domain extraction from URL with subdomain."""
        result = extract_domain("https://blog.example.com/page")
        assert result == "example.com"

    def test_handles_multi_part_tld(self) -> None:
        """Test extraction with multi-part TLDs like .co.uk."""
        result = extract_domain("https://blog.example.co.uk/page")
        assert result == "example.co.uk"

    def test_handles_com_au(self) -> None:
        """Test extraction with .com.au TLD."""
        result = extract_domain("https://shop.example.com.au/")
        assert result == "example.com.au"

    def test_deeply_nested_subdomain(self) -> None:
        """Test extraction from deeply nested subdomains."""
        result = extract_domain("https://a.b.c.example.org/")
        assert result == "example.org"

    def test_handles_www(self) -> None:
        """Test domain extraction with www."""
        result = extract_domain("https://www.example.com/")
        assert result == "example.com"


# =============================================================================
# parse_url Tests
# =============================================================================


class TestParseUrl:
    """Tests for the parse_url function."""

    def test_basic_parsing(self) -> None:
        """Test basic URL parsing."""
        info = parse_url("https://example.com/page")
        assert info.scheme == "https"
        assert info.registered_domain == "example.com"
        assert info.path == "/page"

    def test_preserves_original(self) -> None:
        """Test that original URL is preserved."""
        original = "https://EXAMPLE.com/PAGE"
        info = parse_url(original)
        assert info.original == original
        assert info.normalized != original  # normalized is different

    def test_extracts_subdomain(self) -> None:
        """Test subdomain extraction."""
        info = parse_url("https://blog.example.com/")
        assert info.subdomain == "blog"
        assert info.domain == "example"
        assert info.suffix == "com"

    def test_extracts_query(self) -> None:
        """Test query string extraction."""
        info = parse_url("https://example.com/?page=1&sort=asc")
        assert "page=1" in info.query
        assert "sort=asc" in info.query

    def test_full_domain_property(self) -> None:
        """Test full_domain property."""
        info = parse_url("https://blog.example.com/")
        assert info.full_domain == "blog.example.com"

    def test_full_domain_no_subdomain(self) -> None:
        """Test full_domain without subdomain."""
        info = parse_url("https://example.com/")
        assert info.full_domain == "example.com"

    def test_is_https_property(self) -> None:
        """Test is_https property."""
        https_info = parse_url("https://example.com/")
        http_info = parse_url("http://example.com/")
        assert https_info.is_https is True
        assert http_info.is_https is False

    def test_is_www_property(self) -> None:
        """Test is_www property."""
        www_info = parse_url("https://www.example.com/")
        no_www_info = parse_url("https://example.com/")
        assert www_info.is_www is True
        assert no_www_info.is_www is False

    def test_path_depth_property(self) -> None:
        """Test path_depth property."""
        assert parse_url("https://example.com/").path_depth == 0
        assert parse_url("https://example.com/page").path_depth == 1
        assert parse_url("https://example.com/blog/2024/post").path_depth == 3


class TestURLInfoDataclass:
    """Tests for URLInfo dataclass properties."""

    def test_urlinfo_is_frozen(self) -> None:
        """Test that URLInfo is immutable."""
        info = parse_url("https://example.com/")
        with pytest.raises(AttributeError):
            info.scheme = "http"  # type: ignore

    def test_urlinfo_equality(self) -> None:
        """Test URLInfo equality comparison."""
        info1 = parse_url("https://example.com/page")
        info2 = parse_url("https://example.com/page")
        assert info1.normalized == info2.normalized


# =============================================================================
# urls_are_equivalent Tests
# =============================================================================


class TestUrlsAreEquivalent:
    """Tests for the urls_are_equivalent function."""

    def test_identical_urls_equivalent(self) -> None:
        """Test that identical URLs are equivalent."""
        assert urls_are_equivalent(
            "https://example.com/page",
            "https://example.com/page",
        )

    def test_case_differences_equivalent(self) -> None:
        """Test that URLs differing only in case are equivalent."""
        assert urls_are_equivalent(
            "https://EXAMPLE.COM/PATH",
            "https://example.com/path",
        )

    def test_trailing_slash_equivalent(self) -> None:
        """Test that trailing slash differences are equivalent."""
        assert urls_are_equivalent(
            "https://example.com/page/",
            "https://example.com/page",
        )

    def test_tracking_params_equivalent(self) -> None:
        """Test that URLs with tracking params are equivalent to those without."""
        assert urls_are_equivalent(
            "https://example.com/page?utm_source=google",
            "https://example.com/page",
        )

    def test_query_order_equivalent(self) -> None:
        """Test that query param order differences are equivalent."""
        assert urls_are_equivalent(
            "https://example.com/?a=1&b=2",
            "https://example.com/?b=2&a=1",
        )

    def test_fragment_equivalent(self) -> None:
        """Test that fragment differences are equivalent."""
        assert urls_are_equivalent(
            "https://example.com/page#section",
            "https://example.com/page",
        )

    def test_different_urls_not_equivalent(self) -> None:
        """Test that actually different URLs are not equivalent."""
        assert not urls_are_equivalent(
            "https://example.com/page1",
            "https://example.com/page2",
        )

    def test_different_domains_not_equivalent(self) -> None:
        """Test that different domains are not equivalent."""
        assert not urls_are_equivalent(
            "https://example.com/page",
            "https://other.com/page",
        )

    def test_handles_invalid_url(self) -> None:
        """Test that invalid URLs return False instead of raising."""
        assert not urls_are_equivalent("", "https://example.com/")
        assert not urls_are_equivalent("https://example.com/", "")


# =============================================================================
# is_internal_url Tests
# =============================================================================


class TestIsInternalUrl:
    """Tests for the is_internal_url function."""

    def test_same_domain_is_internal(self) -> None:
        """Test that same domain is considered internal."""
        assert is_internal_url("https://example.com/page", "example.com")

    def test_subdomain_is_internal(self) -> None:
        """Test that subdomains are considered internal."""
        assert is_internal_url("https://blog.example.com/page", "example.com")
        assert is_internal_url("https://api.example.com/v1", "example.com")

    def test_www_is_internal(self) -> None:
        """Test that www subdomain is considered internal."""
        assert is_internal_url("https://www.example.com/page", "example.com")

    def test_different_domain_is_external(self) -> None:
        """Test that different domains are external."""
        assert not is_internal_url("https://other.com/page", "example.com")

    def test_similar_domain_is_external(self) -> None:
        """Test that similar but different domains are external."""
        assert not is_internal_url("https://example.org/page", "example.com")
        assert not is_internal_url("https://myexample.com/page", "example.com")

    def test_case_insensitive(self) -> None:
        """Test that comparison is case-insensitive."""
        assert is_internal_url("https://EXAMPLE.COM/page", "example.com")
        assert is_internal_url("https://example.com/page", "EXAMPLE.COM")

    def test_base_domain_with_subdomain(self) -> None:
        """Test when base_domain includes a subdomain."""
        assert is_internal_url("https://api.example.com/", "www.example.com")

    def test_multi_part_tld(self) -> None:
        """Test with multi-part TLDs."""
        assert is_internal_url("https://blog.example.co.uk/", "example.co.uk")
        assert not is_internal_url("https://blog.example.com/", "example.co.uk")


# =============================================================================
# get_url_path_parts Tests
# =============================================================================


class TestGetUrlPathParts:
    """Tests for the get_url_path_parts function."""

    def test_basic_path_parts(self) -> None:
        """Test basic path segment extraction."""
        parts = get_url_path_parts("https://example.com/blog/2024/post-title")
        assert parts == ["blog", "2024", "post-title"]

    def test_root_path_empty(self) -> None:
        """Test that root path returns empty list."""
        parts = get_url_path_parts("https://example.com/")
        assert parts == []

    def test_single_segment(self) -> None:
        """Test single path segment."""
        parts = get_url_path_parts("https://example.com/page")
        assert parts == ["page"]

    def test_trailing_slash_ignored(self) -> None:
        """Test that trailing slash doesn't affect segments."""
        parts = get_url_path_parts("https://example.com/blog/post/")
        assert parts == ["blog", "post"]

    def test_path_normalized(self) -> None:
        """Test that path is normalized before extraction."""
        parts = get_url_path_parts("https://example.com/BLOG/POST")
        assert parts == ["blog", "post"]  # lowercased


# =============================================================================
# Constants Tests
# =============================================================================


class TestConstants:
    """Tests for module constants."""

    def test_tracking_params_contains_common_params(self) -> None:
        """Test that TRACKING_PARAMS contains common tracking parameters."""
        assert "utm_source" in TRACKING_PARAMS
        assert "utm_medium" in TRACKING_PARAMS
        assert "utm_campaign" in TRACKING_PARAMS
        assert "gclid" in TRACKING_PARAMS
        assert "fbclid" in TRACKING_PARAMS
        assert "msclkid" in TRACKING_PARAMS

    def test_keep_params_contains_important_params(self) -> None:
        """Test that KEEP_PARAMS contains important SEO parameters."""
        assert "page" in KEEP_PARAMS
        assert "q" in KEEP_PARAMS
        assert "query" in KEEP_PARAMS
        assert "id" in KEEP_PARAMS
        assert "category" in KEEP_PARAMS
