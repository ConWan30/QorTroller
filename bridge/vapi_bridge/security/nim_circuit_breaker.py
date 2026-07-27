"""Circuit breaker pattern for NIM API calls.

Implements circuit breaker to prevent cascading failures and provide
graceful degradation when NIM service is unavailable.
"""
from __future__ import annotations

import time
import logging
from enum import Enum
from typing import Optional, Callable
from dataclasses import dataclass

log = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreakerConfig:
    """Circuit breaker configuration."""
    failure_threshold: int = 5      # Failures before opening
    timeout_seconds: int = 60       # How long to stay open
    half_open_max_calls: int = 3   # Test calls in half-open


class NIMCircuitBreaker:
    """Circuit breaker for NIM API calls."""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._half_open_call_count = 0

    def call(self, func: Callable, *args, **kwargs) -> any:
        """Execute a call through the circuit breaker."""

        if self._state == CircuitState.OPEN:
            # Check if we should transition to half-open
            if time.time() - self._last_failure_time > self._config.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_call_count = 0
                log.info("Circuit breaker transitioning to HALF_OPEN")
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (since {self._last_failure_time})"
                )

        try:
            result = func(*args, **kwargs)

            # Success handling
            if self._state == CircuitState.HALF_OPEN:
                self._half_open_call_count += 1
                if self._half_open_call_count >= self._config.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    log.info("Circuit breaker transitioning to CLOSED")
            else:
                self._failure_count = 0

            return result

        except Exception as e:
            # Failure handling
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._failure_count >= self._config.failure_threshold:
                self._state = CircuitState.OPEN
                log.error(
                    f"Circuit breaker transitioning to OPEN "
                    f"({self._failure_count} failures)"
                )

            raise

    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            "state": self._state.value,
            "failure_count": self._failure_count,
            "last_failure_time": self._last_failure_time,
            "half_open_call_count": self._half_open_call_count
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass