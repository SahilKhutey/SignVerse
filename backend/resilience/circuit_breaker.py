"""
Circuit breaker pattern for fault tolerance.
Prevents cascading failures when a service is down.
"""
import asyncio
import time
import logging
from enum import Enum
from typing import Callable, Any, Optional
from dataclasses import dataclass, field
from functools import wraps

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"          # Normal operation
    OPEN = "open"              # Failing, reject calls
    HALF_OPEN = "half_open"    # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for a circuit breaker."""
    failure_threshold: int = 5       # Failures before opening
    success_threshold: int = 2       # Successes in half-open to close
    timeout_s: float = 30.0          # Time before trying half-open
    expected_exceptions: tuple = (Exception,)


class CircuitBreakerOpen(Exception):
    """Raised when circuit is open and call is rejected."""
    pass


BREAKER_REGISTRY = {}


class CircuitBreaker:
    """
    Circuit breaker for protecting against cascading failures.
    
    States:
    - CLOSED: Normal, calls pass through. Track failures.
    - OPEN: Calls immediately rejected. Wait for timeout.
    - HALF_OPEN: Allow one test call. If success, close. If fail, open again.
    """
    
    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_state_change: float = time.time()
        
        # Register breaker
        BREAKER_REGISTRY[name] = self
    
    def can_execute(self) -> bool:
        """Check if a call is allowed."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if timeout has elapsed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.config.timeout_s:
                self._transition_to(CircuitState.HALF_OPEN)
                return True
            return False
        
        if self.state == CircuitState.HALF_OPEN:
            # Allow one test call at a time
            return True
        
        return False
    
    def record_success(self):
        """Record a successful call."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self._transition_to(CircuitState.CLOSED)
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = max(0, self.failure_count - 1)
    
    def record_failure(self, exception: Exception):
        """Record a failed call."""
        if not isinstance(exception, self.config.expected_exceptions):
            # Unexpected exception, don't count
            return
        
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.state == CircuitState.HALF_OPEN:
            self._transition_to(CircuitState.OPEN)
        elif self.state == CircuitState.CLOSED:
            if self.failure_count >= self.config.failure_threshold:
                self._transition_to(CircuitState.OPEN)
    
    def _transition_to(self, new_state: CircuitState):
        """Transition to a new state."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        
        if new_state == CircuitState.CLOSED:
            self.failure_count = 0
            self.success_count = 0
        elif new_state == CircuitState.HALF_OPEN:
            self.success_count = 0
        
        logger.info(
            f"Circuit breaker '{self.name}': {old_state.value} → {new_state.value}"
        )
    
    def get_state(self) -> dict:
        """Get current state for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time,
        }


# === Decorator ===

def circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator: protect a function with a circuit breaker."""
    breaker = CircuitBreaker(name, config)
    
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                if not breaker.can_execute():
                    raise CircuitBreakerOpen(
                        f"Circuit '{name}' is OPEN. Try again later."
                    )
                try:
                    result = await func(*args, **kwargs)
                    breaker.record_success()
                    return result
                except Exception as e:
                    breaker.record_failure(e)
                    raise e
            async_wrapper.breaker = breaker
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                if not breaker.can_execute():
                    raise CircuitBreakerOpen(
                        f"Circuit '{name}' is OPEN. Try again later."
                    )
                try:
                    result = func(*args, **kwargs)
                    breaker.record_success()
                    return result
                except Exception as e:
                    breaker.record_failure(e)
                    raise e
            sync_wrapper.breaker = breaker
            return sync_wrapper
            
    return decorator


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 0.1,
    backoff_factor: float = 2.0,
    expected_exceptions: tuple = (Exception,),
):
    """Decorator to retry a function (sync or async) with exponential backoff."""
    def decorator(func):
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                delay = initial_delay
                for attempt in range(max_retries + 1):
                    try:
                        return await func(*args, **kwargs)
                    except expected_exceptions as e:
                        if attempt == max_retries:
                            raise e
                        logger.warning(
                            f"Async call to {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f}s... Error: {e}"
                        )
                        await asyncio.sleep(delay)
                        delay *= backoff_factor
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                delay = initial_delay
                for attempt in range(max_retries + 1):
                    try:
                        return func(*args, **kwargs)
                    except expected_exceptions as e:
                        if attempt == max_retries:
                            raise e
                        logger.warning(
                            f"Sync call to {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}). "
                            f"Retrying in {delay:.2f}s... Error: {e}"
                        )
                        time.sleep(delay)
                        delay *= backoff_factor
            return sync_wrapper
    return decorator
