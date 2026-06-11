"""
Rate limiting using token bucket algorithm.
Prevents abuse, ensures fair usage.
"""
import time
import threading
from typing import Dict, Optional
from dataclasses import dataclass, field
from fastapi import HTTPException, Request, status
from collections import defaultdict


@dataclass
class TokenBucket:
    """Token bucket for one client."""
    capacity: float            # Max tokens
    refill_rate: float         # Tokens per second
    tokens: float = field(default=0.0)
    last_refill: float = field(default_factory=time.time)
    locked_until: float = 0.0  # If non-zero, client is temporarily locked out
    total_requests: int = 0
    rejected_requests: int = 0


class RateLimiter:
    """
    Per-client rate limiting with token bucket.
    Thread-safe, in-memory (replace with Redis for multi-process).
    """
    
    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.lock = threading.RLock()
        
        # Default limits per endpoint category
        self.default_limits = {
            "ingest": {"capacity": 10, "refill_rate": 1.0},        # 10 burst, 1/sec sustained
            "perception": {"capacity": 30, "refill_rate": 5.0},    # 30 burst, 5/sec
            "dataset": {"capacity": 50, "refill_rate": 10.0},     # 50 burst, 10/sec
            "export": {"capacity": 5, "refill_rate": 0.5},        # 5 burst, 0.5/sec
            "websocket": {"capacity": 100, "refill_rate": 30.0},   # 100 burst, 30/sec (frames)
        }
    
    def _get_bucket(self, client_id: str, category: str) -> TokenBucket:
        """Get or create bucket for client."""
        with self.lock:
            key = f"{client_id}:{category}"
            if key not in self.buckets:
                limits = self.default_limits.get(category, {"capacity": 10, "refill_rate": 1.0})
                self.buckets[key] = TokenBucket(
                    capacity=limits["capacity"],
                    refill_rate=limits["refill_rate"],
                    tokens=limits["capacity"],  # Start full
                )
            return self.buckets[key]
    
    def _refill(self, bucket: TokenBucket):
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - bucket.last_refill
        new_tokens = elapsed * bucket.refill_rate
        bucket.tokens = min(bucket.capacity, bucket.tokens + new_tokens)
        bucket.last_refill = now
    
    def is_allowed(self, client_id: str, category: str = "default") -> tuple:
        """
        Check if client is allowed to make a request.
        Returns: (allowed: bool, retry_after: float, remaining: float)
        """
        with self.lock:
            bucket = self._get_bucket(client_id, category)
            
            # Check lockout
            if bucket.locked_until > time.time():
                return False, bucket.locked_until - time.time(), 0.0
            
            # Refill
            self._refill(bucket)
            
            # Try to consume token
            if bucket.tokens >= 1.0:
                bucket.tokens -= 1.0
                bucket.total_requests += 1
                return True, 0.0, bucket.tokens
            
            # Not enough tokens
            bucket.rejected_requests += 1
            
            # Calculate retry-after
            tokens_needed = 1.0 - bucket.tokens
            retry_after = tokens_needed / bucket.refill_rate
            
            # Lock out if too many rejections
            if bucket.rejected_requests > 50:
                bucket.locked_until = time.time() + 60  # 1 min lockout
            
            return False, retry_after, 0.0
    
    def get_stats(self, client_id: str) -> Dict:
        """Get stats for a client."""
        with self.lock:
            stats = {}
            for category in self.default_limits:
                key = f"{client_id}:{category}"
                if key in self.buckets:
                    b = self.buckets[key]
                    stats[category] = {
                        "tokens": b.tokens,
                        "capacity": b.capacity,
                        "total": b.total_requests,
                        "rejected": b.rejected_requests,
                    }
            return stats


# Singleton
limiter = RateLimiter()


# === FastAPI dependency ===

def check_rate_limit(category: str = "default"):
    """FastAPI dependency that checks rate limit."""
    async def dependency(request: Request):
        client_id = _get_client_id(request)
        allowed, retry_after, remaining = limiter.is_allowed(client_id, category)
        
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {category}",
                headers={
                    "Retry-After": str(int(retry_after) + 1),
                    "X-RateLimit-Remaining": "0",
                }
            )
    
    return dependency


def _get_client_id(request: Request) -> str:
    """Get client identifier for rate limiting."""
    # Prefer authenticated user
    auth = request.headers.get("Authorization")
    if auth:
        return f"auth:{hash(auth) % 10000}"
    
    # Fall back to IP
    client_ip = request.client.host if request.client else "unknown"
    # Consider X-Forwarded-For if behind proxy
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    
    return f"ip:{client_ip}"
