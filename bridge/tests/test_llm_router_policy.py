"""Tests for routing policy resolution.

Covers: RoutingPolicy defaults, resolve_policy_from_env() for all
LLM_ROUTE_MODE values, env var overrides, task class chains,
and Level 0 task rejection.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch

from bridge.vapi_bridge.llm_routing.policy import (
    RoutingPolicy,
    RoutingDecision,
    resolve_policy_from_env,
    LEVEL_0_TASKS,
    DEFAULT_TASK_CHAINS,
)


# ══════════════════════════════════════════════════════
# RoutingPolicy defaults
# ══════════════════════════════════════════════════════

class TestRoutingPolicyDefaults:
    """Default policy values are safe and explicit."""

    def test_default_chain(self):
        """Default: primary=quicksilver, secondary=local, no tertiary."""
        p = RoutingPolicy()
        assert p.primary == "quicksilver"
        assert p.secondary == "local"
        assert p.tertiary == ""

    def test_default_mode(self):
        """Default mode is 'auto'."""
        p = RoutingPolicy()
        assert p.mode == "auto"

    def test_default_refuse_cloud(self):
        """Default: cloud is NOT refused."""
        p = RoutingPolicy()
        assert p.refuse_cloud is False

    def test_default_allow_nim_for_assistant(self):
        """Default: NIM is NOT allowed for assistant."""
        p = RoutingPolicy()
        assert p.allow_nim_for_assistant is False

    def test_default_failover_on_timeout(self):
        """Default: failover on timeout is enabled."""
        p = RoutingPolicy()
        assert p.failover_on_timeout is True

    def test_default_tuning(self):
        """Default tuning values are set."""
        p = RoutingPolicy()
        assert p.timeout_seconds == 30
        assert p.max_failures == 3
        assert p.cooldown_seconds == 300
        assert p.health_cache_seconds == 30


# ══════════════════════════════════════════════════════
# resolve_policy_from_env — mode presets
# ══════════════════════════════════════════════════════

class TestResolveFromEnv:
    """resolve_policy_from_env() for each LLM_ROUTE_MODE."""

    def test_auto_mode(self):
        """auto → default policy."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "auto"}, clear=True):
            p = resolve_policy_from_env()
            assert p.mode == "auto"
            assert p.primary == "quicksilver"
            assert p.secondary == "local"

    def test_failover_mode(self):
        """failover → same as auto."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "failover"}, clear=True):
            p = resolve_policy_from_env()
            assert p.mode == "failover"

    def test_primary_only_mode(self):
        """primary_only → max_failures=0 (no failover)."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "primary_only"}, clear=True):
            p = resolve_policy_from_env()
            assert p.mode == "primary_only"
            assert p.max_failures == 0

    def test_cheap_mode(self):
        """cheap → prefer_cheapest=True."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "cheap"}, clear=True):
            p = resolve_policy_from_env()
            assert p.mode == "cheap"
            assert p.prefer_cheapest is True

    def test_local_mode(self):
        """local → excludes quicksilver and nim."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "local"}, clear=True):
            p = resolve_policy_from_env()
            assert "quicksilver" in p.excluded_backends
            assert "nim" in p.excluded_backends

    def test_cloud_mode(self):
        """cloud → excludes local."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "cloud"}, clear=True):
            p = resolve_policy_from_env()
            assert "local" in p.excluded_backends

    def test_pin_quicksilver_mode(self):
        """pin:quicksilver → pinned_backend='quicksilver'."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "pin:quicksilver"}, clear=True):
            p = resolve_policy_from_env()
            assert p.pinned_backend == "quicksilver"

    def test_pin_nim_mode(self):
        """pin:nim → pinned_backend='nim'."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "pin:nim"}, clear=True):
            p = resolve_policy_from_env()
            assert p.pinned_backend == "nim"

    def test_pin_local_mode(self):
        """pin:local → pinned_backend='local'."""
        with patch.dict("os.environ", {"LLM_ROUTE_MODE": "pin:local"}, clear=True):
            p = resolve_policy_from_env()
            assert p.pinned_backend == "local"

    def test_refuse_cloud_flag(self):
        """LLM_REFUSE_CLOUD=true sets refuse_cloud."""
        with patch.dict("os.environ", {"LLM_REFUSE_CLOUD": "true"}, clear=True):
            p = resolve_policy_from_env()
            assert p.refuse_cloud is True

    def test_refuse_cloud_default(self):
        """LLM_REFUSE_CLOUD unset or false → refuse_cloud=False."""
        with patch.dict("os.environ", {}, clear=True):
            p = resolve_policy_from_env()
            assert p.refuse_cloud is False

    def test_custom_primary_secondary(self):
        """LLM_PRIMARY and LLM_SECONDARY override defaults."""
        with patch.dict(
            "os.environ",
            {"LLM_PRIMARY": "nim", "LLM_SECONDARY": "quicksilver"},
            clear=True,
        ):
            p = resolve_policy_from_env()
            assert p.primary == "nim"
            assert p.secondary == "quicksilver"

    def test_custom_tertiary(self):
        """LLM_TERTIARY fills the third slot."""
        with patch.dict("os.environ", {"LLM_TERTIARY": "nim"}, clear=True):
            p = resolve_policy_from_env()
            assert p.tertiary == "nim"

    def test_allow_nim_for_assistant(self):
        """LLM_ALLOW_NIM_FOR_ASSISTANT=true sets the flag."""
        with patch.dict(
            "os.environ", {"LLM_ALLOW_NIM_FOR_ASSISTANT": "true"}, clear=True
        ):
            p = resolve_policy_from_env()
            assert p.allow_nim_for_assistant is True

    def test_failover_on_timeout_false(self):
        """LLM_FAILOVER_ON_TIMEOUT=false disables timeout failover."""
        with patch.dict(
            "os.environ", {"LLM_FAILOVER_ON_TIMEOUT": "false"}, clear=True
        ):
            p = resolve_policy_from_env()
            assert p.failover_on_timeout is False

    def test_health_cache_s(self):
        """LLM_HEALTH_CACHE_S overrides cache seconds."""
        with patch.dict("os.environ", {"LLM_HEALTH_CACHE_S": "60"}, clear=True):
            p = resolve_policy_from_env()
            assert p.health_cache_seconds == 60

    def test_router_chain_raw_override(self):
        """LLM_ROUTER_CHAIN overrides primary/secondary/tertiary."""
        with patch.dict(
            "os.environ",
            {"LLM_ROUTER_CHAIN": "nim,local,quicksilver"},
            clear=True,
        ):
            p = resolve_policy_from_env()
            assert p.primary == "nim"
            assert p.secondary == "local"
            assert p.tertiary == "quicksilver"

    def test_router_chain_partial(self):
        """LLM_ROUTER_CHAIN with 2 items sets primary+secondary only."""
        with patch.dict(
            "os.environ",
            {"LLM_ROUTER_CHAIN": "local,nim"},
            clear=True,
        ):
            p = resolve_policy_from_env()
            assert p.primary == "local"
            assert p.secondary == "nim"
            assert p.tertiary == ""


# ══════════════════════════════════════════════════════
# Task class chains
# ══════════════════════════════════════════════════════

class TestTaskClassChains:
    """DEFAULT_TASK_CHAINS define per-role backend ordering."""

    def test_assistant_chain(self):
        """assistant: quicksilver → local (NIM excluded by default)."""
        assert DEFAULT_TASK_CHAINS["assistant"] == ["quicksilver", "local"]

    def test_guardian_advisory_chain(self):
        """guardian_advisory: nim → local → quicksilver."""
        assert DEFAULT_TASK_CHAINS["guardian_advisory"] == [
            "nim", "local", "quicksilver",
        ]

    def test_offline_chain(self):
        """offline: local only."""
        assert DEFAULT_TASK_CHAINS["offline"] == ["local"]

    def test_sovereign_strict_chain(self):
        """sovereign_strict: local only (refuses cloud)."""
        assert DEFAULT_TASK_CHAINS["sovereign_strict"] == ["local"]


# ══════════════════════════════════════════════════════
# Level 0 reject
# ══════════════════════════════════════════════════════

class TestLevel0Tasks:
    """LEVEL_0_TASKS contains all deterministic protocol paths."""

    def test_level0_contains_poac(self):
        assert "poac" in LEVEL_0_TASKS

    def test_level0_contains_invariant_gate(self):
        assert "invariant_gate" in LEVEL_0_TASKS

    def test_level0_contains_chain_write(self):
        assert "chain_write" in LEVEL_0_TASKS

    def test_level0_contains_adjudication(self):
        assert "adjudication" in LEVEL_0_TASKS

    def test_level0_contains_events_root(self):
        assert "events_root" in LEVEL_0_TASKS

    def test_level0_contains_kas(self):
        assert "kas" in LEVEL_0_TASKS

    def test_level0_contains_classify(self):
        assert "classify" in LEVEL_0_TASKS

    def test_level0_frozen(self):
        """LEVEL_0_TASKS is a frozenset (immutable)."""
        with pytest.raises(AttributeError):
            LEVEL_0_TASKS.add("new_task")  # type: ignore


# ══════════════════════════════════════════════════════
# RoutingDecision
# ══════════════════════════════════════════════════════

class TestRoutingDecision:
    """RoutingDecision records the policy trace."""

    def test_decision_defaults(self):
        policy = RoutingPolicy()
        decision = RoutingDecision(
            policy=policy,
            chain_before_filter=["quicksilver", "local"],
            chain_after_filter=["quicksilver", "local"],
            skipped_reasons={},
            selected_backend="quicksilver",
            fallback_used=False,
        )
        assert decision.selected_backend == "quicksilver"
        assert decision.fallback_used is False
        assert decision.skipped_reasons == {}

    def test_decision_with_failover(self):
        policy = RoutingPolicy()
        decision = RoutingDecision(
            policy=policy,
            chain_before_filter=["quicksilver", "local"],
            chain_after_filter=["local"],
            skipped_reasons={"quicksilver": "timeout"},
            selected_backend="local",
            fallback_used=True,
        )
        assert decision.selected_backend == "local"
        assert decision.fallback_used is True
        assert decision.skipped_reasons["quicksilver"] == "timeout"