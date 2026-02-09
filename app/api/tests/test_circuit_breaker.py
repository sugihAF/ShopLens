"""Tests for the circuit breaker module."""

import time
import pytest

from app.core.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreaker:
    """Test circuit breaker state transitions and behavior."""

    def test_initial_state_is_closed(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1.0)
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_stays_closed_under_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=1.0)
        cb.record_failure()
        cb.record_failure()
        # 2 failures < threshold of 3
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_closed_to_open_after_threshold(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=10.0)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_open_to_half_open_after_recovery_timeout(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Wait for recovery timeout
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.allow_request() is True

    def test_half_open_to_closed_on_success(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_half_open_to_open_on_failure(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        assert cb.state == CircuitState.HALF_OPEN

        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_success_resets_failure_count(self):
        cb = CircuitBreaker("test", failure_threshold=3, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        # After success, failure count resets so one more failure shouldn't open
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_reset(self):
        cb = CircuitBreaker("test", failure_threshold=2, recovery_timeout=10.0)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_request_rejected_when_open(self):
        cb = CircuitBreaker("test", failure_threshold=1, recovery_timeout=60.0)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

        # Multiple allow_request checks should all return False
        for _ in range(5):
            assert cb.allow_request() is False
