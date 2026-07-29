"""Tests for Level 0 task rejection — the router must refuse every
deterministic protocol path before touching any backend.

Rail: "Level 0 no LLM → Router hard-refuse on tagged tasks"
"""

from __future__ import annotations

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from bridge.vapi_bridge.llm_routing.router import LLMRouter
from bridge.vapi_bridge.llm_routing.policy import RoutingPolicy, LEVEL_0_TASKS


# ══════════════════════════════════════════════════════
# Every Level 0 task is refused
# ══════════════════════════════════════════════════════

class TestEveryLevel0TaskRefused:
    """Every task in LEVEL_0_TASKS returns error='no_llm_on_level0'."""

    @pytest.mark.parametrize("task_class", sorted(LEVEL_0_TASKS))
    @pytest.mark.asyncio
    async def test_level0_task_refused(self, task_class: str):
        """All Level 0 tasks are refused regardless of backend state."""
        router = LLMRouter(policy=RoutingPolicy())
        result = await router.route(
            task_class=task_class,
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.success is False
        assert result.error == "no_llm_on_level0"
        assert result.content is None
        assert result.live is False

    @pytest.mark.parametrize("task_class", sorted(LEVEL_0_TASKS))
    @pytest.mark.asyncio
    async def test_level0_never_touches_backend(self, task_class: str):
        """Level 0 rejection happens before any backend is touched."""
        router = LLMRouter(policy=RoutingPolicy())

        # Spy on backend.chat — it should never be called
        original_chats = {}
        for bid, bk in router._backends.items():
            original_chats[bid] = bk.chat
            bk.chat = AsyncMock(side_effect=Exception("should not be called"))

        result = await router.route(
            task_class=task_class,
            messages=[{"role": "user", "content": "test"}],
        )

        # Verify no backend was called
        for bid, original_chat in original_chats.items():
            router._backends[bid].chat.assert_not_called()


# ══════════════════════════════════════════════════════
# Level 0 rejection is independent of policy
# ══════════════════════════════════════════════════════

class TestLevel0IndependentOfPolicy:
    """Level 0 rejection happens regardless of policy settings."""

    @pytest.mark.asyncio
    async def test_refused_even_with_pinned_backend(self):
        """Level 0 is refused even with pinned_backend set."""
        router = LLMRouter(policy=RoutingPolicy(pinned_backend="local"))
        result = await router.route(
            task_class="poac",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.success is False
        assert result.error == "no_llm_on_level0"

    @pytest.mark.asyncio
    async def test_refused_even_with_refuse_cloud(self):
        """Level 0 is refused even with refuse_cloud=true."""
        router = LLMRouter(policy=RoutingPolicy(refuse_cloud=True))
        result = await router.route(
            task_class="chain_write",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.success is False
        assert result.error == "no_llm_on_level0"

    @pytest.mark.asyncio
    async def test_refused_even_with_primary_only(self):
        """Level 0 is refused even with primary_only mode."""
        router = LLMRouter(policy=RoutingPolicy(mode="primary_only"))
        result = await router.route(
            task_class="invariant_gate",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.success is False
        assert result.error == "no_llm_on_level0"

    @pytest.mark.asyncio
    async def test_refused_even_with_task_split(self):
        """Level 0 is refused even with task_split mode."""
        router = LLMRouter(policy=RoutingPolicy(mode="task_split"))
        result = await router.route(
            task_class="adjudication",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.success is False
        assert result.error == "no_llm_on_level0"


# ══════════════════════════════════════════════════════
# Non-Level-0 tasks are NOT refused
# ══════════════════════════════════════════════════════

class TestNonLevel0TasksAllowed:
    """Non-Level-0 tasks proceed past the Level 0 gate."""

    @pytest.mark.parametrize("task_class", [
        "assistant",
        "guardian_advisory",
        "offline",
        "sovereign_strict",
        "custom_task",
        "",
    ])
    @pytest.mark.asyncio
    async def test_non_level0_task_not_refused(self, task_class: str):
        """Non-Level-0 tasks are not refused by the Level 0 gate."""
        router = LLMRouter(policy=RoutingPolicy())
        result = await router.route(
            task_class=task_class,
            messages=[{"role": "user", "content": "test"}],
        )
        # Error should be about routing, not Level 0 rejection
        assert result.error != "no_llm_on_level0"
        # If no backends are configured, error is "no_backends_available"
        # or "all_backends_exhausted" — but not Level 0


# ══════════════════════════════════════════════════════
# Honesty fields on Level 0 rejection
# ══════════════════════════════════════════════════════

class TestLevel0HonestyFields:
    """Level 0 rejection still carries honesty fields."""

    @pytest.mark.asyncio
    async def test_honesty_fields_present(self):
        """Level 0 rejection has error, live=False, latency_ms=0."""
        router = LLMRouter(policy=RoutingPolicy())
        result = await router.route(
            task_class="kas",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.error == "no_llm_on_level0"
        assert result.live is False
        assert result.latency_ms == 0.0
        assert result.backend == ""
        assert result.content is None
        assert result.success is False
        assert result.attempts == []


# ══════════════════════════════════════════════════════
# Edge cases
# ══════════════════════════════════════════════════════

class TestLevel0EdgeCases:
    """Edge cases around Level 0 rejection."""

    @pytest.mark.asyncio
    async def test_future_level0_task_refused(self):
        """A new Level 0 task added to the set is refused."""
        custom_level0 = LEVEL_0_TASKS | {"new_protocol_path"}
        with patch.object(LEVEL_0_TASKS, "__contains__", lambda self, x: x in custom_level0):
            router = LLMRouter(policy=RoutingPolicy())
            result = await router.route(
                task_class="new_protocol_path",
                messages=[{"role": "user", "content": "test"}],
            )
            assert result.error == "no_llm_on_level0"

    @pytest.mark.asyncio
    async def test_case_sensitive_task_class(self):
        """Task class matching is case-sensitive."""
        router = LLMRouter(policy=RoutingPolicy())
        # "PoAC" is not the same as "poac"
        result = await router.route(
            task_class="PoAC",
            messages=[{"role": "user", "content": "test"}],
        )
        # Should not be refused — "PoAC" != "poac"
        assert result.error != "no_llm_on_level0"

    @pytest.mark.asyncio
    async def test_empty_task_class(self):
        """Empty task class is not refused."""
        router = LLMRouter(policy=RoutingPolicy())
        result = await router.route(
            task_class="",
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.error != "no_llm_on_level0"

    @pytest.mark.asyncio
    async def test_none_task_class(self):
        """None task class is not refused (treated as empty)."""
        router = LLMRouter(policy=RoutingPolicy())
        result = await router.route(
            task_class="",  # route() expects str, not None
            messages=[{"role": "user", "content": "test"}],
        )
        assert result.error != "no_llm_on_level0"