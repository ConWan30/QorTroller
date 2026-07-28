"""LLMRouter — three-tier backend router with explicit policy, failover, and provenance.

Routes requests through an ordered backend chain (QuickSilver, NIM, LOCAL)
with health tracking, cooldown, and honesty fields on every response.
"""

from __future__ import annotations

import asyncio
import hashlib
import time as _time
import uuid
import logging
from typing import Optional, Dict, Any, List

from .types import (
    RouteResult,
    ProvenanceRecord,
    BackendId,
    TaskClass,
)
from .policy import (
    RoutingPolicy,
    RoutingDecision,
    LEVEL_0_TASKS,
    resolve_policy_from_env,
)
from .health import HealthCache
from .backends.quicksilver import QuickSilverBackend
from .backends.nim import NimBackend
from .backends.local import LocalBackend

log = logging.getLogger(__name__)


class LLMRouter:
    """Three-tier backend router.

    One router, three backends, explicit policy. Every response carries
    honesty fields so the caller knows exactly where the answer came from.
    """

    def __init__(
        self,
        policy: Optional[RoutingPolicy] = None,
    ) -> None:
        """Initialize the router.

        Args:
            policy: Routing policy. If None, resolved from env vars.
        """
        self._policy = policy or resolve_policy_from_env()

        # ── Register backends ────────────────────────
        self._backends: Dict[str, Any] = {}
        self._register(QuickSilverBackend())
        self._register(NimBackend())
        self._register(LocalBackend())

        # ── Health cache ─────────────────────────────
        self._health = HealthCache(cache_seconds=self._policy.health_cache_seconds)
        for bid, bk in self._backends.items():
            self._health.register(bid, bk)

        # ── Build the active chain ───────────────────
        self._chain = self._build_chain()

        log.info(
            "LLMRouter initialized: mode=%s chain=%s",
            self._policy.mode, self._chain,
        )

    # ── Registration ──────────────────────────────────

    def _register(self, backend: Any) -> None:
        """Register a backend adapter."""
        self._backends[backend.id] = backend

    # ── Chain building ────────────────────────────────

    def _build_chain(self) -> List[str]:
        """Build the ordered chain from policy + configured backends.

        Order: PRIMARY → SECONDARY → TERTIARY → remaining configured.
        Filter: only configured() backends survive.
        Policy rails applied: refuse_cloud, excluded_backends, pinned.
        """
        policy = self._policy

        # Pinned backend bypasses all chain logic
        if policy.pinned_backend:
            return [policy.pinned_backend]

        # Collect configured backends
        available = [
            bid for bid, bk in self._backends.items()
            if bk.configured()
        ]

        # Build explicit slots from PRIMARY/SECONDARY/TERTIARY
        explicit = []
        for slot in [policy.primary, policy.secondary, policy.tertiary]:
            if slot and slot in available:
                explicit.append(slot)
                available.remove(slot)

        # Append remaining configured backends (e.g. nim if not in slots)
        explicit.extend(available)

        # Apply policy rails
        if policy.excluded_backends:
            explicit = [b for b in explicit if b not in policy.excluded_backends]

        if policy.refuse_cloud:
            explicit = [b for b in explicit if b not in ("quicksilver", "nim")]

        # Reorder cheapest-first if policy says so
        if policy.prefer_cheapest:
            _COST_ORDER = {"local": 0, "nim": 1, "quicksilver": 2}
            explicit.sort(key=lambda b: _COST_ORDER.get(b, 99))

        return explicit

    # ── Public API ────────────────────────────────────

    async def route(
        self,
        task_class: str,
        messages: List[Dict[str, str]],
        tools: Optional[List[Dict[str, Any]]] = None,
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> RouteResult:
        """Route a chat completion through the backend chain.

        Args:
            task_class: Routing class. Drives chain selection.
                        One of: assistant, guardian_advisory, offline,
                        sovereign_strict. Level 0 tasks are refused.
            messages: OpenAI-shaped message array.
            tools: Optional tool definitions.
            temperature: 0.0 = deterministic, 1.0 = creative.
            max_tokens: Maximum response tokens.

        Returns:
            RouteResult with content, provider, honesty fields, provenance.
        """
        start = _time.time()

        # ── Rule 1: Level 0 reject ───────────────────
        if task_class in LEVEL_0_TASKS:
            return RouteResult(
                content=None,
                success=False,
                error="no_llm_on_level0",
                backend="",
                route_mode=self._policy.mode,
                latency_ms=0.0,
                live=False,
            )

        # ── Rule 2: Resolve chain ────────────────────
        chain = self._resolve_chain(task_class)
        if not chain:
            return RouteResult(
                content=None,
                success=False,
                error="no_backends_available",
                backend="",
                route_mode=self._policy.mode,
                latency_ms=(_time.time() - start) * 1000,
                live=False,
            )

        decision = RoutingDecision(
            policy=self._policy,
            chain_before_filter=list(chain),
            chain_after_filter=list(chain),
            skipped_reasons={},
            selected_backend=None,
            fallback_used=False,
        )

        # ── Extract prompt text for hash tracking ────
        prompt_text = " ".join(
            m.get("content", "") for m in messages[-2:]
        )

        # ── Rule 3: Walk the chain ───────────────────
        for backend_id in chain:
            backend = self._backends[backend_id]

            # Capability check
            if tools and "TOOLS" not in backend.capabilities:
                decision.skipped_reasons[backend_id] = "no_tools"
                continue

            # Availability check (cached health)
            if not self._is_available(backend_id):
                decision.skipped_reasons[backend_id] = "unavailable"
                continue

            # Try the backend
            try:
                response = await asyncio.wait_for(
                    backend.chat(
                        messages=messages,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    ),
                    timeout=self._policy.timeout_seconds,
                )
            except asyncio.TimeoutError:
                if self._policy.failover_on_timeout:
                    self._record_failure(backend_id)
                    decision.skipped_reasons[backend_id] = "timeout"
                    continue
                return RouteResult(
                    content=None, backend=backend_id,
                    success=False, error="timeout",
                    route_mode=self._policy.mode,
                    latency_ms=(_time.time() - start) * 1000,
                    live=False,
                )
            except Exception as exc:
                # Network-level failure → failover
                if self._is_network_error(exc):
                    self._record_failure(backend_id)
                    decision.skipped_reasons[backend_id] = str(exc)
                    continue
                # Auth or client error → fail honest
                return RouteResult(
                    content=None, backend=backend_id,
                    success=False, error=str(exc),
                    route_mode=self._policy.mode,
                    latency_ms=(_time.time() - start) * 1000,
                    live=False,
                )

            # ── Rule 4: Handle response ──────────────
            if response and "choices" in response:
                elapsed = (_time.time() - start) * 1000
                choice = response["choices"][0]
                content = choice["message"]["content"]
                model = response.get("model", "")
                usage = response.get("usage", {})

                decision.selected_backend = backend_id
                decision.fallback_used = backend_id != self._policy.primary

                # Record success → reset health
                self._record_success(backend_id)

                # Check if backend was degraded
                bh = self._health.get_health(backend_id)
                degraded = bh is not None and bh.state == "DEGRADED"

                return RouteResult(
                    content=content,
                    backend=backend_id,
                    model=model,
                    route_mode=self._policy.mode,
                    primary_attempted=self._policy.primary,
                    attempts=list(decision.skipped_reasons.keys()),
                    fallback_used=decision.fallback_used,
                    degraded=degraded,
                    latency_ms=elapsed,
                    live=True,
                    success=True,
                    error=None,
                    provenance=ProvenanceRecord(
                        call_id=self._generate_call_id(),
                        timestamp=start,
                        backend=backend_id,
                        model=model,
                        route_mode=self._policy.mode,
                        attempts=list(decision.skipped_reasons.keys()),
                        fallback_used=decision.fallback_used,
                        latency_ms=elapsed,
                    ),
                )

            # Empty response → failover
            self._record_failure(backend_id)
            decision.skipped_reasons[backend_id] = "empty_response"
            continue

        # ── Rule 5: All backends exhausted ───────────
        decision.fallback_used = True
        elapsed = (_time.time() - start) * 1000

        return RouteResult(
            content=None,
            backend="fallback",
            success=False,
            error="all_backends_exhausted",
            route_mode=self._policy.mode,
            primary_attempted=self._policy.primary,
            attempts=list(decision.skipped_reasons.keys()),
            fallback_used=True,
            latency_ms=elapsed,
            live=False,
            provenance=ProvenanceRecord(
                call_id=self._generate_call_id(),
                timestamp=start,
                backend="fallback",
                model="",
                route_mode=self._policy.mode,
                attempts=list(decision.skipped_reasons.keys()),
                fallback_used=True,
                latency_ms=elapsed,
            ),
        )

    # ── Task-aware chain resolution ───────────────────

    def _resolve_chain(self, task_class: str) -> List[str]:
        """Resolve the backend chain for a given task class.

        In task_split mode, uses the task class table.
        Otherwise, uses the built chain from PRIMARY/SECONDARY/TERTIARY.
        """
        if self._policy.mode == "task_split" and task_class in self._policy.task_chain:
            return list(self._policy.task_chain[task_class])
        return list(self._chain)

    # ── Health tracking ───────────────────────────────

    def _is_available(self, backend_id: str) -> bool:
        """Check if a backend is available, using cached health."""
        return self._health.is_healthy(backend_id)

    def _record_failure(self, backend_id: str) -> None:
        """Record a failure and update health state."""
        self._health.record_failure(
            backend_id,
            max_failures=self._policy.max_failures,
            cooldown_seconds=self._policy.cooldown_seconds,
        )

    def _record_success(self, backend_id: str) -> None:
        """Record a success and reset health state."""
        self._health.record_success(backend_id)

    # ── Error classification ──────────────────────────

    @staticmethod
    def _is_network_error(exc: Exception) -> bool:
        """Check if an exception is a network-level failure.

        Network errors trigger failover. Auth/client errors do not.
        """
        exc_name = type(exc).__name__
        exc_str = str(exc).lower()

        network_indicators = [
            "connection", "refused", "reset", "timeout",
            "eof", "broken pipe", "dns", "resolve",
            "5", "500", "502", "503", "504",  # 5xx server errors
        ]
        return any(ind in exc_name.lower() or ind in exc_str for ind in network_indicators)

    # ── Helpers ───────────────────────────────────────

    @staticmethod
    def _generate_call_id() -> str:
        """Generate a unique call ID for provenance."""
        ts = int(_time.time())
        return f"llm_{ts}_{uuid.uuid4().hex[:8]}"

    # ── Policy access ─────────────────────────────────

    @property
    def policy(self) -> RoutingPolicy:
        """The current routing policy."""
        return self._policy

    @property
    def chain(self) -> List[str]:
        """The current active backend chain."""
        return list(self._chain)

    @property
    def backends(self) -> Dict[str, Any]:
        """Registered backends."""
        return dict(self._backends)