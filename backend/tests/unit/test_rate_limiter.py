"""
Unit tests for rate limiter.
"""
import pytest
import time
from backend.security.rate_limiter import RateLimiter


@pytest.mark.unit
class TestRateLimiter:
    """Tests for token bucket rate limiter."""
    
    def test_initial_request_allowed(self):
        """First request should always be allowed."""
        limiter = RateLimiter()
        allowed, retry, remaining = limiter.is_allowed("client1", "test")
        assert allowed is True
        assert remaining >= 0
    
    def test_capacity_enforced(self):
        """Should reject after capacity exhausted."""
        limiter = RateLimiter()
        from backend.security.rate_limiter import TokenBucket
        
        # Use a small capacity of 2
        bucket = TokenBucket(capacity=2.0, refill_rate=0.01, tokens=2.0)
        limiter.buckets["client1:test"] = bucket
        
        # First 2 should pass
        assert limiter.is_allowed("client1", "test")[0] is True
        assert limiter.is_allowed("client1", "test")[0] is True
        # Third should fail
        allowed, retry, _ = limiter.is_allowed("client1", "test")
        assert allowed is False
        assert retry > 0
    
    def test_refill_over_time(self):
        """Tokens should refill over time."""
        limiter = RateLimiter()
        from backend.security.rate_limiter import TokenBucket
        
        bucket = TokenBucket(capacity=10.0, refill_rate=10.0, tokens=0.0, last_refill=time.time() - 1)
        limiter.buckets["client1:test"] = bucket
        
        # Should have ~10 tokens after 1 second
        allowed, _, _ = limiter.is_allowed("client1", "test")
        assert allowed is True
    
    def test_lockout_after_many_rejections(self):
        """Client should be locked out after many rejections."""
        limiter = RateLimiter()
        from backend.security.rate_limiter import TokenBucket
        
        bucket = TokenBucket(capacity=1.0, refill_rate=0.001, tokens=0.0, rejected_requests=100)
        limiter.buckets["client1:test"] = bucket
        
        # Should be locked
        allowed, retry, _ = limiter.is_allowed("client1", "test")
        assert allowed is False
        assert retry >= 60  # Should be locked for 60s
    
    def test_separate_buckets_per_category(self):
        """Different categories should have separate buckets."""
        limiter = RateLimiter()
        # Exhaust "ingest" bucket
        for _ in range(100):
            limiter.is_allowed("client1", "ingest")
        # "export" should still be available
        allowed, _, _ = limiter.is_allowed("client1", "export")
        assert allowed is True
    
    def test_stats_returned_correctly(self):
        """get_stats() should return per-category stats."""
        limiter = RateLimiter()
        limiter.is_allowed("client1", "ingest")
        limiter.is_allowed("client1", "ingest")
        
        stats = limiter.get_stats("client1")
        assert "ingest" in stats
        assert stats["ingest"]["total"] == 2
