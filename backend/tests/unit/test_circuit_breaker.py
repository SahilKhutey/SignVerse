"""
Unit tests for circuit breaker.
"""
import pytest
import time
import asyncio
from backend.resilience.circuit_breaker import (
    CircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitBreakerOpen,
    circuit_breaker
)


@pytest.mark.unit
class TestCircuitBreaker:
    """Tests for circuit breaker state machine."""
    
    def test_starts_closed(self):
        """New breaker should be CLOSED."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True
    
    def test_opens_after_threshold_failures(self):
        """Should open after N consecutive failures."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
        
        for _ in range(3):
            try:
                if cb.can_execute():
                    cb.record_failure(ValueError("fail"))
            except CircuitBreakerOpen:
                pass
        
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False
    
    def test_transitions_to_half_open_after_timeout(self):
        """Should transition to HALF_OPEN after timeout."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            timeout_s=0.1,
        ))
        cb.record_failure(ValueError("fail"))
        assert cb.state == CircuitState.OPEN
        
        time.sleep(0.15)
        assert cb.can_execute() is True
        assert cb.state == CircuitState.HALF_OPEN
    
    def test_closes_after_success_in_half_open(self):
        """Should close after success threshold in HALF_OPEN."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            success_threshold=2,
            timeout_s=0.1,
        ))
        cb.record_failure(ValueError("fail"))
        time.sleep(0.15)
        cb.can_execute()  # Triggers half-open
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
    
    def test_reopens_on_failure_in_half_open(self):
        """Should re-open on any failure in HALF_OPEN."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=1,
            timeout_s=0.1,
        ))
        cb.record_failure(ValueError("fail"))
        time.sleep(0.15)
        cb.can_execute()  # Half-open
        cb.record_failure(ValueError("still failing"))
        assert cb.state == CircuitState.OPEN
    
    def test_ignores_unexpected_exceptions(self):
        """Unexpected exceptions don't count as failures."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(
            failure_threshold=2,
            expected_exceptions=(ValueError,)
        ))
        # TypeError not in expected_exceptions
        for _ in range(10):
            cb.record_failure(TypeError("unexpected"))
        assert cb.state == CircuitState.CLOSED
    
    def test_success_resets_failure_count(self):
        """Success should reduce failure count."""
        cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=5))
        cb.record_failure(ValueError("fail"))
        cb.record_failure(ValueError("fail"))
        assert cb.failure_count == 2
        cb.record_success()
        assert cb.failure_count == 1
    
    def test_get_state_returns_dict(self):
        """get_state() should return monitoring data."""
        cb = CircuitBreaker("test", CircuitBreakerConfig())
        state = cb.get_state()
        assert "name" in state
        assert "state" in state
        assert "failure_count" in state


@pytest.mark.asyncio
@pytest.mark.unit
class TestCircuitBreakerDecorator:
    """Tests for the circuit_breaker decorator."""
    
    async def test_decorator_protects_function(self):
        """Decorator should wrap function with circuit breaker."""
        @circuit_breaker("test_dec", CircuitBreakerConfig(failure_threshold=1))
        async def failing():
            raise ValueError("boom")
        
        with pytest.raises(ValueError):
            await failing()
    
    async def test_decorator_rejects_when_open(self):
        """Should raise CircuitBreakerOpen when circuit is open."""
        @circuit_breaker("test_dec2", CircuitBreakerConfig(
            failure_threshold=1, timeout_s=10
        ))
        async def failing():
            raise ValueError("boom")
        
        # First call fails, opens circuit
        with pytest.raises(ValueError):
            await failing()
        
        # Second call rejected
        with pytest.raises(CircuitBreakerOpen):
            await failing()
    
    async def test_decorator_passes_through_success(self):
        """Successful function should return value."""
        @circuit_breaker("test_dec3")
        async def working():
            return "result"
        
        result = await working()
        assert result == "result"
