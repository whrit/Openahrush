"""
SSRF (Server-Side Request Forgery) prevention module.

Provides comprehensive URL validation to prevent SSRF attacks via webhook URLs.
Blocks private IP ranges, localhost, internal DNS names, and cloud metadata services.

Usage:
    from semrush_core.security.ssrf import validate_webhook_url

    result = await validate_webhook_url("https://example.com/webhook")
    if not result.is_valid:
        raise ValueError(f"Invalid webhook URL: {result.error}")
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass, field
from urllib.parse import urlparse

# Blocked IP networks - private ranges and special addresses
BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    # IPv4 private ranges
    ipaddress.ip_network("10.0.0.0/8"),  # Class A private
    ipaddress.ip_network("172.16.0.0/12"),  # Class B private
    ipaddress.ip_network("192.168.0.0/16"),  # Class C private
    ipaddress.ip_network("127.0.0.0/8"),  # Loopback
    ipaddress.ip_network("169.254.0.0/16"),  # Link-local (AWS metadata)
    ipaddress.ip_network("0.0.0.0/8"),  # Current network
    # IPv6 special addresses
    ipaddress.ip_network("::1/128"),  # Localhost
    ipaddress.ip_network("fe80::/10"),  # Link-local
    ipaddress.ip_network("fc00::/7"),  # Unique local (private)
    ipaddress.ip_network("::ffff:0:0/96"),  # IPv4-mapped IPv6 (validated separately)
]

# Internal TLDs and hostnames to block
INTERNAL_TLDS: set[str] = {
    "local",
    "internal",
    "intranet",
    "corp",
    "lan",
    "home",
    "localdomain",
    "localhost",
}

# Kubernetes internal DNS suffixes
KUBERNETES_SUFFIXES: list[str] = [
    ".svc.cluster.local",
    ".pod.cluster.local",
]

# Reserved/internal hostnames
RESERVED_HOSTNAMES: set[str] = {
    "localhost",
    "instance-data",  # AWS metadata
    "metadata",  # Cloud metadata
    "metadata.google.internal",
    "169.254.169.254",  # AWS/GCP metadata IP
}


@dataclass
class ValidationResult:
    """
    Result of URL validation.

    Attributes:
        is_valid: Whether the URL passed all security checks.
        error: Error message if validation failed, None otherwise.
        hostname: Extracted hostname from URL.
        scheme: URL scheme (http/https).
        port: Port number if specified.
        path: URL path component.
        resolved_ips: List of resolved IP addresses (if DNS resolution was performed).
    """

    is_valid: bool
    error: str | None = None
    hostname: str | None = None
    scheme: str | None = None
    port: int | None = None
    path: str | None = None
    resolved_ips: list[str] = field(default_factory=list)


def is_private_ip(ip_str: str) -> bool:
    """
    Check if an IP address is in a private/blocked network.

    Args:
        ip_str: IP address string (IPv4 or IPv6).

    Returns:
        True if the IP is private/blocked, False if public.

    Raises:
        ValueError: If the IP address is invalid.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError as e:
        raise ValueError(f"Invalid IP address: {ip_str}") from e

    # Check against all blocked networks
    for network in BLOCKED_NETWORKS:
        if ip in network:
            return True

    # Handle IPv6-mapped IPv4 addresses
    if isinstance(ip, ipaddress.IPv6Address):
        if ip.ipv4_mapped:
            # Check the underlying IPv4 address
            return is_private_ip(str(ip.ipv4_mapped))

    # Use built-in checks for additional coverage
    if ip.is_private:
        return True
    if ip.is_loopback:
        return True
    if ip.is_link_local:
        return True
    if ip.is_reserved:
        return True

    return bool(ip.is_unspecified)


def is_internal_hostname(hostname: str) -> bool:
    """
    Check if a hostname is an internal/reserved hostname.

    Args:
        hostname: Hostname to check.

    Returns:
        True if the hostname is internal/blocked.
    """
    hostname_lower = hostname.lower()

    # Check reserved hostnames
    if hostname_lower in RESERVED_HOSTNAMES:
        return True

    # Check if it's the metadata IP
    if hostname_lower == "169.254.169.254":
        return True

    # Check internal TLDs (must be the TLD, not a substring)
    parts = hostname_lower.split(".")
    if parts:
        tld = parts[-1]
        if tld in INTERNAL_TLDS:
            return True

    # Check Kubernetes internal DNS
    return any(hostname_lower.endswith(suffix) for suffix in KUBERNETES_SUFFIXES)


def validate_url_format(url: str, require_https: bool = False) -> ValidationResult:
    """
    Validate URL format and extract components.

    Args:
        url: URL string to validate.
        require_https: Whether to require HTTPS scheme.

    Returns:
        ValidationResult with parsed URL components.
    """
    if not url or not isinstance(url, str):
        return ValidationResult(
            is_valid=False,
            error="URL is required and must be a string",
        )

    # Check for null bytes (injection attempt)
    if "\x00" in url:
        return ValidationResult(
            is_valid=False,
            error="URL contains invalid characters",
        )

    try:
        parsed = urlparse(url)
    except Exception:
        return ValidationResult(
            is_valid=False,
            error="Malformed URL",
        )

    # Validate scheme
    if parsed.scheme not in ("http", "https"):
        return ValidationResult(
            is_valid=False,
            error=f"Invalid scheme: {parsed.scheme}. Only HTTP and HTTPS are allowed",
        )

    if require_https and parsed.scheme != "https":
        return ValidationResult(
            is_valid=False,
            error="HTTPS is required for webhook URLs",
        )

    # Validate hostname
    if not parsed.hostname:
        return ValidationResult(
            is_valid=False,
            error="URL must include a hostname",
        )

    # Check for embedded credentials (security risk)
    if parsed.username or parsed.password:
        return ValidationResult(
            is_valid=False,
            error="URLs with embedded credentials are not allowed",
        )

    # Extract port
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80

    return ValidationResult(
        is_valid=True,
        hostname=parsed.hostname,
        scheme=parsed.scheme,
        port=port,
        path=parsed.path or "/",
    )


async def resolve_and_validate_host(hostname: str) -> ValidationResult:
    """
    Resolve hostname via DNS and validate all resolved IPs.

    Args:
        hostname: Hostname to resolve.

    Returns:
        ValidationResult with resolved IPs or error.
    """
    # First check if hostname is already an IP address
    try:
        ipaddress.ip_address(hostname)
        # It's an IP, check it directly
        if is_private_ip(hostname):
            return ValidationResult(
                is_valid=False,
                error=f"Private/blocked IP address: {hostname}",
                hostname=hostname,
                resolved_ips=[hostname],
            )
        return ValidationResult(
            is_valid=True,
            hostname=hostname,
            resolved_ips=[hostname],
        )
    except ValueError:
        # Not an IP, proceed with DNS resolution
        pass

    # Check if hostname pattern is blocked before DNS resolution
    if is_internal_hostname(hostname):
        return ValidationResult(
            is_valid=False,
            error=f"Internal hostname not allowed: {hostname}",
            hostname=hostname,
        )

    # Perform DNS resolution
    try:
        # getaddrinfo returns list of (family, type, proto, canonname, sockaddr)
        addr_info = socket.getaddrinfo(
            hostname,
            None,
            socket.AF_UNSPEC,  # Allow both IPv4 and IPv6
            socket.SOCK_STREAM,
        )
    except socket.gaierror as e:
        return ValidationResult(
            is_valid=False,
            error=f"DNS resolution failed for {hostname}: {e}",
            hostname=hostname,
        )
    except OSError as e:
        return ValidationResult(
            is_valid=False,
            error=f"DNS resolution error for {hostname}: {e}",
            hostname=hostname,
        )

    if not addr_info:
        return ValidationResult(
            is_valid=False,
            error=f"No DNS records found for {hostname}",
            hostname=hostname,
        )

    # Extract and validate all resolved IPs
    resolved_ips: list[str] = []
    for info in addr_info:
        sockaddr = info[4]
        # sockaddr[0] is the IP address (str for AF_INET/AF_INET6)
        ip_str = str(sockaddr[0])

        if ip_str not in resolved_ips:
            resolved_ips.append(ip_str)

            # Check if any resolved IP is private
            try:
                if is_private_ip(ip_str):
                    return ValidationResult(
                        is_valid=False,
                        error=f"Hostname {hostname} resolves to private IP: {ip_str}",
                        hostname=hostname,
                        resolved_ips=resolved_ips,
                    )
            except ValueError:
                # Invalid IP from DNS (shouldn't happen but be safe)
                continue

    return ValidationResult(
        is_valid=True,
        hostname=hostname,
        resolved_ips=resolved_ips,
    )


async def validate_webhook_url(
    url: str,
    require_https: bool = False,
) -> ValidationResult:
    """
    Validate a webhook URL for SSRF vulnerabilities.

    Performs comprehensive security checks:
    1. URL format validation
    2. Scheme validation (HTTP/HTTPS)
    3. Hostname pattern checks (internal hostnames, TLDs)
    4. DNS resolution
    5. IP address validation (private ranges, localhost, link-local)

    Args:
        url: The webhook URL to validate.
        require_https: Whether to require HTTPS (recommended for production).

    Returns:
        ValidationResult indicating if the URL is safe to use.

    Example:
        >>> result = await validate_webhook_url("https://example.com/webhook")
        >>> if result.is_valid:
        ...     # Safe to use the URL
        ...     pass
        >>> else:
        ...     print(f"Rejected: {result.error}")
    """
    # Step 1: Validate URL format
    format_result = validate_url_format(url, require_https=require_https)
    if not format_result.is_valid:
        return format_result

    hostname = format_result.hostname
    if not hostname:
        return ValidationResult(
            is_valid=False,
            error="Could not extract hostname from URL",
        )

    # Step 2: Check if hostname is directly a private IP
    try:
        if is_private_ip(hostname):
            return ValidationResult(
                is_valid=False,
                error=f"Private/blocked IP address in URL: {hostname}",
                hostname=hostname,
                scheme=format_result.scheme,
                port=format_result.port,
                path=format_result.path,
            )
    except ValueError:
        # Not a valid IP, check as hostname
        pass

    # Step 3: Check internal hostname patterns
    if is_internal_hostname(hostname):
        return ValidationResult(
            is_valid=False,
            error=f"Internal hostname not allowed: {hostname}",
            hostname=hostname,
            scheme=format_result.scheme,
            port=format_result.port,
            path=format_result.path,
        )

    # Step 4: Resolve DNS and validate IPs
    dns_result = await resolve_and_validate_host(hostname)
    if not dns_result.is_valid:
        return ValidationResult(
            is_valid=False,
            error=dns_result.error,
            hostname=hostname,
            scheme=format_result.scheme,
            port=format_result.port,
            path=format_result.path,
            resolved_ips=dns_result.resolved_ips,
        )

    # All checks passed
    return ValidationResult(
        is_valid=True,
        hostname=hostname,
        scheme=format_result.scheme,
        port=format_result.port,
        path=format_result.path,
        resolved_ips=dns_result.resolved_ips,
    )
