"""Phase 235.x-STABILITY-9 stage 5 (2026-05-17) — Startup-jitter tests.

Validates the startup_grace primitive + AbsorbedAgentTicker first-tick
jitter + per-agent injections. Stage 5 eliminates the boot STARVATION
wave by spreading thundering-herd contributors across a configurable
window.
"""
import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge import startup_grace as sg


_AGENTS_DIR = Path(__file__).resolve().parents[1] / "vapi_bridge"


def _stub_cfg(**overrides):
    base = {
        "startup_jitter_enabled": True,
        "startup_jitter_max_s": 1.0,    # tight bound for fast tests
        "startup_jitter_seed": "",
        # Stage 10 2026-05-17: scheduler disabled in stage-5 tests to
        # preserve their original semantics (tests stage-5 jitter in isolation).
        "boot_cohort_scheduler_enabled": False,
        "boot_cohort_spacing_s": 5.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


@pytest.fixture(autouse=True)
def _reset_rng():
    """Reset module-level RNG state between tests."""
    sg.reset_for_test()
    yield
    sg.reset_for_test()


def test_t_235_stab9_5_1_cfg_defaults() -> None:
    """cfg.startup_jitter_enabled=True, max_s=30.0 by default."""
    os.environ.pop("STARTUP_JITTER_ENABLED", None)
    os.environ.pop("STARTUP_JITTER_MAX_S", None)
    os.environ.pop("STARTUP_JITTER_SEED", None)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.startup_jitter_enabled is True
    assert cfg.startup_jitter_max_s == 30.0
    assert cfg.startup_jitter_seed == ""


def test_t_235_stab9_5_2_env_override_disable() -> None:
    """STARTUP_JITTER_ENABLED=false flips the flag."""
    os.environ["STARTUP_JITTER_ENABLED"] = "false"
    try:
        from bridge.vapi_bridge.config import Config
        cfg = Config()
        assert cfg.startup_jitter_enabled is False
    finally:
        os.environ.pop("STARTUP_JITTER_ENABLED", None)


@pytest.mark.asyncio
async def test_t_235_stab9_5_3_disabled_is_noop() -> None:
    """When disabled, startup_grace returns immediately without sleeping."""
    cfg = _stub_cfg(startup_jitter_enabled=False, startup_jitter_max_s=10.0)
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="TestAgent")
    elapsed = time.monotonic() - t0
    assert elapsed < 0.1, f"Expected near-zero, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_t_235_stab9_5_4_enabled_sleeps_in_range() -> None:
    """When enabled with max=1.0, sleep is in [0, 1.0]s."""
    cfg = _stub_cfg(startup_jitter_max_s=1.0)
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="TestAgent")
    elapsed = time.monotonic() - t0
    # Allow small scheduling overhead (~50ms) beyond the max
    assert 0.0 <= elapsed <= 1.2, f"Expected 0..1.2s, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_t_235_stab9_5_5_zero_max_is_noop() -> None:
    """max_jitter_s=0 short-circuits — useful for per-agent disable."""
    cfg = _stub_cfg(startup_jitter_max_s=10.0)
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="TestAgent", max_jitter_s=0.0)
    elapsed = time.monotonic() - t0
    assert elapsed < 0.1


@pytest.mark.asyncio
async def test_t_235_stab9_5_6_per_agent_override() -> None:
    """max_jitter_s kwarg overrides cfg value."""
    cfg = _stub_cfg(startup_jitter_max_s=30.0)
    t0 = time.monotonic()
    await sg.startup_grace(cfg, agent_name="TestAgent", max_jitter_s=0.5)
    elapsed = time.monotonic() - t0
    assert elapsed <= 0.7, f"Override max=0.5 should bound elapsed, got {elapsed:.3f}s"


@pytest.mark.asyncio
async def test_t_235_stab9_5_7_seeded_reproducible() -> None:
    """cfg.startup_jitter_seed produces reproducible jitter values."""
    cfg = _stub_cfg(startup_jitter_seed="test-seed-abc", startup_jitter_max_s=10.0)
    # Reset RNG, sample twice — second sample should differ (different position
    # in the sequence), but the FIRST sample should be identical to a fresh-seed
    # run.
    sg.reset_for_test()
    rng_a = sg._get_rng(cfg)
    val_a = rng_a.uniform(0.0, 10.0)
    sg.reset_for_test()
    rng_b = sg._get_rng(cfg)
    val_b = rng_b.uniform(0.0, 10.0)
    assert val_a == val_b, "Seeded RNG must produce identical first sample"


@pytest.mark.asyncio
async def test_t_235_stab9_5_8_unseeded_nondeterministic() -> None:
    """Without seed, two fresh RNG inits produce different first samples."""
    sg.reset_for_test()
    cfg = _stub_cfg(startup_jitter_seed="")
    rng_a = sg._get_rng(cfg)
    val_a = rng_a.uniform(0.0, 100000.0)  # wide range to make collision unlikely
    sg.reset_for_test()
    rng_b = sg._get_rng(cfg)
    val_b = rng_b.uniform(0.0, 100000.0)
    # Probability of identical = essentially 0; if equal, RNG isn't really fresh
    assert val_a != val_b, "Unseeded RNG should produce different samples per init"


def test_t_235_stab9_5_9_absorbed_ticker_jitters_first_tick() -> None:
    """AbsorbedAgentTicker's __init__ applies jitter to each spec's
    last_invoked_at so first-tick fires within the jitter window
    (not immediately on tick #1 for all specs)."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, SENTRY_ABSORBED,
    )
    cfg = _stub_cfg(startup_jitter_max_s=10.0)
    sg.reset_for_test()
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=SENTRY_ABSORBED,
        cfg=cfg, store=None,
    )
    # Per-spec last_invoked_at must be != 0.0 (jittered, not default)
    now = time.time()
    for spec in SENTRY_ABSORBED:
        state = ticker._state[spec.name]
        # last_invoked_at = now + jitter_offset - interval_s
        # → state.last_invoked_at ∈ [now - interval_s, now - interval_s + jitter_max]
        expected_min = now - spec.interval_s - 1.0  # allow 1s clock skew
        expected_max = now - spec.interval_s + 10.0 + 1.0
        assert expected_min <= state.last_invoked_at <= expected_max, (
            f"{spec.name}: last_invoked_at={state.last_invoked_at} "
            f"outside expected [{expected_min}, {expected_max}]"
        )


def test_t_235_stab9_5_10_jitter_disabled_no_offset() -> None:
    """When startup_jitter_enabled=False, AbsorbedAgentTicker keeps
    last_invoked_at at default 0.0 — pre-stage-5 behavior preserved."""
    from bridge.vapi_bridge.operator_steward_absorbed_agents import (
        AbsorbedAgentTicker, CURATOR_ABSORBED,
    )
    cfg = _stub_cfg(startup_jitter_enabled=False)
    sg.reset_for_test()
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=CURATOR_ABSORBED,
        cfg=cfg, store=None,
    )
    for spec in CURATOR_ABSORBED:
        state = ticker._state[spec.name]
        assert state.last_invoked_at == 0.0, (
            f"{spec.name}: jitter disabled but last_invoked_at != 0.0 "
            f"(got {state.last_invoked_at}) — pre-stage-5 thundering-herd "
            f"behavior not preserved"
        )


def test_t_235_stab9_5_11_eight_agents_have_jitter_call() -> None:
    """The 8 standalone agents each have an `await startup_grace(...)`
    call near the top of their run method (per stage-5 plan)."""
    agents = [
        ("session_adjudicator.py", "SessionAdjudicator"),
        ("session_adjudicator_validator.py", "SessionAdjudicatorValidationAgent"),
        ("separation_ratio_monitor_agent.py", "SeparationRatioMonitorAgent"),
        ("controller_hardware_intelligence_agent.py", "ControllerHardwareIntelligenceAgent"),
        ("enrollment_auto_guidance_agent.py", "EnrollmentAutoGuidanceAgent"),
        ("fleet_consensus_snapshot_agent.py", "FleetConsensusSnapshotAgent"),
        ("biometric_privacy_compliance_agent.py", "BiometricPrivacyComplianceAgent"),
        ("separation_ratio_recovery_agent.py", "SeparationRatioRecoveryAgent"),
        ("fleet_signal_coherence_agent.py", "FleetSignalCoherenceAgent"),
        ("session_boundary_detector_agent.py", "SessionBoundaryDetectorAgent"),
    ]
    for file_name, agent_name in agents:
        src = (_AGENTS_DIR / file_name).read_text(encoding="utf-8")
        assert "from .startup_grace import startup_grace" in src, (
            f"{file_name} missing startup_grace import"
        )
        assert f'agent_name="{agent_name}"' in src, (
            f"{file_name} missing startup_grace call with agent_name={agent_name!r}"
        )


def test_t_235_stab9_5_12_corpus_curator_sleep30_preserved() -> None:
    """T-235-EL-3 compatibility: literal `asyncio.sleep(30)` in
    corpus_curator_agent.py is NOT touched by stage 5."""
    src = (_AGENTS_DIR / "corpus_curator_agent.py").read_text(encoding="utf-8")
    assert "asyncio.sleep(30)" in src, (
        "T-235-EL-3 will fail — stage 5 must not remove the literal "
        "`asyncio.sleep(30)` from corpus_curator_agent.py"
    )
