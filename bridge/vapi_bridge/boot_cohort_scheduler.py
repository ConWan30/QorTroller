"""Phase 235.x-STABILITY-9 stage 10 (2026-05-17) — Deterministic boot-
cohort slot scheduler.

Stages 6-9 progressively narrowed the STARVATION search:
  Stage 6: cleared Curator Task 6/7
  Stage 7: cleared individual first-fire compute
  Stage 8: cleared ChainReconciler SQLite (0 SLOW SQLITE batch markers)
  Stage 9: capped chain RPC tail latency (17.6s → 9.4s peak)

The remaining 52-54s peak STARVATION fires at boot+2:00-2:30 in EVERY
observation window, BEFORE ChainReconciler runs its first instrumented
call. The blocker is no longer a per-function bug — it's the boot moment
itself: ~17 absorbed + standalone agents all firing their first cycle
within the same 5-30s window after boot, colliding on httpx pool +
ThreadPoolExecutor + asyncio scheduler.

Stage 5 attempted to solve this with RANDOM jitter `[0, max_jitter_s]`,
but uniform draws of N=17 over a 30s window are statistically clustered
(last observation: 4-5 agents fired in seconds 25-29 of the window).

This module replaces random jitter with DETERMINISTIC slot scheduling:

  Slot 0  → boot + 0   * spacing  = boot +  0s
  Slot 1  → boot + 1   * spacing  = boot +  5s
  Slot 2  → boot + 2   * spacing  = boot + 10s
  ...
  Slot 16 → boot + 16  * spacing  = boot + 80s

Slot assignment is stable across restarts because agents are assigned
slots in deterministic registration order (main.py boots in fixed
sequence; first-come-first-served slot allocation is reproducible).

Design discipline:
  - Singleton: one scheduler per process; module-level `get_scheduler()`.
  - Stdlib only.
  - O(1) lookup after first registration; O(N) memory.
  - Reversible via cfg.boot_cohort_scheduler_enabled (default True).
  - Q2 preserved: only the FIRST fire is offset; original cadences
    apply to all subsequent invocations.
  - Q1 preserved: BOOT_COHORT_SCHEDULER_ENABLED=false reverts every
    caller to its stage-5 random-jitter fallback in a single env flip.
"""
from __future__ import annotations

import logging
import threading
from typing import Dict, Optional

log = logging.getLogger(__name__)


class BootCohortScheduler:
    """Singleton-per-process deterministic slot scheduler.

    Usage:
      scheduler = get_scheduler(cfg)
      offset_s = scheduler.first_fire_offset_for("ChainReconciler")
      # offset_s is deterministic: scheduler assigns next slot * spacing.

    Re-requesting the same name returns the same offset (cached).
    """

    def __init__(self, *, spacing_s: float = 5.0, enabled: bool = True) -> None:
        self._spacing_s = float(spacing_s)
        self._enabled = bool(enabled)
        self._slots: Dict[str, int] = {}
        self._next_slot: int = 0
        self._lock = threading.Lock()
        log.info(
            "[BootCohortScheduler] STAGE-10 initialized "
            "(enabled=%s, spacing_s=%.1fs)",
            self._enabled, self._spacing_s,
        )

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def spacing_s(self) -> float:
        return self._spacing_s

    def first_fire_offset_for(self, agent_name: str) -> float:
        """Return deterministic first-fire offset (seconds since boot)
        for `agent_name`.

        When disabled: returns 0.0 (caller falls back to its own jitter).
        When enabled: returns slot_index * spacing_s. Same name always
        returns same offset within the process lifetime.
        """
        if not self._enabled:
            return 0.0
        with self._lock:
            if agent_name not in self._slots:
                self._slots[agent_name] = self._next_slot
                self._next_slot += 1
                log.debug(
                    "[BootCohortScheduler] STAGE-10 assigned slot=%d "
                    "to agent='%s' (offset=%.1fs)",
                    self._slots[agent_name], agent_name,
                    self._slots[agent_name] * self._spacing_s,
                )
            return self._slots[agent_name] * self._spacing_s

    def get_state_summary(self) -> Dict[str, object]:
        """Read-only snapshot for /operator/* endpoints."""
        with self._lock:
            return {
                "enabled":      self._enabled,
                "spacing_s":    self._spacing_s,
                "slots_used":   len(self._slots),
                "next_slot":    self._next_slot,
                "max_offset_s": (
                    (self._next_slot - 1) * self._spacing_s
                    if self._next_slot > 0 else 0.0
                ),
                "assignments":  dict(self._slots),
            }


# Singleton: one scheduler per process.
_singleton: Optional[BootCohortScheduler] = None
_singleton_lock = threading.Lock()


def get_scheduler(cfg=None) -> BootCohortScheduler:
    """Return the process-singleton scheduler. Lazy-init from cfg on
    first call; subsequent calls return the same instance (cfg ignored
    after first construction)."""
    global _singleton
    if _singleton is not None:
        return _singleton
    with _singleton_lock:
        if _singleton is not None:
            return _singleton
        spacing = float(getattr(cfg, "boot_cohort_spacing_s", 5.0)) if cfg else 5.0
        enabled = bool(getattr(cfg, "boot_cohort_scheduler_enabled", True)) if cfg else True
        _singleton = BootCohortScheduler(spacing_s=spacing, enabled=enabled)
        return _singleton


def reset_for_test() -> None:
    """Reset singleton — for tests only."""
    global _singleton
    with _singleton_lock:
        _singleton = None
