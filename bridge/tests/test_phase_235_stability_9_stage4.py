"""Phase 235.x-STABILITY-9 stages 4c/4d/4e (2026-05-17) — Absorbed-agent
ticker tests.

Validates the generic AbsorbedAgentTicker + per-steward absorbed agent
rosters used by Sentry/Guardian/Curator polling loops to replace 9
standalone background asyncio tasks.
"""
import asyncio
import os
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from bridge.vapi_bridge.operator_steward_absorbed_agents import (
    AbsorbedAgentSpec,
    AbsorbedAgentTicker,
    SENTRY_ABSORBED,
    GUARDIAN_ABSORBED,
    CURATOR_ABSORBED,
)


_MAIN_PY = Path(__file__).resolve().parents[1] / "vapi_bridge" / "main.py"


def _stub_cfg(**overrides):
    """Minimal cfg stub for ticker init."""
    base = {
        "stewards_absorb_enabled": True,
        "phg_registry_address": "",
        "ceremony_registry_address": "",
        "vhp_renewal_enabled": True,
        "ruling_provenance_enabled": True,
        "ruling_provenance_publish_enabled": False,
        "ruling_enforcement_enabled": False,
        "supervisor_enabled": True,
        "agent_calibration_monitor_enabled": True,
        "protocol_intelligence_enabled": True,
        "data_provenance_dag_enabled": False,  # disable curator's first task
        "validation_gate_n": 100,
        "validation_divergence_threshold": 0.3,
        "validation_max_divergence_rate": 1.0,
        "grind_session_id": "",
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_t_235_stab9_4_1_sentry_roster_4_agents() -> None:
    """Sentry absorbs exactly 4 agents per agent_rationalization_v1.md §3.3."""
    assert len(SENTRY_ABSORBED) == 4
    names = [s.name for s in SENTRY_ABSORBED]
    assert "VHPRenewalAgent" in names
    assert "CeremonyWatchdogAgent" in names
    assert "ChainReconciler" in names
    assert "RulingProvenanceAnchorAgent" in names


def test_t_235_stab9_4_2_guardian_roster_4_agents() -> None:
    """Guardian absorbs 4 agents (PMSA + MEGA dropped per V-check —
    they were never spawned in main.py despite cfg flags True)."""
    assert len(GUARDIAN_ABSORBED) == 4
    names = [s.name for s in GUARDIAN_ABSORBED]
    assert "ProtocolIntelligenceAgent" in names
    assert "AgentSupervisor" in names
    assert "AgentCalibrationMonitor" in names
    assert "RulingEnforcementAgent" in names
    # V-check exclusions
    assert "ProtocolMaturityScoringAgent" not in names
    assert "MaturityElevationGateAgent" not in names


def test_t_235_stab9_4_3_curator_roster_1_agent() -> None:
    """Curator absorbs CorpusDataCuratorAgent (7-task data coherence)."""
    assert len(CURATOR_ABSORBED) == 1
    assert CURATOR_ABSORBED[0].name == "CorpusDataCuratorAgent"


def test_t_235_stab9_4_4_total_absorbed_count_9() -> None:
    """4 (Sentry) + 4 (Guardian) + 1 (Curator) = 9 absorbed agents."""
    total = len(SENTRY_ABSORBED) + len(GUARDIAN_ABSORBED) + len(CURATOR_ABSORBED)
    assert total == 9


def test_t_235_stab9_4_5_spec_intervals_match_originals() -> None:
    """Per Q2: absorbed agents retain their ORIGINAL cadences."""
    intervals = {s.name: s.interval_s for s in SENTRY_ABSORBED + GUARDIAN_ABSORBED + CURATOR_ABSORBED}
    # Verify a few load-bearing intervals
    assert intervals["ChainReconciler"] == 30
    assert intervals["RulingProvenanceAnchorAgent"] == 60
    assert intervals["CeremonyWatchdogAgent"] == 300
    assert intervals["VHPRenewalAgent"] == 21600
    assert intervals["ProtocolIntelligenceAgent"] == 60
    assert intervals["AgentSupervisor"] == 900
    assert intervals["AgentCalibrationMonitor"] == 900
    assert intervals["RulingEnforcementAgent"] == 300
    assert intervals["CorpusDataCuratorAgent"] == 1800


def test_t_235_stab9_4_6_cfg_flag_default_on() -> None:
    """STEWARDS_ABSORB_ENABLED defaults True (stages 4c/4d/4e active)."""
    os.environ.pop("STEWARDS_ABSORB_ENABLED", None)
    from bridge.vapi_bridge.config import Config
    cfg = Config()
    assert cfg.stewards_absorb_enabled is True


def test_t_235_stab9_4_7_cfg_flag_env_disable() -> None:
    """STEWARDS_ABSORB_ENABLED=false reverts to pre-stage-4 spawn behavior."""
    os.environ["STEWARDS_ABSORB_ENABLED"] = "false"
    try:
        from bridge.vapi_bridge.config import Config
        cfg = Config()
        assert cfg.stewards_absorb_enabled is False
    finally:
        os.environ.pop("STEWARDS_ABSORB_ENABLED", None)


def test_t_235_stab9_4_8_main_py_spawn_blocks_gated() -> None:
    """The 9 standalone spawn blocks for absorbed agents are gated by
    stewards_absorb_enabled=False — verify the gate pattern appears at
    the expected sites in main.py."""
    src = _MAIN_PY.read_text(encoding="utf-8")
    # Count occurrences of the gate pattern in the absorbed blocks.
    gate_pattern = 'not getattr(self.cfg, "stewards_absorb_enabled", True)'
    occurrences = src.count(gate_pattern)
    # 9 absorbed agents — but ProtocolMaturityScoringAgent + MaturityElevationGateAgent
    # weren't spawned, so only 9 spawn blocks needed gating
    assert occurrences == 9, (
        f"Expected exactly 9 stewards_absorb gate patterns in main.py, "
        f"got {occurrences}. Stages 4c/4d/4e roll-up: ChainReconciler + "
        f"CeremonyWatchdog + RulingProvenanceAnchor + VHPRenewal (Sentry x4) + "
        f"RulingEnforcement + AgentSupervisor + AgentCalibrationMonitor + "
        f"ProtocolIntelligence (Guardian x4) + CorpusDataCurator (Curator x1)"
    )


def test_t_235_stab9_4_9_steward_pollings_accept_chain_bus_kwargs() -> None:
    """The 3 steward polling-loop entrypoints accept chain + bus kwargs
    for absorbed-ticker construction."""
    from bridge.vapi_bridge import operator_agent_sentry_polling as s
    from bridge.vapi_bridge import operator_agent_guardian_polling as g
    from bridge.vapi_bridge import operator_agent_curator_polling as c
    import inspect
    for module, name in [
        (s, "run_sentry_polling_loop"),
        (g, "run_guardian_polling_loop"),
        (c, "run_curator_polling_loop"),
    ]:
        fn = getattr(module, name)
        sig = inspect.signature(fn)
        params = sig.parameters
        assert "chain" in params, f"{name} missing chain kwarg"
        assert "bus" in params, f"{name} missing bus kwarg"


@pytest.mark.asyncio
async def test_t_235_stab9_4_10_ticker_tick_all_fail_open(tmp_path) -> None:
    """AbsorbedAgentTicker.tick_all() never raises out even when
    every spec fails to instantiate."""
    cfg = _stub_cfg()
    # Bad module paths in specs → all instantiations fail
    bad_specs = [
        AbsorbedAgentSpec(
            name="DoesNotExist",
            module_path="bridge.vapi_bridge.nonexistent_module",
            class_name="NotAClass",
            method_name="not_a_method",
            interval_s=60,
        )
    ]
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=bad_specs,
        cfg=cfg, store=None,
    )
    # Should not raise + return dict with the spec name
    result = await ticker.tick_all()
    assert isinstance(result, dict)
    assert "DoesNotExist" in result


@pytest.mark.asyncio
async def test_t_235_stab9_4_11_ticker_respects_intervals(tmp_path) -> None:
    """Specs with interval_s > 0 only fire when elapsed exceeds the
    interval. First call (last_invoked_at=0) always fires."""

    invocations = {"n": 0}

    class FakeAgent:
        def __init__(self, *, cfg, store):
            pass

        def my_method(self):
            invocations["n"] += 1

    import sys
    sys.modules["fake_agent_for_test"] = type(sys)("fake_agent_for_test")
    sys.modules["fake_agent_for_test"].FakeAgent = FakeAgent

    spec = AbsorbedAgentSpec(
        name="FakeAgent",
        module_path="fake_agent_for_test",
        class_name="FakeAgent",
        method_name="my_method",
        interval_s=3600,
        is_async=False,
    )
    cfg = _stub_cfg()
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=[spec],
        cfg=cfg, store=None,
    )
    # First tick: invocation #1 (last_invoked_at=0 → always fires)
    await ticker.tick_all()
    assert invocations["n"] == 1
    # Second tick immediately after: elapsed < 3600 → no fire
    await ticker.tick_all()
    assert invocations["n"] == 1


def test_t_235_stab9_4_12_get_state_summary_shape() -> None:
    """get_state_summary returns per-agent dict with expected keys."""
    cfg = _stub_cfg()
    ticker = AbsorbedAgentTicker(
        steward_name="TestSteward",
        specs=[SENTRY_ABSORBED[0]],   # use a real spec for clean keys
        cfg=cfg, store=None,
    )
    summary = ticker.get_state_summary()
    assert SENTRY_ABSORBED[0].name in summary
    s = summary[SENTRY_ABSORBED[0].name]
    assert "invocations" in s
    assert "failures" in s
    assert "last_invoked_at" in s
    assert "last_error" in s
    assert "instantiated" in s
