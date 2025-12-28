"""
Tests for robots.txt parser.

TDD tests covering:
- Fetching and caching robots.txt per domain
- Parsing Allow/Disallow rules
- User-Agent matching
- Sitemap URL extraction
- Crawl-delay handling
- Bypass option for respect_robots=false
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from semrush_seo.robots import (
    RobotsParser,
    RobotsRule,
    RobotsSettings,
    is_allowed,
    parse_robots_txt,
)


class TestRobotsSettings:
    """Tests for RobotsSettings configuration."""

    def test_default_settings(self) -> None:
        """Default settings should have sensible values."""
        settings = RobotsSettings()
        assert settings.user_agent == "Openahrush"
        assert settings.respect_robots is True
        assert settings.cache_ttl_seconds == 3600

    def test_custom_settings(self) -> None:
        """Custom settings should override defaults."""
        settings = RobotsSettings(
            user_agent="CustomBot",
            respect_robots=False,
            cache_ttl_seconds=7200,
        )
        assert settings.user_agent == "CustomBot"
        assert settings.respect_robots is False
        assert settings.cache_ttl_seconds == 7200


class TestRobotsRule:
    """Tests for RobotsRule dataclass."""

    def test_disallow_rule(self) -> None:
        """Disallow rule should be created correctly."""
        rule = RobotsRule(path="/admin", allow=False)
        assert rule.path == "/admin"
        assert rule.allow is False

    def test_allow_rule(self) -> None:
        """Allow rule should be created correctly."""
        rule = RobotsRule(path="/admin/login", allow=True)
        assert rule.path == "/admin/login"
        assert rule.allow is True


class TestParseRobotsTxt:
    """Tests for robots.txt parsing."""

    def test_parse_simple_disallow(self) -> None:
        """Parse simple Disallow rule."""
        content = """
User-agent: *
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert len(result.rules) >= 1
        assert any(r.path == "/admin" and not r.allow for r in result.rules)

    def test_parse_multiple_disallow(self) -> None:
        """Parse multiple Disallow rules."""
        content = """
User-agent: *
Disallow: /admin
Disallow: /private
Disallow: /temp
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        paths = [r.path for r in result.rules if not r.allow]
        assert "/admin" in paths
        assert "/private" in paths
        assert "/temp" in paths

    def test_parse_allow_and_disallow(self) -> None:
        """Parse Allow and Disallow rules together."""
        content = """
User-agent: *
Disallow: /admin
Allow: /admin/login
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any(r.path == "/admin" and not r.allow for r in result.rules)
        assert any(r.path == "/admin/login" and r.allow for r in result.rules)

    def test_parse_specific_user_agent(self) -> None:
        """Parse rules for specific User-Agent."""
        content = """
User-agent: Googlebot
Disallow: /google-only

User-agent: Openahrush
Disallow: /openahrush-blocked

User-agent: *
Disallow: /blocked-all
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        # Should have Openahrush-specific rules
        paths = [r.path for r in result.rules]
        assert "/openahrush-blocked" in paths

    def test_parse_wildcard_user_agent(self) -> None:
        """Parse rules for wildcard User-Agent when no specific match."""
        content = """
User-agent: Googlebot
Disallow: /google-only

User-agent: *
Disallow: /blocked-all
"""
        result = parse_robots_txt(content, user_agent="UnknownBot")
        # Should fall back to wildcard rules
        paths = [r.path for r in result.rules]
        assert "/blocked-all" in paths
        assert "/google-only" not in paths

    def test_parse_sitemap(self) -> None:
        """Parse Sitemap URLs."""
        content = """
User-agent: *
Disallow: /admin

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap-news.xml
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert "https://example.com/sitemap.xml" in result.sitemaps
        assert "https://example.com/sitemap-news.xml" in result.sitemaps

    def test_parse_crawl_delay(self) -> None:
        """Parse Crawl-delay directive."""
        content = """
User-agent: *
Crawl-delay: 5
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert result.crawl_delay == 5

    def test_parse_crawl_delay_float(self) -> None:
        """Parse Crawl-delay as float."""
        content = """
User-agent: *
Crawl-delay: 2.5
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert result.crawl_delay == 2.5

    def test_parse_empty_content(self) -> None:
        """Parse empty robots.txt."""
        content = ""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert len(result.rules) == 0
        assert len(result.sitemaps) == 0

    def test_parse_disallow_all(self) -> None:
        """Parse Disallow: / (block all)."""
        content = """
User-agent: *
Disallow: /
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any(r.path == "/" and not r.allow for r in result.rules)

    def test_parse_allow_all(self) -> None:
        """Parse Disallow: (empty, allow all)."""
        content = """
User-agent: *
Disallow:
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        # Empty Disallow means allow all
        assert len([r for r in result.rules if not r.allow]) == 0

    def test_parse_with_comments(self) -> None:
        """Parse robots.txt with comments."""
        content = """
# This is a comment
User-agent: *  # Another comment
Disallow: /admin  # Block admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any(r.path == "/admin" for r in result.rules)

    def test_parse_case_insensitive_directives(self) -> None:
        """Directives should be case-insensitive."""
        content = """
USER-AGENT: *
DISALLOW: /admin
ALLOW: /admin/public
SITEMAP: https://example.com/sitemap.xml
CRAWL-DELAY: 3
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any(r.path == "/admin" for r in result.rules)
        assert "https://example.com/sitemap.xml" in result.sitemaps
        assert result.crawl_delay == 3

    def test_parse_wildcard_patterns(self) -> None:
        """Parse wildcard patterns in paths."""
        content = """
User-agent: *
Disallow: /*.pdf
Disallow: /search?*
Allow: /search?q=*
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any("*.pdf" in r.path for r in result.rules)
        assert any("search?" in r.path for r in result.rules)

    def test_parse_end_of_match(self) -> None:
        """Parse $ end-of-match patterns."""
        content = """
User-agent: *
Disallow: /*.pdf$
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any(".pdf$" in r.path for r in result.rules)


class TestIsAllowed:
    """Tests for URL allowance checking."""

    def test_allowed_no_rules(self) -> None:
        """URL should be allowed if no rules match."""
        content = """
User-agent: *
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/public", result) is True

    def test_disallowed_exact_match(self) -> None:
        """URL should be disallowed on exact match."""
        content = """
User-agent: *
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/admin", result) is False

    def test_disallowed_prefix_match(self) -> None:
        """URL should be disallowed on prefix match."""
        content = """
User-agent: *
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/admin/users", result) is False
        assert is_allowed("/admin/", result) is False

    def test_allow_overrides_disallow(self) -> None:
        """More specific Allow should override Disallow."""
        content = """
User-agent: *
Disallow: /admin
Allow: /admin/login
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/admin", result) is False
        assert is_allowed("/admin/login", result) is True

    def test_disallow_root_blocks_all(self) -> None:
        """Disallow: / should block all paths."""
        content = """
User-agent: *
Disallow: /
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/", result) is False
        assert is_allowed("/anything", result) is False
        assert is_allowed("/deep/path/here", result) is False

    def test_longer_path_wins(self) -> None:
        """Longer matching path should take precedence."""
        content = """
User-agent: *
Disallow: /directory
Allow: /directory/page
Disallow: /directory/page/blocked
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/directory", result) is False
        assert is_allowed("/directory/page", result) is True
        assert is_allowed("/directory/page/blocked", result) is False

    def test_wildcard_pattern_matching(self) -> None:
        """Wildcard patterns should be matched correctly."""
        content = """
User-agent: *
Disallow: /*.pdf
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/document.pdf", result) is False
        assert is_allowed("/docs/file.pdf", result) is False
        assert is_allowed("/document.html", result) is True

    def test_end_of_match_pattern(self) -> None:
        """End-of-match pattern ($) should work correctly."""
        content = """
User-agent: *
Disallow: /*.pdf$
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert is_allowed("/document.pdf", result) is False
        assert is_allowed("/document.pdf?query=1", result) is True  # Not ending with .pdf


class TestRobotsParser:
    """Tests for RobotsParser class."""

    @pytest.mark.asyncio
    async def test_parser_caches_robots_txt(self) -> None:
        """Parser should cache robots.txt per domain."""
        robots_content = """
User-agent: *
Disallow: /admin
"""
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = robots_content

            parser = RobotsParser()
            await parser.fetch("https://example.com/page")
            await parser.fetch("https://example.com/other")

            # Should only fetch once for same domain
            assert mock_fetch.call_count == 1

    @pytest.mark.asyncio
    async def test_parser_respects_bypass_setting(self) -> None:
        """Parser should bypass robots.txt when respect_robots=False."""
        settings = RobotsSettings(respect_robots=False)
        parser = RobotsParser(settings=settings)

        # Should always return allowed without fetching
        result = await parser.is_allowed("https://example.com/blocked")
        assert result is True

    @pytest.mark.asyncio
    async def test_parser_handles_fetch_error(self) -> None:
        """Parser should allow crawling if robots.txt fetch fails."""
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.side_effect = Exception("Network error")

            parser = RobotsParser()
            result = await parser.is_allowed("https://example.com/page")

            # Should default to allowed on error
            assert result is True

    @pytest.mark.asyncio
    async def test_parser_returns_sitemaps(self) -> None:
        """Parser should return sitemap URLs from robots.txt."""
        robots_content = """
User-agent: *
Disallow: /admin

Sitemap: https://example.com/sitemap.xml
Sitemap: https://example.com/sitemap2.xml
"""
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = robots_content

            parser = RobotsParser()
            sitemaps = await parser.get_sitemaps("https://example.com")

            assert "https://example.com/sitemap.xml" in sitemaps
            assert "https://example.com/sitemap2.xml" in sitemaps

    @pytest.mark.asyncio
    async def test_parser_returns_crawl_delay(self) -> None:
        """Parser should return crawl delay from robots.txt."""
        robots_content = """
User-agent: *
Crawl-delay: 5
Disallow: /admin
"""
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = robots_content

            parser = RobotsParser()
            delay = await parser.get_crawl_delay("https://example.com")

            assert delay == 5

    @pytest.mark.asyncio
    async def test_parser_handles_404_robots(self) -> None:
        """Parser should allow all if robots.txt returns 404."""
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = None  # Indicates 404

            parser = RobotsParser()
            result = await parser.is_allowed("https://example.com/anything")

            assert result is True

    @pytest.mark.asyncio
    async def test_parser_different_domains_separate_cache(self) -> None:
        """Parser should cache separately for different domains."""
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = "User-agent: *\nDisallow: /admin"

            parser = RobotsParser()
            await parser.fetch("https://example.com/page")
            await parser.fetch("https://other.com/page")

            # Should fetch twice for different domains
            assert mock_fetch.call_count == 2

    @pytest.mark.asyncio
    async def test_parser_clear_cache(self) -> None:
        """Parser should allow clearing the cache."""
        robots_content = "User-agent: *\nDisallow: /admin"
        with patch("semrush_seo.robots.fetch_robots_txt") as mock_fetch:
            mock_fetch.return_value = robots_content

            parser = RobotsParser()
            await parser.fetch("https://example.com/page")
            parser.clear_cache()
            await parser.fetch("https://example.com/page")

            # Should fetch twice after cache clear
            assert mock_fetch.call_count == 2


class TestRobotsEdgeCases:
    """Tests for edge cases."""

    def test_parse_malformed_robots(self) -> None:
        """Parser should handle malformed robots.txt gracefully."""
        content = """
This is not valid robots.txt
Random text here
User-agent: *
Disallow: /admin
More random text
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        # Should still extract valid rules
        assert any(r.path == "/admin" for r in result.rules)

    def test_parse_unicode_content(self) -> None:
        """Parser should handle Unicode content."""
        content = """
# Unicode comment: robots.txt
User-agent: *
Disallow: /admin
"""
        result = parse_robots_txt(content, user_agent="Openahrush")
        assert any(r.path == "/admin" for r in result.rules)

    def test_parse_very_long_robots(self) -> None:
        """Parser should handle very long robots.txt."""
        content = "User-agent: *\n"
        for i in range(1000):
            content += f"Disallow: /path{i}\n"

        result = parse_robots_txt(content, user_agent="Openahrush")
        assert len(result.rules) == 1000

    def test_user_agent_partial_match(self) -> None:
        """User-Agent matching should be case-insensitive substring match."""
        content = """
User-agent: openahrush
Disallow: /blocked

User-agent: *
Disallow: /other
"""
        # Should match case-insensitively
        result = parse_robots_txt(content, user_agent="Openahrush")
        paths = [r.path for r in result.rules]
        assert "/blocked" in paths
