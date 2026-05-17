"""Phase 235.x-STABILITY-9 stage 5 (2026-05-17) — Startup-jitter primitive.

Centralized startup-jitter primitive that spreads the thundering-herd
of background agent first-polls across a configurable window. Eliminates
the boot STARVATION wave empirically observed at 13:25 (66 events over
7.5 min, 49.73s peak excess) by injecting `await asyncio.sleep(random)`
at the top of each thundering-herd contributor's run method.

Design discipline:
  - Reuses the canonical `random.uniform(0, max_s)` pattern from
    `bridge/vapi_bridge/batcher.py:510-512` (retry-jitter context;
    same statistical shape, different lifecycle)
  - No-op when `cfg.startup_jitter_enabled=False` (Q1 reactivation:
    one env flag flip reverts to pre-stage-5 thundering-herd)
  - Conservative max (default 30s) — well within loop_health_monitor's
    tolerance (check_interval_s=2.0, starvation_threshold_s=1.0; jitter
    fires ONCE at startup, not continuously)
  - Per-agent override via `max_jitter_s` kwarg (e.g. for agents that
    need tighter bounds because their work cadence is short)
  - Logs at debug level when active; never raises
  - Reproducible across restarts when cfg.startup_jitter_seed is set
    (for ceremony-grade audit reproducibility)

Usage:

    # Inside an async agent's run method:
    async def run_poll_loop(self):
        from .startup_grace import startup_grace
        await startup_grace(self._cfg, agent_name="MyAgentName")
        # ... rest of run loop
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
from typing import Optional

log = logging.getLogger(__name__)


# Module-level RNG (separate from global random for deterministic
# behavior under seed). Initialized lazily on first call.
_rng: Optional[random.Random] = None
_seed_logged: bool = False


def _get_rng(cfg) -> random.Random:
    """Lazy-init RNG with optional cfg.startup_jitter_seed.

    Default behavior (no seed): uses os.urandom-derived seed for
    each fresh process — jitter is non-deterministic across restarts.

    Seeded behavior (cfg.startup_jitter_seed set): jitter is
    reproducible across restarts, suitable for ceremony audit trails
    where exact boot timing must be reconstructable.
    """
    global _rng, _seed_logged
    if _rng is not None:
        return _rng
    seed_value = getattr(cfg, "startup_jitter_seed", "") or ""
    if seed_value:
        # Deterministic seed for reproducibility
        _rng = random.Random(seed_value)
        if not _seed_logged:
            log.info(
                "Phase 235.x-STABILITY-9 stage 5: startup_grace seeded "
                "with cfg.startup_jitter_seed (reproducible across restarts)"
            )
            _seed_logged = True
    else:
        # Default: process-fresh seed via os.urandom
        _rng = random.Random(os.urandom(16))
        if not _seed_logged:
            log.info(
                "Phase 235.x-STABILITY-9 stage 5: startup_grace using "
                "process-fresh seed (non-deterministic across restarts)"
            )
            _seed_logged = True
    return _rng


async def startup_grace(
    cfg,
    *,
    agent_name: str,
    max_jitter_s: Optional[float] = None,
) -> None:
    """Inject random startup delay [0, max_jitter_s] before agent's
    first work iteration.

    Args:
      cfg: vapi_bridge.config.Config (or test stub) — reads
           cfg.startup_jitter_enabled + cfg.startup_jitter_max_s
      agent_name: label for debug logging + observability
      max_jitter_s: per-agent override; defaults to
           cfg.startup_jitter_max_s (default 30.0s)

    Behavior:
      - cfg.startup_jitter_enabled=False → no-op (no sleep, no log)
      - cfg.startup_jitter_enabled=True  → await asyncio.sleep(jitter)
      - jitter = uniform(0, effective_max)
      - never raises (fail-open per stability discipline)
    """
    try:
        if not getattr(cfg, "startup_jitter_enabled", True):
            return
        effective_max = (
            max_jitter_s if max_jitter_s is not None
            else float(getattr(cfg, "startup_jitter_max_s", 30.0))
        )
        if effective_max <= 0.0:
            return
        rng = _get_rng(cfg)
        jitter_s = rng.uniform(0.0, effective_max)
        log.debug(
            "startup_grace: %s sleeping %.2fs (max=%.1fs)",
            agent_name, jitter_s, effective_max,
        )
        await asyncio.sleep(jitter_s)
    except Exception as exc:  # noqa: BLE001 — fail-open
        log.warning(
            "startup_grace: %s jitter sleep error (%s); proceeding without jitter",
            agent_name, exc,
        )


def reset_for_test() -> None:
    """Reset module-level RNG state. Called from tests that need a
    fresh deterministic seed per test (avoid cross-test seed leak)."""
    global _rng, _seed_logged
    _rng = None
    _seed_logged = False
