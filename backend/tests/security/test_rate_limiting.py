"""
Security tests for Rate Limiting.
Verifies rate-limiting throttling, IP lockouts, and endpoint category separation.
"""
import pytest
import time
from backend.security.rate_limiter import RateLimiter, TokenBucket


@pytest.mark.security
class TestRateLimitingSecurity:
    """Verifies that rate limit policies block brute force and denial of service attempts."""

    def test_request_throttling_and_rejections(self):
        """Requests exceeding category capacity must be blocked with retry duration."""
        limiter = RateLimiter()
        client_ip = "198.51.100.12"
        
        # Configure a small bucket: 3 tokens, refill rate 1 token/sec
        bucket = TokenBucket(capacity=3, refill_rate=1.0, tokens=3)
        limiter.buckets[f"{client_ip}:api"] = bucket

        # First 3 requests allowed
        for _ in range(3):
            allowed, _, _ = limiter.is_allowed(client_ip, "api")
            assert allowed is True

        # 4th request must be rejected
        allowed, retry_after, remaining = limiter.is_allowed(client_ip, "api")
        assert allowed is False
        assert retry_after > 0
        assert remaining == 0

    def test_ip_lockout_escalation(self):
        """Repeated rejections must trigger an escalated lockout duration (e.g. >= 60 seconds)."""
        limiter = RateLimiter()
        client_ip = "203.0.113.88"
        
        # Set up a bucket with 0 tokens and 100 rejected requests
        bucket = TokenBucket(capacity=5, refill_rate=0.1, tokens=0, rejected_requests=101)
        limiter.buckets[f"{client_ip}:login"] = bucket

        # Next check should enforce the lockout interval
        limiter.is_allowed(client_ip, "login")
        allowed, retry_after, _ = limiter.is_allowed(client_ip, "login")
        assert allowed is False
        assert retry_after >= 59.0  # Lockout escalates to 60s minimum (with a small buffer for timing)

    def test_category_bucket_isolation(self):
        """Throttling one category must not block unrelated categories for the same IP."""
        limiter = RateLimiter()
        client_ip = "192.0.2.1"
        
        # Deplete "api" category
        api_bucket = TokenBucket(capacity=1, refill_rate=0.001, tokens=0)
        limiter.buckets[f"{client_ip}:api"] = api_bucket
        
        allowed_api, _, _ = limiter.is_allowed(client_ip, "api")
        assert allowed_api is False

        # "export" category bucket should still accept requests
        export_bucket = TokenBucket(capacity=5, refill_rate=1.0, tokens=5)
        limiter.buckets[f"{client_ip}:export"] = export_bucket

        allowed_export, _, _ = limiter.is_allowed(client_ip, "export")
        assert allowed_export is True
