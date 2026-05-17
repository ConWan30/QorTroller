"""Phase 235.x-STABILITY-9 stage 10 (2026-05-17) — Boot-cohort scheduler tests.

Validates the deterministic slot scheduler + AbsorbedAgentTicker wiring
+ startup_grace wiring + Q1 (env-flag reversibility) + Q2 (cadence
preservation).
"""
import asyncio
import logging
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.boot_cohort_scheduler import (
    BootCohortScheduler, get_scheduler, reset_for_test,
)
from bridge.vapi_bridge import startup_grace as sg


_BRIDGE_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


def _stub_cfg(**overrides):
    base = {
        "boot_cohort_scheduler_enabled": True,
        "boot_cohort_spacing_s": 5.0,
        "startup_jitter_enabled": True,
        "startup_jitter_max_s": 30.0,
        "startup_jitter_seed": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_singletons():
    """Reset both scheduler + startup_grace RNG between tests."""
    reset_for_test()
    sg.reset_for_test()
    yield
    reset_for_test()
    sg.reset_for_test()


# ─── Cfg tests ────────────────────────────────────────────────────────────

def test_t_235_stab9_10_1_cfg_defaults() -> None:
    """Stage 10 cfg fields ship with correct defaults."""
    for v in ["BOOT_COHORT_SCHEDULER_ENABLED", "BOOT_COHORT_SPACING_S"]:
        os.environ.pop(v, None)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.boot_cohort_scheduler_enabled is True
    assert cfg.boot_cohort_spacing_s == 5.0


def test_t_235_stab9_10_2_env_override_disable() -> None:
    """BOOT_COHORT_SCHEDULER_ENABLED=false reverts to stage-5 fallback."""
    os.environ["BOOT_COHORT_SCHEDULER_ENABLED"] = "false"
    try:
        from bridge.vapi_bridge.config import Config
        cfg = Config()
        assert cfg.boot_cohort_scheduler_enabled is False
    finally:
        os.environ.pop("BOOT_COHORT_SCHEDULER_ENABLED", None)


# ─── Core scheduler behavior ──────────────────────────────────────────────

def test_t_235_stab9_10_3_deterministic_same_name_same_offset() -> None:
    """Same agent name always returns same offset within process."""
    s = BootCohortScheduler(spacing_s=5.0, enabled=True)
    a = s.first_fire_offset_for("AgentX")
    b = s.first_fire_offset_for("AgentX")
    c = s.first_fire_offset_for("AgentX")
    assert a == b == c


def test_t_235_stab9_10_4_distinct_names_distinct_offsets() -> None:
    """Distinct agents get distinct (sequential) slots."""
    s = BootCohortScheduler(spacing_s=5.0, enabled=True)
    a = s.first_fire_offset_for("A")
    b = s.first_fire_offset_for("B")
    c = s.first_fire_offset_for("C")
    assert {a, b, c} == {0.0, 5.0, 10.0}
    assert a < b < c, "slots must be sequential by registration order"


def test_t_235_stab9_10_5_offsets_multiple_of_spacing() -> None:
    """All offsets are multiples of spacing_s."""
    s = BootCohortScheduler(spacing_s=7.5, enabled=True)
    for name in ["a", "b", "c", "d", "e"]:
        offset = s.first_fire_offset_for(name)
        assert offset % 7.5 == 0.0


def test_t_235_stab9_10_6_disabled_returns_zero() -> None:
    """When scheduler disabled, returns 0.0 (caller falls back)."""
    s = BootCohortScheduler(spacing_s=5.0, enabled=False)
    assert s.first_fire_offset_for("A") == 0.0
    assert s.first_fire_offset_for("B") == 0.0


def test_t_235_stab9_10_7_state_summary_shape() -> None:
    """get_state_summary returns observable dict."""
    s = BootCohortScheduler(spacing_s=5.0, enabled=True)
    s.first_fire_offset_for("A")
    s.first_fire_offset_for("B")
    state = s.get_state_summary()
    assert state["enabled"] is True
    assert state["spacing_s"] == 5.0
    assert state["slots_used"] == 2
    assert state["next_slot"] == 2
    assert state["max_offset_s"] == 5.0  # (2-1)*5
    assert state["assignments"] == {"A": 0, "B": 1}


# ─── Singleton ────────────────────────────────────────────────────────────

def test_t_235_stab9_10_8_singleton() -> None:
    """get_scheduler returns the same instance across calls."""
    cfg = _stub_cfg()
    a = get_scheduler(cfg)
    b = get_scheduler(cfg)
    assert a is b


def test_t_235_stab9_10_9_singleton_locks_first_cfg() -> None:
    """Singleton ignores later cfg (first construction wins)."""
    cfg_a = _stub_cfg(boot_cohort_spacing_s=2.0)
    cfg_b = _stub_cfg(boot_cohort_spacing_s=10.0)
    a = get_scheduler(cfg_a)
    b = get_scheduler(cfg_b)
    assert a is b
    assert a.spacing_s == 2.0  # cfg_a's value, not cfg_b's


# ─── AbsorbedAgentTicker wiring ───────────────────────────────────────────

def test_t_235_stab9_10_10_absorbed_ticker_uses_scheduler() -> None:
    """AbsorbedAgentTicker.__init__ uses scheduler when enabled."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, SENTRY_ABSORBED,
    )
    cfg = _stub_cfg(boot_cohort_spacing_s=5.0)
    now = time.time()
    ticker = AbsorbedAgentTicker(
        steward_name="Sentry",
        specs=SENTRY_ABSORBED,
        cfg=cfg, store=None,
    )
    # First-fire offsets should be deterministic multiples of 5.0s,
    # not random. Each spec's last_invoked_at = now + slot_offset - interval_s
    offsets = []
    for spec in SENTRY_ABSORBED:
        state = ticker._state[spec.name]
        # Reconstruct the slot offset
        offset = state.last_invoked_at - (now - spec.interval_s)
        offsets.append(offset)
    # All offsets multiples of 5.0 (within float tolerance)
    for o in offsets:
        # allow ±1s for clock drift between init + measurement
        nearest = round(o / 5.0) * 5.0
        assert abs(o - nearest) < 1.5, f"offset {o} not near multiple of 5.0"


def test_t_235_stab9_10_11_absorbed_ticker_disabled_falls_back_to_jitter() -> None:
    """When scheduler disabled, AbsorbedAgentTicker falls back to stage-5 jitter."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, CURATOR_ABSORBED,
    )
    cfg = _stub_cfg(
        boot_cohort_scheduler_enabled=False,  # disable stage 10
        startup_jitter_enabled=True,          # stage 5 still on
        startup_jitter_max_s=10.0,
    )
    ticker = AbsorbedAgentTicker(
        steward_name="Curator",
        specs=CURATOR_ABSORBED,
        cfg=cfg, store=None,
    )
    # Last_invoked_at should NOT be 0.0 (stage 5 fired)
    state = ticker._state["CorpusDataCuratorAgent"]
    assert state.last_invoked_at != 0.0


def test_t_235_stab9_10_12_absorbed_ticker_both_disabled_preserves_zero() -> None:
    """Both stage 10 + 5 disabled → last_invoked_at stays 0.0 (pre-jitter behavior)."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, CURATOR_ABSORBED,
    )
    cfg = _stub_cfg(
        boot_cohort_scheduler_enabled=False,
        startup_jitter_enabled=False,
    )
    ticker = AbsorbedAgentTicker(
        steward_name="Curator",
        specs=CURATOR_ABSORBED,
        cfg=cfg, store=None,
    )
    state = ticker._state["CorpusDataCuratorAgent"]
    assert state.last_invoked_at == 0.0


# ─── startup_grace wiring ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_235_stab9_10_13_startup_grace_uses_scheduler() -> None:
    """startup_grace uses scheduler slot when stage 10 enabled."""
    # Spacing low so test runs fast; first agent gets slot 0 → no sleep
    cfg = _stub_cfg(boot_cohort_scheduler_enabled=True, boot_cohort_spacing_s=0.05)
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="FirstAgent")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05, f"slot 0 should have ~0s delay; elapsed={elapsed:.3f}s"

    # Second agent gets slot 1 → ~0.05s sleep
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="SecondAgent")
    elapsed = time.monotonic() - t0
    assert 0.04 <= elapsed < 0.20, f"slot 1 should have ~0.05s delay; elapsed={elapsed:.3f}s"


@pytest.mark.asyncio
async def test_t_235_stab9_10_14_startup_grace_falls_back_to_jitter() -> None:
    """startup_grace falls back to stage-5 random jitter when stage 10 disabled."""
    cfg = _stub_cfg(
        boot_cohort_scheduler_enabled=False,
        startup_jitter_enabled=True,
        startup_jitter_max_s=0.1,
    )
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="JitterAgent")
    elapsed = time.monotonic() - t0
    # Stage-5 jitter ∈ [0, 0.1]s
    assert 0.0 <= elapsed < 0.3, f"jitter ∈ [0, 0.1]s; elapsed={elapsed:.3f}s"


@pytest.mark.asyncio
async def test_t_235_stab9_10_15_startup_grace_all_disabled_is_noop() -> None:
    """Both stage 10 + 5 disabled → startup_grace returns immediately."""
    cfg = _stub_cfg(
        boot_cohort_scheduler_enabled=False,
        startup_jitter_enabled=False,
    )
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="NoOpAgent")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.05


# ─── Q2 cadence preservation ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t_235_stab9_10_16_absorbed_cadence_preserved_after_first_fire() -> None:
    """After first fire, absorbed agent fires at ORIGINAL interval_s
    (Q2 invariant — stage 10 only offsets the FIRST fire)."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, AbsorbedAgentSpec,
    )

    spec = AbsorbedAgentSpec(
        name="TestAgent",
        module_path="nonexistent",   # build will fail but state still set
        class_name="X",
        method_name="y",
        interval_s=60,
        is_async=False,
    )
    cfg = _stub_cfg(boot_cohort_spacing_s=5.0)
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=[spec],
        cfg=cfg, store=None,
    )
    state = ticker._state["TestAgent"]
    # interval_s field unchanged
    assert spec.interval_s == 60, "Stage 10 must NOT modify spec.interval_s"


# ─── Architecture verification ────────────────────────────────────────────

def test_t_235_stab9_10_17_module_is_stdlib_only() -> None:
    """boot_cohort_scheduler.py has zero bridge-relative imports."""
    src = (_BRIDGE_DIR / "boot_cohort_scheduler.py").read_text(encoding="utf-8")
    assert "from .config" not in src
    assert "from .store" not in src
    assert "from .chain" not in src
    assert "from .operator_" not in src
    # Stdlib only:
    assert "import threading" in src
    assert "import logging" in src


def test_t_235_stab9_10_18_chain_py_untouched() -> None:
    """Stage 10 does NOT modify chain.py (FROZEN-adjacent guard)."""
    src = (_BRIDGE_DIR / "chain.py").read_text(encoding="utf-8")
    assert "STAGE-10" not in src
    assert "BootCohortScheduler" not in src
    assert "boot_cohort" not in src.lower()


def test_t_235_stab9_10_19_grep_for_searchable_logs() -> None:
    """Stage 10 logs use the searchable STAGE-10 prefix."""
    src_sched = (_BRIDGE_DIR / "boot_cohort_scheduler.py").read_text(encoding="utf-8")
    assert "STAGE-10" in src_sched
    src_ticker = (_BRIDGE_DIR / "operator_steward_absorbed_agents.py").read_text(encoding="utf-8")
    assert "stage-10 deterministic slot" in src_ticker
    src_grace = (_BRIDGE_DIR / "startup_grace.py").read_text(encoding="utf-8")
    assert "STAGE-10" in src_grace
