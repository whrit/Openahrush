"""
robots.txt parser and URL allowance checker.

Provides parsing and caching of robots.txt files with:
- User-Agent matching (specific and wildcard)
- Allow/Disallow rule parsing
- Crawl-delay extraction
- Sitemap URL discovery
- Configurable bypass option
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

import httpx


@dataclass
class RobotsSettings:
    """
    Configuration settings for robots.txt parsing.

    Attributes:
        user_agent: User-Agent name to match rules against.
        respect_robots: Whether to respect robots.txt (if False, always allow).
        cache_ttl_seconds: How long to cache robots.txt files.
    """

    user_agent: str = "Openahrush"
    respect_robots: bool = True
    cache_ttl_seconds: int = 3600


@dataclass
class RobotsRule:
    """
    A single robots.txt rule.

    Attributes:
        path: The path pattern from Allow/Disallow directive.
        allow: True for Allow, False for Disallow.
    """

    path: str
    allow: bool


@dataclass
class RobotsData:
    """
    Parsed robots.txt data.

    Attributes:
        rules: List of Allow/Disallow rules for the matched User-Agent.
        sitemaps: List of sitemap URLs found.
        crawl_delay: Crawl-delay value in seconds (if specified).
    """

    rules: list[RobotsRule] = field(default_factory=list)
    sitemaps: list[str] = field(default_factory=list)
    crawl_delay: float | None = None


async def fetch_robots_txt(url: str, timeout: float = 10.0) -> str | None:
    """
    Fetch robots.txt for a domain.

    Args:
        url: Any URL on the domain (will extract base URL).
        timeout: Request timeout in seconds.

    Returns:
        robots.txt content as string, or None if not found/error.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(robots_url)
            if response.status_code == 200:
                return response.text
            return None
    except Exception:
        return None


def parse_robots_txt(content: str, user_agent: str) -> RobotsData:
    """
    Parse robots.txt content for a specific User-Agent.

    Implements robots.txt parsing according to the standard,
    with case-insensitive directive matching and User-Agent
    substring matching.

    Args:
        content: robots.txt file content.
        user_agent: User-Agent name to match rules for.

    Returns:
        RobotsData with rules, sitemaps, and crawl-delay.
    """
    if not content:
        return RobotsData()

    lines = content.split("\n")
    user_agent_lower = user_agent.lower()

    # Parse all user-agent blocks
    current_agents: list[str] = []
    agent_rules: dict[str, list[RobotsRule]] = {}
    agent_crawl_delays: dict[str, float] = {}
    all_sitemaps: list[str] = []

    for line in lines:
        # Remove comments
        comment_idx = line.find("#")
        if comment_idx >= 0:
            line = line[:comment_idx]

        line = line.strip()
        if not line:
            continue

        # Parse directive
        if ":" not in line:
            continue

        directive, _, value = line.partition(":")
        directive = directive.strip().lower()
        value = value.strip()

        if directive == "user-agent":
            # Start new agent block or add to current
            agent_name = value.lower()
            if not current_agents or (current_agents and agent_name not in current_agents):
                if current_agents:
                    # Previous block ended, start fresh
                    current_agents = []
            current_agents.append(agent_name)
            if agent_name not in agent_rules:
                agent_rules[agent_name] = []

        elif directive == "disallow":
            if value:  # Empty disallow means allow all
                for agent in current_agents:
                    agent_rules.setdefault(agent, []).append(
                        RobotsRule(path=value, allow=False)
                    )

        elif directive == "allow":
            if value:
                for agent in current_agents:
                    agent_rules.setdefault(agent, []).append(
                        RobotsRule(path=value, allow=True)
                    )

        elif directive == "crawl-delay":
            try:
                delay = float(value)
                for agent in current_agents:
                    agent_crawl_delays[agent] = delay
            except ValueError:
                pass

        elif directive == "sitemap":
            if value:
                all_sitemaps.append(value)

    # Find matching rules for user-agent
    # Priority: exact match > partial match > wildcard
    matched_rules: list[RobotsRule] = []
    matched_delay: float | None = None

    # Check for exact/substring match first
    for agent_name, rules in agent_rules.items():
        if agent_name == "*":
            continue  # Handle wildcard last
        if user_agent_lower in agent_name or agent_name in user_agent_lower:
            matched_rules = rules
            matched_delay = agent_crawl_delays.get(agent_name)
            break

    # Fall back to wildcard if no specific match
    if not matched_rules and "*" in agent_rules:
        matched_rules = agent_rules["*"]
        matched_delay = agent_crawl_delays.get("*")

    return RobotsData(
        rules=matched_rules,
        sitemaps=all_sitemaps,
        crawl_delay=matched_delay,
    )


def _path_matches(path: str, pattern: str) -> bool:
    """
    Check if a path matches a robots.txt pattern.

    Supports:
    - Prefix matching
    - * wildcard (matches any sequence)
    - $ end-of-string anchor

    Args:
        path: The URL path to check.
        pattern: The robots.txt pattern.

    Returns:
        True if path matches pattern.
    """
    # Handle end-of-match anchor
    if pattern.endswith("$"):
        pattern = pattern[:-1]
        # Path must end with pattern (after wildcards expanded)
        if "*" in pattern:
            # Convert to regex for complex matching
            regex_pattern = re.escape(pattern).replace(r"\*", ".*")
            regex_pattern = regex_pattern + "$"
            return bool(re.match(regex_pattern, path))
        else:
            return path.endswith(pattern) or path == pattern
    elif "*" in pattern:
        # Wildcard pattern without $
        regex_pattern = re.escape(pattern).replace(r"\*", ".*")
        return bool(re.match(regex_pattern, path))
    else:
        # Simple prefix match
        return path.startswith(pattern)


def is_allowed(path: str, robots_data: RobotsData) -> bool:
    """
    Check if a path is allowed based on robots.txt rules.

    Implements the precedence rules:
    1. Most specific (longest) matching rule wins
    2. If same length, Allow takes precedence over Disallow

    Args:
        path: URL path to check (e.g., "/admin/users").
        robots_data: Parsed robots.txt data.

    Returns:
        True if path is allowed, False otherwise.
    """
    if not robots_data.rules:
        return True

    # Ensure path starts with /
    if not path.startswith("/"):
        path = "/" + path

    # Find all matching rules
    matching_rules: list[tuple[int, bool, str]] = []

    for rule in robots_data.rules:
        if _path_matches(path, rule.path):
            # Store (path_length, is_allow, path) for sorting
            matching_rules.append((len(rule.path), rule.allow, rule.path))

    if not matching_rules:
        return True  # No matching rules = allowed

    # Sort by path length (longest first), then by allow (True before False)
    matching_rules.sort(key=lambda x: (-x[0], not x[1]))

    # Return the allow value of the most specific match
    return matching_rules[0][1]


@dataclass
class CacheEntry:
    """Cache entry for robots.txt data."""

    data: RobotsData
    fetched_at: float


class RobotsParser:
    """
    Robots.txt parser with caching.

    Fetches, parses, and caches robots.txt files per domain.
    Provides URL allowance checking respecting the configured User-Agent.

    Usage:
        parser = RobotsParser()
        if await parser.is_allowed("https://example.com/page"):
            # crawl the page
    """

    def __init__(self, settings: RobotsSettings | None = None) -> None:
        """
        Initialize the robots.txt parser.

        Args:
            settings: Optional RobotsSettings configuration.
        """
        self.settings = settings or RobotsSettings()
        self._cache: dict[str, CacheEntry] = {}

    def _get_domain(self, url: str) -> str:
        """Extract domain from URL for caching."""
        parsed = urlparse(url)
        return f"{parsed.scheme}://{parsed.netloc}"

    def _is_cache_valid(self, entry: CacheEntry) -> bool:
        """Check if cache entry is still valid."""
        return (time.time() - entry.fetched_at) < self.settings.cache_ttl_seconds

    async def fetch(self, url: str) -> RobotsData:
        """
        Fetch and parse robots.txt for a URL's domain.

        Uses caching to avoid repeated fetches.

        Args:
            url: Any URL on the domain.

        Returns:
            Parsed RobotsData for the domain.
        """
        domain = self._get_domain(url)

        # Check cache
        if domain in self._cache:
            entry = self._cache[domain]
            if self._is_cache_valid(entry):
                return entry.data

        # Fetch and parse
        try:
            content = await fetch_robots_txt(url)
            if content is None:
                # No robots.txt or error - allow everything
                data = RobotsData()
            else:
                data = parse_robots_txt(content, self.settings.user_agent)
        except Exception:
            # On error, default to allowing
            data = RobotsData()

        # Cache result
        self._cache[domain] = CacheEntry(data=data, fetched_at=time.time())
        return data

    async def is_allowed(self, url: str) -> bool:
        """
        Check if a URL is allowed to be crawled.

        Args:
            url: Full URL to check.

        Returns:
            True if URL is allowed, False otherwise.
        """
        # Bypass if not respecting robots
        if not self.settings.respect_robots:
            return True

        try:
            robots_data = await self.fetch(url)
            parsed = urlparse(url)
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            return is_allowed(path, robots_data)
        except Exception:
            # On error, default to allowed
            return True

    async def get_sitemaps(self, url: str) -> list[str]:
        """
        Get sitemap URLs from robots.txt.

        Args:
            url: Any URL on the domain.

        Returns:
            List of sitemap URLs found in robots.txt.
        """
        robots_data = await self.fetch(url)
        return robots_data.sitemaps

    async def get_crawl_delay(self, url: str) -> float | None:
        """
        Get crawl-delay from robots.txt.

        Args:
            url: Any URL on the domain.

        Returns:
            Crawl-delay in seconds, or None if not specified.
        """
        robots_data = await self.fetch(url)
        return robots_data.crawl_delay

    def clear_cache(self) -> None:
        """Clear the robots.txt cache."""
        self._cache.clear()
