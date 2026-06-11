"""
Security tests for Server-Side Request Forgery (SSRF) prevention.
Verifies that local network loopbacks, private CIDR blocks, and cloud metadata services are blocked.
"""
import pytest
from backend.ingestion.validators import validate_url


@pytest.mark.security
class TestSSRFPrevention:
    """Verifies protection against Server-Side Request Forgery (SSRF)."""

    def test_localhost_and_loopback_blocked(self):
        """Loopback IP and hostname requests must be blocked."""
        loopbacks = [
            "http://localhost/admin",
            "http://127.0.0.1/",
            "http://[::1]/",
            "http://127.0.0.2/",
            "http://localhost:8000/status"
        ]
        for url in loopbacks:
            valid, err = validate_url(url)
            assert valid is False, f"Failed to block loopback URL: {url}"
            assert "internal" in err.lower()

    def test_private_subnets_blocked(self):
        """Private CIDR subnets (RFC 1918) must be blocked."""
        private_subnets = [
            "http://10.0.0.1/metadata",
            "http://192.168.1.50/config",
            "http://172.16.5.5/",
            "http://172.31.255.255/"
        ]
        for url in private_subnets:
            valid, err = validate_url(url)
            assert valid is False, f"Failed to block private subnet URL: {url}"
            assert "internal" in err.lower()

    def test_cloud_metadata_services_blocked(self):
        """Cloud instance metadata services must be blocked."""
        metadata_urls = [
            "http://169.254.169.254/latest/meta-data/",
            "http://[fd00:ec2::254]/latest/meta-data/"  # AWS IPv6 Link-local
        ]
        for url in metadata_urls:
            valid, err = validate_url(url)
            assert valid is False, f"Failed to block cloud metadata service: {url}"
            assert "internal" in err.lower()

    def test_allowlist_domain_restriction(self):
        """Requests must be restricted to allowlisted domains when specified."""
        allowed = {"youtube.com", "vimeo.com"}
        
        # Valid domain
        valid, err = validate_url("https://youtube.com/watch?v=123", allowed)
        assert valid is True

        # Malicious subdomains or sibling domains
        invalid_domains = [
            "https://evil-youtube.com/watch",
            "https://youtube.com.evil.com/watch",
            "https://google.com/",
            "https://attacker-domain.org/"
        ]
        for url in invalid_domains:
            valid, err = validate_url(url, allowed)
            assert valid is False, f"Failed to block domain: {url}"
            assert "allowlist" in err.lower()
