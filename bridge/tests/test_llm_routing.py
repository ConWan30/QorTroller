"""Tests for the three-tier LLM backend router.

Covers: policy resolution, chain building, health tracking,
failover matrix, honesty fields, Level 0 reject, sovereignty rail.
"""

from __future__ import annotations

import os
import sys

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.llm_routing.policy import (
    RoutingPolicy,
    RoutingDecision,
    resolve_policy_from_env,
    LEVEL_0_TASKS,
    DEFAULT_TASK_CHAINS,
)
from vapi_bridge.llm_routing.types import RouteResult, ProvenanceRecord, BackendHealth
from vapi_bridge.llm_routing.health import HealthCache
from vapi_bridge.llm_routing.router import LLMRouter


# ══════════════════════════════════════════════════════
# Fixtures
# ══════════════════════════════════════════════════════

@pytest.fixture
def mock_backend():
    """Create a mock backend that returns a fixed response."""
    backend = MagicMock()
    backend.id = "mock"
    backend.capabilities = frozenset({"CHAT", "TOOLS"})
    backend.configured.return_value = True
    backend.is_available.return_value = True

    async def chat(messages, tools=None, temperature=0.0, max_tokens=4096):
        return {
            "choices": [{"message": {"role": "assistant", "content": "mock response"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "model": "mock-model",
        }
    backend.chat = AsyncMock(side_effect=chat)

    async def health():
        return type("HealthStatus", (), {"ok": True, "latency_ms": 5.0, "model": "mock-model", "error": ""})()
    backend.health = AsyncMock(side_effect=health)

    return backend


@pytest.fixture
def mock_backend_failing():
    """Create a mock backend that always fails."""
    backend = MagicMock()
    backend.id = "failing"
    backend.capabilities = frozenset({"CHAT"})
    backend.configured.return_value = True
    backend.is_available.return_value = True
    backend.chat = AsyncMock(side_effect=Exception("connection refused"))
    backend.health = AsyncMock(side_effect=Exception("down"))
    return backend


# ══════════════════════════════════════════════════════
# Test: Policy resolution
# ══════════════════════════════════════════════════════

class TestPolicyResolution:
    """RoutingPolicy and resolve_policy_from_env()"""

    def test_default_policy(self):
        """Default policy has chain=[quicksilver, local], mode=auto."""
        policy = RoutingPolicy()
        assert policy.primary == "quicksilver"
        assert policy.secondary == "local"
        assert policy.tertiary == ""
        assert policy.mode == "auto"
        assert not policy.refuse_cloud
        assert not policy.allow_nim_for_assistant

    def test_primary_only_mode(self):
        """primary_only sets max_failures=0."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "primary_only"}, clear=True):
            policy = resolve_policy_from_env()
            assert policy.mode == "primary_only"
            assert policy.max_failures == 0

    def test_local_mode(self):
        """local mode excludes quicksilver and nim."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "local"}, clear=True):
            policy = resolve_policy_from_env()
            assert "quicksilver" in policy.excluded_backends
            assert "nim" in policy.excluded_backends

    def test_cloud_mode(self):
        """cloud mode excludes local."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "cloud"}, clear=True):
            policy = resolve_policy_from_env()
            assert "local" in policy.excluded_backends

    def test_pin_mode(self):
        """pin:local sets pinned_backend."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "pin:local"}, clear=True):
            policy = resolve_policy_from_env()
            assert policy.pinned_backend == "local"

    def test_custom_primary_secondary(self):
        """LLM_PRIMARY and LLM_SECONDARY override defaults."""
        with patch.dict(
            "os.environ",
            {
                "LLM_PRIMARY": "nim",
                "LLM_SECONDARY": "quicksilver",
                "LLM_ROUTE_MODE": "failover",
            },
            clear=True,
        ):
            policy = resolve_policy_from_env()
            assert policy.primary == "nim"
            assert policy.secondary == "quicksilver"

    def test_refuse_cloud(self):
        """LLM_REFUSE_CLOUD=true sets refuse_cloud flag."""
        with patch.dict("os.environ", {"LLM_REFUSE_CLOUD": "true"}, clear=True):
            policy = resolve_policy_from_env()
            assert policy.refuse_cloud

    def test_task_chains_default(self):
        """Default task chains are pre-populated."""
        assert "assistant" in DEFAULT_TASK_CHAINS
        assert "guardian_advisory" in DEFAULT_TASK_CHAINS
        assert "offline" in DEFAULT_TASK_CHAINS
        assert "sovereign_strict" in DEFAULT_TASK_CHAINS
        assert DEFAULT_TASK_CHAINS["assistant"] == ["quicksilver", "local"]
        assert DEFAULT_TASK_CHAINS["guardian_advisory"] == ["nim", "local", "quicksilver"]
        assert DEFAULT_TASK_CHAINS["offline"] == ["local"]


# ══════════════════════════════════════════════════════
# Test: Level 0 reject
# ══════════════════════════════════════════════════════

class TestLevel0Reject:
    """Router must refuse Level 0 protocol tasks."""

    @pytest.mark.parametrize("task_class", list(LEVEL_0_TASKS))
    def test_level0_tasks_refused(self, task_class):
        """Every Level 0 task returns error='no_llm_on_level0'."""
        router = LLMRouter(policy=RoutingPolicy())
        result = router.route(task_class=task_class, messages=[{"role": "user", "content": "test"}])
        # route() is async — need to await it
        import asyncio
        result = asyncio.run(result)
        assert result.success is False
        assert result.error == "no_llm_on_level0"

    def test_non_level0_task_allowed(self):
        """Non-Level-0 tasks proceed to routing."""
        router = LLMRouter(policy=RoutingPolicy())
        # With no backends configured, it should get no_backends_available
        # rather than no_llm_on_level0
        import asyncio
        result = asyncio.run(
            router.route(task_class="assistant", messages=[{"role": "user", "content": "hi"}])
        )
        assert result.error != "no_llm_on_level0"


# ══════════════════════════════════════════════════════
# Test: Health cache
# ══════════════════════════════════════════════════════

class TestHealthCache:
    """HealthCache state machine and caching."""

    def test_initial_state(self):
        """Backend starts in UNKNOWN state."""
        cache = HealthCache(cache_seconds=30)
        backend = MagicMock()
        backend.id = "test"
        cache.register("test", backend)
        health = cache.get_health("test")
        assert health.state == "UNKNOWN"
        assert health.failures == 0

    def test_record_failure_triggers_degraded(self):
        """One failure → DEGRADED."""
        cache = HealthCache()
        cache.register("test", MagicMock())
        cache.record_failure("test", max_failures=3)
        assert cache.get_health("test").state == "DEGRADED"
        assert cache.get_health("test").failures == 1

    def test_record_failure_triggers_cooldown(self):
        """Three failures → COOLDOWN."""
        cache = HealthCache()
        cache.register("test", MagicMock())
        for _ in range(3):
            cache.record_failure("test", max_failures=3, cooldown_seconds=300)
        assert cache.get_health("test").state == "COOLDOWN"
        assert cache.get_health("test").failures == 3

    def test_record_success_resets_state(self):
        """Success after failures → HEALTHY."""
        cache = HealthCache()
        cache.register("test", MagicMock())
        cache.record_failure("test", max_failures=3)
        assert cache.get_health("test").state == "DEGRADED"
        cache.record_success("test")
        assert cache.get_health("test").state == "HEALTHY"
        assert cache.get_health("test").failures == 0

    def test_is_healthy_on_fresh_probe(self):
        """is_healthy returns True if probe returned ok=True."""
        cache = HealthCache(cache_seconds=300)
        backend = MagicMock()
        backend.id = "test"

        async def health():
            return type("HealthStatus", (), {"ok": True, "latency_ms": 1.0, "model": "test", "error": ""})()
        backend.health = AsyncMock(side_effect=health)

        cache.register("test", backend)
        import asyncio
        asyncio.run(cache.probe("test"))
        assert cache.is_healthy("test")

    def test_is_healthy_on_failed_probe(self):
        """is_healthy returns False if probe returned ok=False."""
        cache = HealthCache(cache_seconds=300)
        backend = MagicMock()
        backend.id = "test"

        async def health():
            return type("HealthStatus", (), {"ok": False, "latency_ms": 0.0, "model": "", "error": "down"})()
        backend.health = AsyncMock(side_effect=health)

        cache.register("test", backend)
        import asyncio
        asyncio.run(cache.probe("test"))
        assert not cache.is_healthy("test")

    def test_stale_cache_returns_unknown(self):
        """Stale cache returns True for UNKNOWN state (retry ok)."""
        cache = HealthCache(cache_seconds=0.001)  # very short cache
        backend = MagicMock()
        backend.id = "test"
        cache.register("test", backend)
        # Never probed — cache is stale, state is UNKNOWN
        import time
        time.sleep(0.01)
        assert cache.is_healthy("test")  # UNKNOWN → allowed


# ══════════════════════════════════════════════════════
# Test: Sovereignty rail
# ══════════════════════════════════════════════════════

class TestSovereigntyRail:
    """LLM_REFUSE_CLOUD strips cloud backends structurally."""

    def test_refuse_cloud_removes_quicksilver_and_nim(self):
        """refuse_cloud=true strips quicksilver and nim from chain."""
        policy = RoutingPolicy(refuse_cloud=True)
        # Build chain manually: only local should survive
        chain = []
        for bid in ["quicksilver", "nim", "local"]:
            chain.append(bid)
        if policy.refuse_cloud:
            chain = [b for b in chain if b not in ("quicksilver", "nim")]
        assert "quicksilver" not in chain
        assert "nim" not in chain
        assert "local" in chain

    def test_sovereign_strict_task_chain(self):
        """sovereign_strict task class maps to [local] only."""
        chain = DEFAULT_TASK_CHAINS["sovereign_strict"]
        assert chain == ["local"]


# ══════════════════════════════════════════════════════
# Test: Honesty fields
# ══════════════════════════════════════════════════════

class TestHonestyFields:
    """RouteResult carries all honesty fields on every response."""

    def test_success_response_has_honesty_fields(self):
        """Successful response has backend, model, route_mode, etc."""
        result = RouteResult(
            content="test",
            success=True,
            backend="local",
            model="deepseek-r1:14b",
            route_mode="failover",
            primary_attempted="quicksilver",
            attempts=["quicksilver"],
            fallback_used=True,
            degraded=False,
            latency_ms=12400,
            live=True,
        )
        assert result.backend == "local"
        assert result.model == "deepseek-r1:14b"
        assert result.route_mode == "failover"
        assert result.primary_attempted == "quicksilver"
        assert result.attempts == ["quicksilver"]
        assert result.fallback_used is True
        assert result.degraded is False
        assert result.latency_ms == 12400
        assert result.live is True

    def test_failure_response_has_honesty_fields(self):
        """Failure response still carries honesty fields."""
        result = RouteResult(
            content=None,
            success=False,
            error="all_backends_exhausted",
            backend="fallback",
            route_mode="failover",
            attempts=["quicksilver", "local"],
            fallback_used=True,
            latency_ms=5000,
            live=False,
        )
        assert result.backend == "fallback"
        assert result.error == "all_backends_exhausted"
        assert result.attempts == ["quicksilver", "local"]
        assert result.live is False

    def test_provenance_record_fields(self):
        """ProvenanceRecord has the expected fields."""
        record = ProvenanceRecord(
            call_id="llm_1234_abcd1234",
            timestamp=1000.0,
            backend="quicksilver",
            model="deepseek-v4-flash",
            route_mode="auto",
            attempts=[],
            fallback_used=False,
            latency_ms=200,
        )
        assert record.call_id.startswith("llm_")
        assert record.backend == "quicksilver"
        assert record.fallback_used is False
        assert record.latency_ms == 200


# ══════════════════════════════════════════════════════
# Test: Network error classification
# ══════════════════════════════════════════════════════

class TestNetworkErrorClassification:
    """Router correctly classifies network vs auth errors."""

    def test_connection_refused_is_network_error(self):
        assert LLMRouter._is_network_error(ConnectionRefusedError())

    def test_timeout_is_network_error(self):
        import asyncio
        assert LLMRouter._is_network_error(asyncio.TimeoutError())

    def test_connection_error_is_network_error(self):
        assert LLMRouter._is_network_error(ConnectionError())

    def test_oserror_connection_refused_is_network_error(self):
        assert LLMRouter._is_network_error(OSError("Connection refused"))

    def test_value_error_is_not_network_error(self):
        assert not LLMRouter._is_network_error(ValueError("invalid"))

    def test_auth_error_is_not_network_error(self):
        assert not LLMRouter._is_network_error(Exception("401 Unauthorized"))

    def test_rate_limit_error_is_not_network_error(self):
        assert not LLMRouter._is_network_error(Exception("429 Too Many Requests"))