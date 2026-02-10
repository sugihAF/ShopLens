"""Circuit breaker pattern for external API calls."""

import time
from enum import Enum
from threading import Lock

from app.core.logging import get_logger

logger = get_logger(__name__)


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """
    Circuit breaker to protect against cascading failures from external APIs.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Requests are rejected immediately (API is down)
    - HALF_OPEN: A single request is allowed through to test recovery

    Transitions:
    - CLOSED -> OPEN: After `failure_threshold` consecutive failures
    - OPEN -> HALF_OPEN: After `recovery_timeout` seconds
    - HALF_OPEN -> CLOSED: On success
    - HALF_OPEN -> OPEN: On failure
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout."""
        with self._lock:
            if (
                self._state == CircuitState.OPEN
                and time.time() - self._last_failure_time >= self.recovery_timeout
            ):
                self._state = CircuitState.HALF_OPEN
                logger.info(f"Circuit breaker '{self.name}': OPEN -> HALF_OPEN (recovery timeout elapsed)")
            return self._state

    def allow_request(self) -> bool:
        """Check if a request should be allowed through."""
        current_state = self.state  # triggers OPEN->HALF_OPEN check
        if current_state == CircuitState.CLOSED:
            return True
        if current_state == CircuitState.HALF_OPEN:
            return True
        # OPEN
        return False

    def record_success(self) -> None:
        """Record a successful request."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                logger.info(f"Circuit breaker '{self.name}': HALF_OPEN -> CLOSED (success)")
            self._state = CircuitState.CLOSED
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit breaker '{self.name}': HALF_OPEN -> OPEN (failure)")
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN
                logger.warning(
                    f"Circuit breaker '{self.name}': CLOSED -> OPEN "
                    f"(failures: {self._failure_count}/{self.failure_threshold})"
                )

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._last_failure_time = 0.0


# Module-level singleton for Gemini API calls
gemini_breaker = CircuitBreaker("gemini", failure_threshold=5, recovery_timeout=30.0)
