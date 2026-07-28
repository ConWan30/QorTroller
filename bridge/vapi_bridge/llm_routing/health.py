"""Cached health probes for backend reachability.

The router polls backends on a configurable interval and caches results.
Per-request is_available() checks use the cache — no I/O on the hot path.
"""

from __future__ import annotations

import time as _time
import logging
from typing import Dict, Optional, Any

from .types import BackendHealth

log = logging.getLogger(__name__)


class HealthCache:
    """Cached health probes for registered backends.

    Usage:
        cache = HealthCache(cache_seconds=30)
        cache.register("quicksilver", backend_instance)
        status = await cache.probe("quicksilver")  # probes + caches
        ok = cache.is_healthy("quicksilver")       # uses cache, no I/O
    """

    def __init__(self, cache_seconds: int = 30) -> None:
        self._cache_seconds = cache_seconds
        self._backends: Dict[str, Any] = {}
        self._health: Dict[str, BackendHealth] = {}
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._last_probe: Dict[str, float] = {}

    def register(self, backend_id: str, backend: Any) -> None:
        """Register a backend for health tracking."""
        self._backends[backend_id] = backend
        self._health[backend_id] = BackendHealth()
        self._cache[backend_id] = {"ok": False, "error": "not yet probed"}
        self._last_probe[backend_id] = 0.0

    def unregister(self, backend_id: str) -> None:
        """Remove a backend from health tracking."""
        self._backends.pop(backend_id, None)
        self._health.pop(backend_id, None)
        self._cache.pop(backend_id, None)
        self._last_probe.pop(backend_id, None)

    # ── Probing ──────────────────────────────────────

    async def probe(self, backend_id: str) -> Dict[str, Any]:
        """Probe a backend's health and cache the result.

        Returns the cached health status (dict with 'ok', 'latency_ms',
        'model', 'error').
        """
        backend = self._backends.get(backend_id)
        if not backend:
            result = {"ok": False, "error": "unknown backend"}
            self._cache[backend_id] = result
            return result

        try:
            status = await backend.health()
            result = {
                "ok": status.ok,
                "latency_ms": status.latency_ms,
                "model": status.model,
                "error": status.error,
            }
        except Exception as exc:
            log.warning("Health probe failed for %s: %s", backend_id, exc)
            result = {"ok": False, "error": str(exc)}

        self._cache[backend_id] = result
        self._last_probe[backend_id] = _time.time()
        return result

    async def probe_all(self) -> Dict[str, Dict[str, Any]]:
        """Probe all registered backends and return results."""
        results = {}
        for backend_id in self._backends:
            results[backend_id] = await self.probe(backend_id)
        return results

    # ── Cache reads (no I/O) ─────────────────────────

    def is_healthy(self, backend_id: str) -> bool:
        """Check if a backend is healthy, using cached data.

        Returns True if the cache is fresh AND ok=True.
        Returns False if the cache is stale, missing, or ok=False.
        This is the method the router calls on the hot path.
        """
        health = self._health.get(backend_id)
        if not health:
            return False

        # Check cooldown
        if health.state == "COOLDOWN":
            if _time.time() < health.cooldown_until:
                return False
            health.state = "UNKNOWN"
            health.failures = 0

        # If state is already known bad, return fast
        if health.state in ("UNHEALTHY", "COOLDOWN"):
            return False

        # Check cache freshness
        last = self._last_probe.get(backend_id, 0.0)
        if _time.time() - last > self._cache_seconds:
            # Cache is stale — return True for UNKNOWN/DEGRADED
            # (the router will probe on the next health interval)
            return health.state in ("UNKNOWN", "HEALTHY", "DEGRADED")

        # Cache is fresh — use cached ok value
        cached = self._cache.get(backend_id, {})
        return cached.get("ok", False)

    def get_health(self, backend_id: str) -> Optional[BackendHealth]:
        """Get the full health state for a backend."""
        return self._health.get(backend_id)

    def get_all_health(self) -> Dict[str, BackendHealth]:
        """Get health state for all backends."""
        return dict(self._health)

    # ── Health state mutations ───────────────────────

    def record_failure(self, backend_id: str, max_failures: int = 3, cooldown_seconds: int = 300) -> None:
        """Record a failure and update health state."""
        health = self._health.get(backend_id)
        if not health:
            return

        health.failures += 1
        health.last_failure = _time.time()

        if health.failures >= max_failures:
            health.state = "COOLDOWN"
            health.cooldown_until = _time.time() + cooldown_seconds
            log.warning(
                "Backend %s entered COOLDOWN (%ds)",
                backend_id, cooldown_seconds,
            )
        elif health.failures >= 1:
            health.state = "DEGRADED"

    def record_success(self, backend_id: str) -> None:
        """Record a success and reset health state."""
        health = self._health.get(backend_id)
        if not health:
            return

        health.state = "HEALTHY"
        health.failures = 0
        health.last_success = _time.time()

    # ── Status summary ───────────────────────────────

    def summary(self) -> Dict[str, Any]:
        """Get a human-readable summary of all backend health."""
        return {
            bid: {
                "state": h.state,
                "failures": h.failures,
                "last_success": h.last_success,
                "cooldown_remaining": max(0.0, h.cooldown_until - _time.time()) if h.state == "COOLDOWN" else 0.0,
            }
            for bid, h in self._health.items()
        }