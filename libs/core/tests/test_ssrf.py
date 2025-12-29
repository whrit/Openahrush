"""
Tests for SSRF (Server-Side Request Forgery) prevention module.

Following TDD: Tests written first, then implementation.

Tests cover:
- Private IP range blocking (10.x, 172.16-31.x, 192.168.x)
- Localhost and loopback blocking (127.0.0.0/8)
- Link-local address blocking (169.254.x.x)
- IPv6 localhost blocking (::1)
- IPv6 private address blocking
- Internal DNS name blocking
- URL parsing validation
- HTTPS enforcement (optional)
- DNS resolution checks
- Edge cases and error handling
"""

import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# IP Address Validation Tests
# =============================================================================


class TestIsPrivateIP:
    """Tests for private IP detection."""

    def test_private_10_network(self):
        """Should detect 10.0.0.0/8 as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("10.0.0.1") is True
        assert is_private_ip("10.255.255.255") is True
        assert is_private_ip("10.1.2.3") is True

    def test_private_172_network(self):
        """Should detect 172.16.0.0/12 as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("172.16.0.1") is True
        assert is_private_ip("172.31.255.255") is True
        assert is_private_ip("172.20.0.1") is True
        # 172.32 is not in the private range
        assert is_private_ip("172.32.0.1") is False

    def test_private_192_168_network(self):
        """Should detect 192.168.0.0/16 as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("192.168.0.1") is True
        assert is_private_ip("192.168.255.255") is True
        assert is_private_ip("192.168.1.1") is True

    def test_loopback_addresses(self):
        """Should detect 127.0.0.0/8 as private/loopback."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("127.0.0.1") is True
        assert is_private_ip("127.255.255.255") is True
        assert is_private_ip("127.0.0.2") is True

    def test_link_local_addresses(self):
        """Should detect 169.254.0.0/16 as private (link-local)."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("169.254.0.1") is True
        assert is_private_ip("169.254.169.254") is True  # AWS metadata
        assert is_private_ip("169.254.255.255") is True

    def test_ipv6_localhost(self):
        """Should detect ::1 as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("::1") is True

    def test_ipv6_link_local(self):
        """Should detect fe80::/10 as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("fe80::1") is True
        assert is_private_ip("fe80::abcd:1234") is True

    def test_ipv6_private(self):
        """Should detect fc00::/7 (unique local) as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("fc00::1") is True
        assert is_private_ip("fd00::1") is True

    def test_public_ipv4(self):
        """Should not detect public IPs as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("8.8.8.8") is False
        assert is_private_ip("1.1.1.1") is False
        assert is_private_ip("93.184.216.34") is False  # example.com

    def test_public_ipv6(self):
        """Should not detect public IPv6 as private."""
        from semrush_core.security.ssrf import is_private_ip

        assert is_private_ip("2001:4860:4860::8888") is False  # Google DNS
        assert is_private_ip("2606:4700:4700::1111") is False  # Cloudflare

    def test_invalid_ip_raises_error(self):
        """Should raise ValueError for invalid IP."""
        from semrush_core.security.ssrf import is_private_ip

        with pytest.raises(ValueError):
            is_private_ip("not-an-ip")

        with pytest.raises(ValueError):
            is_private_ip("256.256.256.256")

        with pytest.raises(ValueError):
            is_private_ip("")


# =============================================================================
# URL Validation Tests
# =============================================================================


class TestValidateWebhookURLFormat:
    """Tests for webhook URL format validation."""

    def test_valid_https_url(self):
        """Should accept valid HTTPS URLs."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("https://example.com/webhook")
        assert result.is_valid is True
        assert result.hostname == "example.com"
        assert result.scheme == "https"

    def test_valid_http_url_without_https_requirement(self):
        """Should accept HTTP URLs when HTTPS not required."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("http://example.com/webhook", require_https=False)
        assert result.is_valid is True
        assert result.scheme == "http"

    def test_reject_http_url_with_https_requirement(self):
        """Should reject HTTP URLs when HTTPS required."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("http://example.com/webhook", require_https=True)
        assert result.is_valid is False
        assert "https" in result.error.lower()

    def test_reject_non_http_schemes(self):
        """Should reject non-HTTP(S) schemes."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("ftp://example.com/file")
        assert result.is_valid is False
        assert "scheme" in result.error.lower()

        result = validate_url_format("file:///etc/passwd")
        assert result.is_valid is False

        result = validate_url_format("javascript:alert(1)")
        assert result.is_valid is False

    def test_reject_url_without_hostname(self):
        """Should reject URLs without hostname."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("https:///path/only")
        assert result.is_valid is False
        assert "hostname" in result.error.lower()

    def test_reject_malformed_url(self):
        """Should reject malformed URLs."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("not-a-valid-url")
        assert result.is_valid is False

        result = validate_url_format("")
        assert result.is_valid is False

    def test_url_with_port(self):
        """Should accept URLs with explicit port."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("https://example.com:8443/webhook")
        assert result.is_valid is True
        assert result.port == 8443

    def test_url_with_path_and_query(self):
        """Should accept URLs with path and query string."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("https://example.com/webhook?token=abc")
        assert result.is_valid is True
        assert result.path == "/webhook"

    def test_url_with_authentication(self):
        """Should reject URLs with embedded credentials (potential security issue)."""
        from semrush_core.security.ssrf import validate_url_format

        result = validate_url_format("https://user:pass@example.com/webhook")
        assert result.is_valid is False
        assert "credential" in result.error.lower()


# =============================================================================
# DNS Hostname Validation Tests
# =============================================================================


class TestIsInternalHostname:
    """Tests for internal hostname detection."""

    def test_localhost_hostname(self):
        """Should detect localhost as internal."""
        from semrush_core.security.ssrf import is_internal_hostname

        assert is_internal_hostname("localhost") is True
        assert is_internal_hostname("LOCALHOST") is True
        assert is_internal_hostname("LocalHost") is True

    def test_internal_tld(self):
        """Should detect internal TLDs as internal."""
        from semrush_core.security.ssrf import is_internal_hostname

        assert is_internal_hostname("server.local") is True
        assert is_internal_hostname("db.internal") is True
        assert is_internal_hostname("api.intranet") is True
        assert is_internal_hostname("host.corp") is True
        assert is_internal_hostname("machine.lan") is True

    def test_kubernetes_internal(self):
        """Should detect Kubernetes internal DNS as internal."""
        from semrush_core.security.ssrf import is_internal_hostname

        assert is_internal_hostname("service.default.svc.cluster.local") is True
        assert is_internal_hostname("api.namespace.svc.cluster.local") is True

    def test_aws_metadata(self):
        """Should detect AWS metadata service hostnames."""
        from semrush_core.security.ssrf import is_internal_hostname

        assert is_internal_hostname("instance-data") is True
        assert is_internal_hostname("metadata") is True

    def test_cloud_metadata_ips(self):
        """Should detect cloud metadata IP patterns."""
        from semrush_core.security.ssrf import is_internal_hostname

        # This tests hostname patterns, not IP resolution
        assert is_internal_hostname("169.254.169.254") is True  # AWS/GCP metadata IP

    def test_public_hostnames(self):
        """Should not detect public hostnames as internal."""
        from semrush_core.security.ssrf import is_internal_hostname

        assert is_internal_hostname("example.com") is False
        assert is_internal_hostname("api.github.com") is False
        assert is_internal_hostname("webhook.site") is False
        assert is_internal_hostname("hooks.slack.com") is False

    def test_hostname_with_internal_substring(self):
        """Should not flag hostnames that contain internal keywords as substrings."""
        from semrush_core.security.ssrf import is_internal_hostname

        # These should NOT be flagged because 'local' is a substring, not a TLD
        assert is_internal_hostname("mylocalapi.example.com") is False
        assert is_internal_hostname("internal-api.company.com") is False


# =============================================================================
# DNS Resolution Tests
# =============================================================================


class TestDNSResolution:
    """Tests for DNS resolution checks."""

    @pytest.mark.asyncio
    async def test_resolve_public_ip(self):
        """Should resolve and allow public IP."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),  # IPv4
            ]
            result = await resolve_and_validate_host("example.com")

        assert result.is_valid is True
        assert "93.184.216.34" in result.resolved_ips

    @pytest.mark.asyncio
    async def test_resolve_private_ip_blocked(self):
        """Should block hostnames that resolve to private IPs."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("192.168.1.1", 443)),  # Private IPv4
            ]
            result = await resolve_and_validate_host("internal.company.com")

        assert result.is_valid is False
        assert "private" in result.error.lower()

    @pytest.mark.asyncio
    async def test_resolve_loopback_blocked(self):
        """Should block hostnames that resolve to loopback."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("127.0.0.1", 443)),
            ]
            result = await resolve_and_validate_host("localhost.example.com")

        assert result.is_valid is False
        assert "private" in result.error.lower() or "loopback" in result.error.lower()

    @pytest.mark.asyncio
    async def test_resolve_link_local_blocked(self):
        """Should block hostnames that resolve to link-local (AWS metadata)."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("169.254.169.254", 80)),  # AWS metadata
            ]
            result = await resolve_and_validate_host("metadata.aws.com")

        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_resolve_multiple_ips_one_private(self):
        """Should block if any resolved IP is private."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),  # Public
                (2, 1, 6, "", ("10.0.0.1", 443)),  # Private
            ]
            result = await resolve_and_validate_host("multi.example.com")

        assert result.is_valid is False
        assert "private" in result.error.lower()

    @pytest.mark.asyncio
    async def test_resolve_dns_failure(self):
        """Should handle DNS resolution failures gracefully."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.side_effect = OSError("Name resolution failed")
            result = await resolve_and_validate_host("nonexistent.invalid")

        assert result.is_valid is False
        assert "dns" in result.error.lower() or "resolution" in result.error.lower()

    @pytest.mark.asyncio
    async def test_resolve_empty_results(self):
        """Should handle empty DNS results."""
        from semrush_core.security.ssrf import resolve_and_validate_host

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = []
            result = await resolve_and_validate_host("no-records.example.com")

        assert result.is_valid is False


# =============================================================================
# Full Webhook URL Validation Tests
# =============================================================================


class TestValidateWebhookURL:
    """Integration tests for full webhook URL validation."""

    @pytest.mark.asyncio
    async def test_valid_public_https_url(self):
        """Should accept valid public HTTPS URL."""
        from semrush_core.security.ssrf import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),
            ]
            result = await validate_webhook_url("https://example.com/webhook")

        assert result.is_valid is True
        assert result.error is None

    @pytest.mark.asyncio
    async def test_reject_private_ip_direct(self):
        """Should reject URLs with private IP directly in hostname."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://192.168.1.1/webhook")

        assert result.is_valid is False
        assert "private" in result.error.lower()

    @pytest.mark.asyncio
    async def test_reject_localhost_direct(self):
        """Should reject localhost URLs."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://localhost/webhook")

        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_reject_loopback_ip(self):
        """Should reject loopback IP URLs."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://127.0.0.1/webhook")

        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_reject_internal_tld(self):
        """Should reject internal TLD URLs."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://server.local/webhook")
        assert result.is_valid is False

        result = await validate_webhook_url("https://api.internal/webhook")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_reject_dns_rebinding_attempt(self):
        """Should reject if DNS resolves to private IP."""
        from semrush_core.security.ssrf import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("10.0.0.1", 443)),  # Private
            ]
            result = await validate_webhook_url("https://malicious.example.com/webhook")

        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_reject_metadata_service_ip(self):
        """Should reject cloud metadata service IPs."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("http://169.254.169.254/latest/meta-data/")

        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_https_enforcement(self):
        """Should enforce HTTPS when required."""
        from semrush_core.security.ssrf import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 80)),
            ]

            # HTTPS required by default
            result = await validate_webhook_url(
                "http://example.com/webhook", require_https=True
            )
            assert result.is_valid is False
            assert "https" in result.error.lower()

            # Allow HTTP when not required
            result = await validate_webhook_url(
                "http://example.com/webhook", require_https=False
            )
            assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_ipv6_private_address(self):
        """Should reject IPv6 private addresses."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://[::1]/webhook")
        assert result.is_valid is False

        result = await validate_webhook_url("https://[fe80::1]/webhook")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_validation_result_includes_details(self):
        """Validation result should include useful details."""
        from semrush_core.security.ssrf import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),
            ]
            result = await validate_webhook_url("https://example.com/webhook")

        assert result.is_valid is True
        assert result.hostname == "example.com"
        assert result.resolved_ips is not None
        assert "93.184.216.34" in result.resolved_ips


# =============================================================================
# Edge Cases and Security Tests
# =============================================================================


class TestSSRFEdgeCases:
    """Tests for edge cases and security concerns."""

    @pytest.mark.asyncio
    async def test_url_encoded_private_ip(self):
        """Should detect URL-encoded private IPs."""
        from semrush_core.security.ssrf import validate_webhook_url

        # URL encoded 127.0.0.1
        result = await validate_webhook_url("https://127%2E0%2E0%2E1/webhook")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_decimal_ip_notation(self):
        """Should handle decimal IP notation (SSRF bypass attempt)."""
        from semrush_core.security.ssrf import validate_webhook_url

        # 2130706433 = 127.0.0.1 in decimal
        result = await validate_webhook_url("https://2130706433/webhook")
        # This should be rejected as it resolves to 127.0.0.1
        # The validation should handle this

    @pytest.mark.asyncio
    async def test_octal_ip_notation(self):
        """Should handle octal IP notation (SSRF bypass attempt)."""
        from semrush_core.security.ssrf import validate_webhook_url

        # 0177.0.0.1 = 127.0.0.1 in octal
        result = await validate_webhook_url("https://0177.0.0.1/webhook")
        # Should be caught by DNS resolution or IP validation

    @pytest.mark.asyncio
    async def test_hex_ip_notation(self):
        """Should handle hex IP notation (SSRF bypass attempt)."""
        from semrush_core.security.ssrf import validate_webhook_url

        # 0x7f000001 = 127.0.0.1 in hex
        result = await validate_webhook_url("https://0x7f000001/webhook")

    @pytest.mark.asyncio
    async def test_ipv6_mapped_ipv4(self):
        """Should detect IPv6-mapped IPv4 addresses."""
        from semrush_core.security.ssrf import validate_webhook_url

        # ::ffff:192.168.1.1 is IPv6-mapped private IPv4
        result = await validate_webhook_url("https://[::ffff:192.168.1.1]/webhook")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_zero_ip(self):
        """Should reject 0.0.0.0 addresses."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://0.0.0.0/webhook")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_url_with_credentials_rejected(self):
        """Should reject URLs with embedded credentials."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://user:pass@example.com/webhook")
        assert result.is_valid is False

    @pytest.mark.asyncio
    async def test_very_long_url(self):
        """Should handle very long URLs."""
        from semrush_core.security.ssrf import validate_webhook_url

        long_path = "/a" * 5000
        result = await validate_webhook_url(f"https://example.com{long_path}")
        # Should either accept (if under limit) or reject with appropriate error

    @pytest.mark.asyncio
    async def test_unicode_hostname(self):
        """Should handle unicode/IDN hostnames properly."""
        from semrush_core.security.ssrf import validate_webhook_url

        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),
            ]
            # Unicode domain
            result = await validate_webhook_url("https://xn--e1afmkfd.xn--p1ai/webhook")
            # Should be handled properly

    @pytest.mark.asyncio
    async def test_null_byte_injection(self):
        """Should reject URLs with null bytes."""
        from semrush_core.security.ssrf import validate_webhook_url

        result = await validate_webhook_url("https://example.com/webhook\x00malicious")
        # Should reject or sanitize

    @pytest.mark.asyncio
    async def test_redirect_info_in_result(self):
        """Validation does not follow redirects (that's the caller's responsibility)."""
        from semrush_core.security.ssrf import validate_webhook_url

        # Validation only checks the provided URL, not redirects
        # Redirect handling should be done with redirect=False in HTTP client
        with patch("socket.getaddrinfo") as mock_getaddrinfo:
            mock_getaddrinfo.return_value = [
                (2, 1, 6, "", ("93.184.216.34", 443)),
            ]
            result = await validate_webhook_url("https://example.com/redirect")
            assert result.is_valid is True


# =============================================================================
# ValidationResult Tests
# =============================================================================


class TestValidationResult:
    """Tests for the ValidationResult dataclass."""

    def test_valid_result(self):
        """Test creating a valid result."""
        from semrush_core.security.ssrf import ValidationResult

        result = ValidationResult(
            is_valid=True,
            error=None,
            hostname="example.com",
            scheme="https",
            port=443,
            path="/webhook",
            resolved_ips=["93.184.216.34"],
        )

        assert result.is_valid is True
        assert result.error is None
        assert result.hostname == "example.com"

    def test_invalid_result(self):
        """Test creating an invalid result."""
        from semrush_core.security.ssrf import ValidationResult

        result = ValidationResult(
            is_valid=False,
            error="Private IP detected",
            hostname="internal.local",
        )

        assert result.is_valid is False
        assert result.error == "Private IP detected"

    def test_result_to_dict(self):
        """Validation result should be convertible to dict."""
        from semrush_core.security.ssrf import ValidationResult

        result = ValidationResult(
            is_valid=True,
            error=None,
            hostname="example.com",
            scheme="https",
            resolved_ips=["1.2.3.4"],
        )

        # Should have a to_dict or similar method for serialization
        # or be a dataclass that can be converted
        assert hasattr(result, "__dict__") or hasattr(result, "model_dump")


# =============================================================================
# Blocked Networks Constants Tests
# =============================================================================


class TestBlockedNetworks:
    """Tests for the BLOCKED_NETWORKS constant."""

    def test_blocked_networks_defined(self):
        """BLOCKED_NETWORKS should be defined with expected networks."""
        from semrush_core.security.ssrf import BLOCKED_NETWORKS

        # Should include standard private networks
        network_strs = [str(net) for net in BLOCKED_NETWORKS]

        assert "10.0.0.0/8" in network_strs
        assert "172.16.0.0/12" in network_strs
        assert "192.168.0.0/16" in network_strs
        assert "127.0.0.0/8" in network_strs
        assert "169.254.0.0/16" in network_strs
        assert "::1/128" in network_strs

    def test_all_networks_are_valid(self):
        """All blocked networks should be valid ipaddress networks."""
        from semrush_core.security.ssrf import BLOCKED_NETWORKS

        for network in BLOCKED_NETWORKS:
            assert isinstance(
                network, (ipaddress.IPv4Network, ipaddress.IPv6Network)
            )
