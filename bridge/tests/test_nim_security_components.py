"""Unit tests for NIM security components.

Tests API key management, audit logging, rate limiting, circuit breaker,
and cost monitoring components.
"""
from __future__ import annotations

import pytest
import time
import json
import hashlib
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass

from vapi_bridge.security.api_key_manager import APIKeyManager, APIKeyVersion, KeyStatus
from vapi_bridge.security.nim_audit_logger import NIMAuditLogger, NIMCallMetadata
from vapi_bridge.security.nim_rate_limiter import NIMRateLimiter, RateLimitRule
from vapi_bridge.security.nim_circuit_breaker import NIMCircuitBreaker, CircuitBreakerOpenError, CircuitState
from vapi_bridge.security.nim_cost_monitor import NIMCostMonitor, CostThreshold


class TestAPIKeyManager:
    """Test API key lifecycle management."""

    def test_generate_key_creates_secure_key(self):
        """Test that key generation creates cryptographically secure keys."""
        manager = APIKeyManager(env="test")
        key_id = manager.generate_key("test_purpose")
        
        assert key_id in manager.keys
        assert "NIM_TEST_TEST_PURPOSE" in key_id
        assert len(manager.keys[key_id].key) >= 32  # 32-byte entropy
        assert manager.keys[key_id].status == KeyStatus.ACTIVE

    def test_key_rotation_creates_new_key(self):
        """Test that key rotation creates a new key with grace period."""
        manager = APIKeyManager(env="test")
        old_key_id = manager.generate_key("test_purpose")
        
        new_key_id = manager.rotate_key(old_key_id)
        
        assert new_key_id is not None
        assert new_key_id != old_key_id
        assert manager.keys[old_key_id].status == KeyStatus.ROTATING
        assert manager.keys[new_key_id].status == KeyStatus.ACTIVE

    def test_key_revocation_immediate(self):
        """Test that key revocation immediately invalidates the key."""
        manager = APIKeyManager(env="test")
        key_id = manager.generate_key("test_purpose")
        
        result = manager.revoke_key(key_id, "test_revoke")
        
        assert result is True
        assert manager.keys[key_id].status == KeyStatus.REVOKED

    def test_get_active_key_returns_valid_key(self):
        """Test that get_active_key returns the active key for a purpose."""
        manager = APIKeyManager(env="test")
        key_id = manager.generate_key("test_purpose")
        
        active_key = manager.get_active_key("test_purpose")
        
        assert active_key == manager.keys[key_id].key

    def test_check_rotation_needed(self):
        """Test that rotation check identifies keys needing rotation."""
        manager = APIKeyManager(env="test")
        # Set rotation interval to very short for testing
        manager.rotation_interval_days = 0.001  # ~86 seconds
        
        key_id = manager.generate_key("test_purpose")
        # Manually set created_at and expires_at to simulate an old key
        lifetime = manager.rotation_interval_days * 86400
        old_time = time.time() - (lifetime * 0.9)  # 90% of lifetime
        manager.keys[key_id].created_at = old_time
        manager.keys[key_id].expires_at = old_time + lifetime
        
        needs_rotation = manager.check_rotation_needed()
        
        assert key_id in needs_rotation


class TestNIMAuditLogger:
    """Test NIM audit logging functionality."""

    def test_log_call_creates_audit_record(self):
        """Test that logging a call creates an audit record."""
        store = Mock()
        store.insert_nim_audit_log = Mock()
        
        logger = NIMAuditLogger(store)
        call_id = logger.log_call(
            endpoint="test_endpoint",
            model="test_model",
            prompt="test prompt",
            response="test response",
            token_count=100,
            latency_ms=500.0,
            estimated_cost_usd=0.01,
            api_key_version="v1",
            success=True
        )
        
        assert call_id is not None
        store.insert_nim_audit_log.assert_called_once()
        
        # Verify the call metadata
        call_args = store.insert_nim_audit_log.call_args[0][0]
        assert isinstance(call_args, NIMCallMetadata)
        assert call_args.endpoint == "test_endpoint"
        assert call_args.model == "test_model"
        assert call_args.success is True

    def test_anomaly_detection_large_prompt(self):
        """Test anomaly detection for unusually large prompts."""
        store = Mock()
        store.insert_nim_audit_log = Mock()
        
        logger = NIMAuditLogger(store)
        large_prompt = "x" * 15000  # Exceeds 10000 threshold
        
        logger.log_call(
            endpoint="test_endpoint",
            model="test_model",
            prompt=large_prompt,
            response="test response",
            token_count=100,
            latency_ms=500.0,
            estimated_cost_usd=0.01,
            api_key_version="v1",
            success=True
        )
        
        call_args = store.insert_nim_audit_log.call_args[0][0]
        assert call_args.anomaly_score > 0.0
        assert "large_prompt" in json.loads(call_args.anomaly_flags or "[]")

    def test_anomaly_detection_high_cost(self):
        """Test anomaly detection for unusually high costs."""
        store = Mock()
        store.insert_nim_audit_log = Mock()
        
        logger = NIMAuditLogger(store)
        
        logger.log_call(
            endpoint="test_endpoint",
            model="test_model",
            prompt="test prompt",
            response="test response",
            token_count=100,
            latency_ms=500.0,
            estimated_cost_usd=0.15,  # Exceeds $0.10 threshold
            api_key_version="v1",
            success=True
        )
        
        call_args = store.insert_nim_audit_log.call_args[0][0]
        assert call_args.anomaly_score > 0.0
        assert "high_cost" in json.loads(call_args.anomaly_flags or "[]")

    def test_get_anomaly_report(self):
        """Test anomaly report generation."""
        store = Mock()
        store._conn = Mock()
        store._conn.return_value.__enter__ = Mock(return_value=store._conn)
        store._conn.return_value.__exit__ = Mock(return_value=None)
        store._conn.execute = Mock()
        store._conn.execute.return_value.fetchall.return_value = [
            {"call_id": "test1", "anomaly_score": 0.8},
            {"call_id": "test2", "anomaly_score": 0.6}
        ]
        
        logger = NIMAuditLogger(store)
        report = logger.get_anomaly_report(hours=24)
        
        assert report["period_hours"] == 24
        assert report["high_anomaly_count"] == 2
        assert len(report["anomalies"]) == 2


class TestNIMRateLimiter:
    """Test NIM rate limiting functionality."""

    def test_rate_limit_allows_within_limits(self):
        """Test that rate limiter allows calls within limits."""
        limiter = NIMRateLimiter()
        
        allowed, limit_type = limiter.check_rate_limit("device1")
        
        assert allowed is True
        assert limit_type is None

    def test_rate_limit_blocks_exceeding_burst(self):
        """Test that rate limiter blocks exceeding burst limit."""
        limiter = NIMRateLimiter()
        limiter._rules["burst"] = RateLimitRule(window_seconds=60, max_calls=2)
        
        # Make 2 calls (at limit)
        limiter.check_rate_limit("device1")
        limiter.check_rate_limit("device1")
        
        # 3rd call should be blocked
        allowed, limit_type = limiter.check_rate_limit("device1")
        
        assert allowed is False
        assert limit_type == "burst"

    def test_rate_limit_per_device_isolation(self):
        """Test that rate limits are isolated per device."""
        limiter = NIMRateLimiter()
        limiter._rules["burst"] = RateLimitRule(window_seconds=60, max_calls=1)
        
        # Device 1 makes a call
        limiter.check_rate_limit("device1")
        
        # Device 1 should be blocked
        allowed1, _ = limiter.check_rate_limit("device1")
        assert allowed1 is False
        
        # Device 2 should still be allowed
        allowed2, _ = limiter.check_rate_limit("device2")
        assert allowed2 is True

    def test_get_device_stats(self):
        """Test device statistics retrieval."""
        limiter = NIMRateLimiter()
        
        # Make some calls
        limiter.check_rate_limit("device1")
        limiter.check_rate_limit("device1")
        
        stats = limiter.get_device_stats("device1")
        
        assert "burst" in stats
        assert "sustained" in stats
        assert "daily" in stats
        assert stats["burst"]["calls"] == 2


class TestNIMCircuitBreaker:
    """Test NIM circuit breaker functionality."""

    def test_circuit_breaker_closed_initially(self):
        """Test that circuit breaker starts in CLOSED state."""
        breaker = NIMCircuitBreaker()
        
        state = breaker.get_state()
        
        assert state["state"] == "closed"
        assert state["failure_count"] == 0

    def test_circuit_breaker_opens_on_threshold(self):
        """Test that circuit breaker opens after failure threshold."""
        breaker = NIMCircuitBreaker()
        breaker._config.failure_threshold = 3
        
        def failing_function():
            raise Exception("Test failure")
        
        # Trigger failures up to threshold
        for _ in range(3):
            try:
                breaker.call(failing_function)
            except Exception:
                pass
        
        state = breaker.get_state()
        assert state["state"] == "open"
        assert state["failure_count"] == 3

    def test_circuit_breaker_blocks_when_open(self):
        """Test that circuit breaker blocks calls when OPEN."""
        breaker = NIMCircuitBreaker()
        breaker._config.failure_threshold = 1
        
        def failing_function():
            raise Exception("Test failure")
        
        # Trigger circuit breaker open
        try:
            breaker.call(failing_function)
        except Exception:
            pass
        
        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            breaker.call(failing_function)

    def test_circuit_breaker_transitions_to_half_open(self):
        """Test that circuit breaker transitions to HALF_OPEN after timeout."""
        breaker = NIMCircuitBreaker()
        breaker._config.failure_threshold = 1
        breaker._config.timeout_seconds = 0.1  # 100ms timeout
        breaker._config.half_open_max_calls = 1  # Only 1 call needed to close
        
        def failing_function():
            raise Exception("Test failure")
        
        # Trigger circuit breaker open
        try:
            breaker.call(failing_function)
        except Exception:
            pass
        
        # Wait for timeout
        time.sleep(0.15)
        
        # Next call should transition to HALF_OPEN then CLOSED
        def succeeding_function():
            return "success"
        
        result = breaker.call(succeeding_function)
        assert result == "success"
        
        state = breaker.get_state()
        assert state["state"] == "closed"  # Should close after successful call


class TestNIMCostMonitor:
    """Test NIM cost monitoring functionality."""

    def test_cost_monitor_normal_status(self):
        """Test cost monitor with normal costs."""
        store = Mock()
        store._conn = Mock()
        store._conn.return_value.__enter__ = Mock(return_value=store._conn)
        store._conn.return_value.__exit__ = Mock(return_value=None)
        store._conn.execute = Mock()
        store._conn.execute.return_value.fetchone.return_value = {
            "total_cost": 25.0,
            "call_count": 100
        }
        
        monitor = NIMCostMonitor(store)
        status = monitor.check_cost_thresholds()
        
        assert status["status"] == "normal"
        assert status["total_cost_usd"] == 25.0

    def test_cost_monitor_warning_status(self):
        """Test cost monitor with warning threshold exceeded."""
        store = Mock()
        store._conn = Mock()
        store._conn.return_value.__enter__ = Mock(return_value=store._conn)
        store._conn.return_value.__exit__ = Mock(return_value=None)
        store._conn.execute = Mock()
        store._conn.execute.return_value.fetchone.return_value = {
            "total_cost": 75.0,  # Exceeds $50 warning
            "call_count": 100
        }
        
        monitor = NIMCostMonitor(store)
        status = monitor.check_cost_thresholds()
        
        assert status["status"] == "warning"
        assert status["total_cost_usd"] == 75.0

    def test_cost_monitor_critical_status(self):
        """Test cost monitor with critical threshold exceeded."""
        store = Mock()
        store._conn = Mock()
        store._conn.return_value.__enter__ = Mock(return_value=store._conn)
        store._conn.return_value.__exit__ = Mock(return_value=None)
        store._conn.execute = Mock()
        store._conn.execute.return_value.fetchone.return_value = {
            "total_cost": 150.0,  # Exceeds $100 critical
            "call_count": 100
        }
        
        monitor = NIMCostMonitor(store)
        status = monitor.check_cost_thresholds()
        
        assert status["status"] == "critical"
        assert status["total_cost_usd"] == 150.0


class TestSecurityIntegration:
    """Test integration of security components."""

    def test_full_security_pipeline(self):
        """Test the full security pipeline with all components."""
        # Setup mock store
        store = Mock()
        store.insert_nim_audit_log = Mock()
        store._conn = Mock()
        store._conn.return_value.__enter__ = Mock(return_value=store._conn)
        store._conn.return_value.__exit__ = Mock(return_value=None)
        store._conn.execute = Mock()
        store._conn.execute.return_value.fetchone.return_value = {
            "total_cost": 10.0,
            "call_count": 5
        }
        
        # Initialize components
        key_manager = APIKeyManager(env="test")
        audit_logger = NIMAuditLogger(store)
        rate_limiter = NIMRateLimiter()
        circuit_breaker = NIMCircuitBreaker()
        cost_monitor = NIMCostMonitor(store)
        
        # Generate API key
        key_id = key_manager.generate_key("test")
        assert key_manager.get_active_key("test") is not None
        
        # Check rate limit
        allowed, _ = rate_limiter.check_rate_limit("device1")
        assert allowed is True
        
        # Log a call
        call_id = audit_logger.log_call(
            endpoint="test_endpoint",
            model="test_model",
            prompt="test prompt",
            response="test response",
            token_count=50,
            latency_ms=200.0,
            estimated_cost_usd=0.005,
            api_key_version="v1",
            success=True
        )
        assert call_id is not None
        
        # Check cost status
        cost_status = cost_monitor.check_cost_thresholds()
        assert cost_status["status"] == "normal"
        
        # Test circuit breaker with successful call
        def test_function():
            return "success"
        
        result = circuit_breaker.call(test_function)
        assert result == "success"
        assert circuit_breaker.get_state()["state"] == "closed"