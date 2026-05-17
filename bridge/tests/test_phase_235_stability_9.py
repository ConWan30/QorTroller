"""Phase 235.x-STABILITY-9 (2026-05-17) — bisection instrument tests.

Tests the MINIMAL_TASK_MODE cfg flag + main.py wiring that lets us
boot the bridge with only uvicorn + loop_health_monitor (no agent
tasks) to establish a baseline for the residual 50-70s
loop_starvation events surfacing after STABILITY-8.

Strategy: STABILITY-9 is structural — it doesn't try to fix the
freezes directly. It gives the operator a clean baseline so the
freezes' source can be localized by incremental re-enablement.
"""
import os
from pathlib import Path

import pytest

from bridge.vapi_bridge.config import Config


_MAIN_PY = Path(__file__).resolve().parents[1] / "vapi_bridge" / "main.py"


def test_t_235_stab9_1_default_off() -> None:
    """minimal_task_mode default is False (production preserved)."""
    os.environ.pop("MINIMAL_TASK_MODE", None)
    cfg = Config()
    assert getattr(cfg, "minimal_task_mode", None) is False


def test_t_235_stab9_2_env_true_enables() -> None:
    """MINIMAL_TASK_MODE=true env flips the flag."""
    os.environ["MINIMAL_TASK_MODE"] = "true"
    try:
        cfg = Config()
        assert cfg.minimal_task_mode is True
    finally:
        os.environ.pop("MINIMAL_TASK_MODE", None)


def test_t_235_stab9_3_env_false_disables() -> None:
    """MINIMAL_TASK_MODE=false env keeps disabled."""
    os.environ["MINIMAL_TASK_MODE"] = "false"
    try:
        cfg = Config()
        assert cfg.minimal_task_mode is False
    finally:
        os.environ.pop("MINIMAL_TASK_MODE", None)


def test_t_235_stab9_4_main_short_circuit_present() -> None:
    """main.py contains the minimal_task_mode short-circuit block."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    assert 'getattr(self.cfg, "minimal_task_mode", False)' in src
    assert "MINIMAL_TASK_MODE=true" in src
    assert "skipping ALL" in src or "skipping all" in src.lower()


def test_t_235_stab9_5_loop_health_hoisted_above_dualshock() -> None:
    """loop_health_monitor is spawned BEFORE the DualShock block
    (so it observes the loop from the earliest possible point AND
    cooperates with the minimal_task_mode short-circuit that follows
    the spawn but precedes DualShock + every other agent)."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    idx_loop_health = src.find("from .loop_health_monitor import")
    idx_dualshock_block = src.find("if self.cfg.dualshock_enabled:")
    assert idx_loop_health > 0, "loop_health_monitor import missing"
    assert idx_dualshock_block > 0, "DualShock block missing"
    assert idx_loop_health < idx_dualshock_block, (
        "loop_health_monitor must spawn BEFORE the DualShock block "
        "(STABILITY-9 invariant — observer must run before observed)"
    )


def test_t_235_stab9_6_single_loop_health_spawn() -> None:
    """There is EXACTLY ONE loop_health_monitor task spawn in main.py
    (the hoisted v0 version — the old v3 block at line ~1740 was
    removed to avoid double-spawn)."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    count = src.count("from .loop_health_monitor import run_loop_health_monitor")
    assert count == 1, (
        f"Expected exactly 1 loop_health_monitor spawn in main.py, "
        f"got {count} — duplicate spawn risks dual-heartbeat noise"
    )


def test_t_235_stab9_7_short_circuit_uses_asyncio_event() -> None:
    """The minimal_task_mode short-circuit parks the coroutine on
    asyncio.Event().wait() rather than returning immediately —
    necessary because bridge.run() is the coroutine uvicorn lives
    under; returning would tear down the server."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    # The short-circuit block is small + nearby; just confirm
    # the pattern appears at least once.
    assert "asyncio.Event().wait()" in src, (
        "minimal_task_mode short-circuit must park the coroutine — "
        "otherwise bridge.run() returns + uvicorn server task is "
        "garbage-collected"
    )
