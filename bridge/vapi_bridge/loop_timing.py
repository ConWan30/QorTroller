"""Phase 235.x-STABILITY-9 stage 7 (2026-05-17) — Shared loop-timing primitive.

Generalizes the stage 6 `_timed_curator_task` + `_timed_db_block` helpers
into a single contextmanager `timed_block` reusable across multiple
agent instrumentation sites. Used by:

- corpus_curator_agent.py    (stage 6 backward-compat shims)
- agent_calibration_monitor.py (stage 7 — _run_all_tests + per-test)
- protocol_intelligence_agent.py (stage 7 — _compute_and_store)
- operator_steward_absorbed_agents.py (stage 7 — tick_all + per-spec)

Discipline:
- Monotonic timing (time.monotonic) for duration; time.time_ns for wall.
- threading.get_ident() for thread identity (cross-thread correlation).
- Searchable prefix per stage (STAGE-6 / STAGE-7) — operators grep
  bridge logs by prefix to localize an offender after a starvation
  event.
- always_info=True for task-body wrappers (curator + ACIM + PIA + ticker
  outer): one INFO line per cycle is cheap + invaluable for steady-state
  baseline.
- always_info=False for sub-block sites (DB calls + per-test + per-spec):
  silent under threshold to avoid log spam; WARNING when over.
- WARNING message includes `hint` string so the operator gets investigation
  guidance inline (e.g. "WAL contention" vs "compute saturation").
- Helpers fail-passthrough on inner exceptions — never swallow.
"""
from __future__ import annotations

import collections
import contextlib
import logging
import os
import threading
import time
from typing import Iterator, Optional


# ---- D1 loop-starvation attribution ring (LOOP_STARVATION_ATTRIBUTION_ENABLED, default OFF) ----------
# timed_block appends each exit {label, dur_s, tid, wall_ns} to a bounded ring; run_loop_health_monitor
# dumps the top-K by dur_s on a starvation event to NAME the loop-blocking sync sources (D1). Default OFF
# => one bool check per timed_block exit (no ring append), byte-identical. O(1) deque append when on.
_ATTRIBUTION_RING_MAX = 256
_attribution_ring = collections.deque(maxlen=_ATTRIBUTION_RING_MAX)
_attribution_enabled = str(os.environ.get("LOOP_STARVATION_ATTRIBUTION_ENABLED", "0")).strip().lower() \
    in ("1", "true", "yes", "on")


def set_attribution_enabled(on: bool) -> None:
    """Toggle the D1 attribution ring at runtime (also read from the env flag at import)."""
    global _attribution_enabled
    _attribution_enabled = bool(on)


def attribution_enabled() -> bool:
    return _attribution_enabled


# ---- D1.1 loop-thread tid (set by run_loop_health_monitor on the event-loop thread) ------------------
# Worker threads (qt-dense-cand, classify-burst, HID reader) can call timed_block-wrapped code too, but
# their blocks do NOT starve the asyncio loop. Recording the loop tid lets the starvation dump filter to
# loop-thread offenders so worker-thread time never masks the real blocker.
_loop_tid: Optional[int] = None


def set_loop_tid(tid: Optional[int]) -> None:
    global _loop_tid
    _loop_tid = tid


def loop_tid() -> Optional[int]:
    return _loop_tid


def recent_blocks(since_wall_ns: Optional[int] = None,
                  loop_tid_only: Optional[int] = None) -> list:
    """Snapshot of ring entries (optionally wall_ns >= since_wall_ns, and/or tid == loop_tid_only)."""
    src = list(_attribution_ring)
    if since_wall_ns is not None:
        src = [b for b in src if b["wall_ns"] >= since_wall_ns]
    if loop_tid_only is not None:
        src = [b for b in src if b["tid"] == loop_tid_only]
    return src


def top_blocks(k: int = 5, since_wall_ns: Optional[int] = None,
               loop_tid_only: Optional[int] = None) -> list:
    """Top-K ring entries by duration -- the starvation-window offenders (optionally loop-tid-filtered)."""
    return sorted(recent_blocks(since_wall_ns, loop_tid_only),
                  key=lambda b: b["dur_s"], reverse=True)[:k]


@contextlib.contextmanager
def timed_block(
    label: str,
    *,
    warn_s: float,
    logger: logging.Logger,
    prefix: str = "[STAGE-7]",
    always_info: bool = False,
    hint: Optional[str] = None,
    slow_word: str = "SLOW",
) -> Iterator[None]:
    """Time a code block; log INFO and/or WARNING based on duration.

    Args:
      label:       site name; appears in every log line (after slow_word)
      warn_s:      WARNING threshold (seconds); exceeded → log.warning
      logger:      caller's logger (module-scoped log handlers apply)
      prefix:      caller-supplied log-line prefix INCLUDING brackets if
                   desired; default "[STAGE-7]". Stage 6 backward-compat
                   wrappers pass "[CorpusDataCuratorAgent] STAGE-6" so
                   existing operator grep patterns continue to match.
      always_info: True → log INFO line on every exit (cycle visibility);
                   False → silent under threshold (avoid spam on hot path)
      hint:        optional investigation hint added to WARNING message
                   (e.g. "WAL contention", "compute saturation")
      slow_word:   WARNING kind word — defaults "SLOW"; stage 6 wrappers
                   pass "SLOW TASK" / "SLOW DB" to preserve grep patterns.

    Behavior:
      - Wraps body in try/finally so timing always recorded.
      - Inner exceptions re-raise verbatim (never swallowed).
      - WARNING never raises out (logger errors swallowed).

    Message formats produced:
      WARNING: "<prefix> <slow_word>: <label> took <dur>s (tid=N, "
               "wall_start_ns=N, warn_threshold=<warn>s)[ — <hint>]"
      INFO:    "<prefix>: <label> duration=<dur>s (tid=N)"
    """
    t_start = time.monotonic()
    wall_ns = time.time_ns()
    tid = threading.get_ident()
    try:
        yield
    finally:
        dur_s = time.monotonic() - t_start
        if _attribution_enabled:                           # D1: name-the-offender ring (O(1) append)
            _attribution_ring.append({"label": label, "dur_s": round(dur_s, 4),
                                      "tid": tid, "wall_ns": wall_ns})
        try:
            if dur_s > warn_s:
                _hint = f" — {hint}" if hint else ""
                logger.warning(
                    "%s %s: %s took %.3fs (tid=%d, wall_start_ns=%d, "
                    "warn_threshold=%.2fs)%s",
                    prefix, slow_word, label, dur_s, tid, wall_ns,
                    warn_s, _hint,
                )
            elif always_info:
                logger.info(
                    "%s: %s duration=%.3fs (tid=%d)",
                    prefix, label, dur_s, tid,
                )
        except Exception:  # noqa: BLE001 — logger must not raise out of finally
            pass
