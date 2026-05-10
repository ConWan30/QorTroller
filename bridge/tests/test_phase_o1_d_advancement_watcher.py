"""Phase O1 D — Operator Initiative Advancement Watcher tests.

The advancement watcher is the parallel-fleet primitive that enforces
the cross-agent phase alignment invariant (Sentry + Guardian + Curator
must advance together through the Phase O ladder).  These tests cover:

  T-O1-D-1: pure synchronous evaluator returns 3 per-agent readiness rows
  T-O1-D-2: phase resolution from bundle filename suffix
  T-O1-D-3: O2 SUGGEST blockers fire when shadow age < 3 weeks
  T-O1-D-4: fleet_phase_aligned True iff all three at SAME phase
  T-O1-D-5: agent-specific O3 gates (KMS for Sentry/Guardian, marketplace for Curator)
  T-O1-D-6: failure to evaluate ONE agent does NOT block the other two
            (INV-INITIATIVE-ADVANCEMENT-002)
  T-O1-D-7: config defaults are opt-in (matches C4 cedar_drift pattern)

These tests use stub Config + Store classes that mirror the production
bridge interfaces — kept self-contained so they don't depend on the full
bridge boot sequence.
"""

from __future__ import annotations

import time
import types
import pytest

from vapi_bridge.operator_initiative_advancement import (
    INITIATIVE_AGENTS,
    PHASE_O2_SHADOW_MIN_HOURS,
    PHASE_O2_EVAL_MIN_COUNT,
    AgentAdvancementReadiness,
    FleetAdvancementSummary,
    _evaluate_agent_readiness,
    evaluate_fleet_advancement_sync,
)


def _make_stub_store(*, activations: dict, eval_counts: dict, drift_counts: dict):
    """Build a minimal stub Store that exposes only the methods
    operator_initiative_advancement.py reads."""
    s = types.SimpleNamespace()

    def get_latest(agent_id):
        return activations.get(agent_id)

    def get_first(agent_id):
        return activations.get(agent_id)

    def count_evals(agent_id):
        return eval_counts.get(agent_id, 0)

    def count_drift(agent_id, drift_type, since_seconds):
        return drift_counts.get((agent_id, drift_type), 0)

    s.get_latest_operator_agent_activation = get_latest
    s.get_first_operator_agent_activation = get_first
    s.count_cedar_shadow_evaluations = count_evals
    s.count_operator_agent_drift_findings = count_drift
    return s


def _make_stub_cfg(**overrides):
    cfg = types.SimpleNamespace()
    cfg.kms_hsm_production_ready = overrides.get("kms_hsm_production_ready", False)
    cfg.marketplace_curator_role_assigned = overrides.get(
        "marketplace_curator_role_assigned", False
    )
    return cfg


def test_T_O1_D_1_evaluator_returns_three_per_agent_rows():
    """Fleet evaluator always returns exactly 3 per-agent rows (parallel
    invariant)."""
    now = time.time()
    activations = {
        agent: {
            "bundle_filename": f"{agent}_o1_shadow_v1.json",
            "anchored_at_unix": now - 100,
        }
        for agent in INITIATIVE_AGENTS
    }
    store = _make_stub_store(
        activations=activations, eval_counts={}, drift_counts={}
    )
    summary = evaluate_fleet_advancement_sync(cfg=_make_stub_cfg(), store=store)
    assert summary.fleet_size == 3
    assert len(summary.per_agent) == 3
    seen_ids = {a.agent_id for a in summary.per_agent}
    assert seen_ids == set(INITIATIVE_AGENTS)


def test_T_O1_D_2_phase_resolution_from_bundle_filename():
    """Bundle filename suffix correctly resolves to phase enum."""
    now = time.time()
    cases = [
        ("anchor_sentry_o1_shadow_v1.json", "O1_SHADOW"),
        ("guardian_o2_suggest_v1.json", "O2_SUGGEST"),
        ("curator_o3_act_v1.json", "O3_ACT"),
        ("unknown.json", "UNKNOWN"),
    ]
    for filename, expected_phase in cases:
        store = _make_stub_store(
            activations={
                "anchor_sentry": {
                    "bundle_filename": filename,
                    "anchored_at_unix": now - 100,
                }
            },
            eval_counts={},
            drift_counts={},
        )
        result = _evaluate_agent_readiness(
            "anchor_sentry", cfg=_make_stub_cfg(), store=store
        )
        assert result.current_phase == expected_phase, f"{filename} → {expected_phase}"


def test_T_O1_D_3_o2_blockers_when_shadow_too_young():
    """Shadow age <3 weeks blocks O2 SUGGEST advancement."""
    now = time.time()
    young_anchor = now - 100  # ~100 seconds ago, far under 3 weeks
    store = _make_stub_store(
        activations={
            "anchor_sentry": {
                "bundle_filename": "anchor_sentry_o1_shadow_v1.json",
                "anchored_at_unix": young_anchor,
            }
        },
        eval_counts={"anchor_sentry": 1000},  # plenty of evals; only age is short
        drift_counts={},
    )
    result = _evaluate_agent_readiness(
        "anchor_sentry", cfg=_make_stub_cfg(), store=store
    )
    assert result.o2_ready is False
    # Look for the shadow_age blocker explicitly
    has_age_blocker = any("shadow_age" in b for b in result.o2_blockers)
    assert has_age_blocker, f"expected shadow_age blocker; got {result.o2_blockers}"


def test_T_O1_D_4_fleet_phase_aligned_iff_all_same_phase():
    """fleet_phase_aligned is True iff all three agents on the SAME phase."""
    now = time.time()

    # Case 1 — all three at O1_SHADOW → aligned
    activations_aligned = {
        agent: {
            "bundle_filename": f"{agent}_o1_shadow_v1.json",
            "anchored_at_unix": now - 100,
        }
        for agent in INITIATIVE_AGENTS
    }
    store = _make_stub_store(
        activations=activations_aligned, eval_counts={}, drift_counts={}
    )
    summary = evaluate_fleet_advancement_sync(cfg=_make_stub_cfg(), store=store)
    assert summary.fleet_phase_aligned is True
    assert summary.fleet_at_o1_count == 3

    # Case 2 — Curator at O2 while Sentry/Guardian at O1 → NOT aligned
    activations_split = {
        "anchor_sentry": {
            "bundle_filename": "anchor_sentry_o1_shadow_v1.json",
            "anchored_at_unix": now - 100,
        },
        "guardian": {
            "bundle_filename": "guardian_o1_shadow_v1.json",
            "anchored_at_unix": now - 100,
        },
        "curator": {
            "bundle_filename": "curator_o2_suggest_v1.json",
            "anchored_at_unix": now - 100,
        },
    }
    store = _make_stub_store(
        activations=activations_split, eval_counts={}, drift_counts={}
    )
    summary = evaluate_fleet_advancement_sync(cfg=_make_stub_cfg(), store=store)
    assert summary.fleet_phase_aligned is False


def test_T_O1_D_5_agent_specific_o3_gates():
    """Sentry/Guardian require KMS HSM; Curator requires marketplace setCurator."""
    now = time.time()
    # Push agents into O2 SUGGEST phase so O3 gates become evaluable
    activations = {
        agent: {
            "bundle_filename": f"{agent}_o2_suggest_v1.json",
            "anchored_at_unix": now - (PHASE_O2_SHADOW_MIN_HOURS + 100) * 3600,
        }
        for agent in INITIATIVE_AGENTS
    }
    store = _make_stub_store(
        activations=activations, eval_counts={}, drift_counts={}
    )

    # Both gates OFF → all three agents have agent-specific blockers
    summary = evaluate_fleet_advancement_sync(
        cfg=_make_stub_cfg(
            kms_hsm_production_ready=False, marketplace_curator_role_assigned=False
        ),
        store=store,
    )
    by_id = {a.agent_id: a for a in summary.per_agent}
    assert any("kms_hsm" in b for b in by_id["anchor_sentry"].o3_blockers)
    assert any("kms_hsm" in b for b in by_id["guardian"].o3_blockers)
    assert any(
        "marketplace_setCurator" in b for b in by_id["curator"].o3_blockers
    )

    # Curator gate ON, KMS gate OFF — only Sentry/Guardian still have KMS blocker
    summary = evaluate_fleet_advancement_sync(
        cfg=_make_stub_cfg(
            kms_hsm_production_ready=False, marketplace_curator_role_assigned=True
        ),
        store=store,
    )
    by_id = {a.agent_id: a for a in summary.per_agent}
    assert any("kms_hsm" in b for b in by_id["anchor_sentry"].o3_blockers)
    assert not any(
        "marketplace_setCurator" in b for b in by_id["curator"].o3_blockers
    )


def test_T_O1_D_6_one_agent_evaluation_failure_does_not_block_others():
    """INV-INITIATIVE-ADVANCEMENT-002: one agent's evaluation failure
    yields a partial-result row for that agent ONLY; the other two
    still get full evaluations."""
    now = time.time()

    def failing_get_latest(agent_id):
        if agent_id == "guardian":
            raise RuntimeError("simulated DB failure for guardian")
        return {
            "bundle_filename": f"{agent_id}_o1_shadow_v1.json",
            "anchored_at_unix": now - 100,
        }

    store = types.SimpleNamespace()
    store.get_latest_operator_agent_activation = failing_get_latest
    store.get_first_operator_agent_activation = failing_get_latest
    store.count_cedar_shadow_evaluations = lambda *_: 0
    store.count_operator_agent_drift_findings = lambda *_, **__: 0

    summary = evaluate_fleet_advancement_sync(cfg=_make_stub_cfg(), store=store)
    by_id = {a.agent_id: a for a in summary.per_agent}

    # Sentry + Curator should have evaluated successfully (no error)
    assert by_id["anchor_sentry"].error is None
    assert by_id["curator"].error is None
    # Guardian alone should carry the failure marker
    assert by_id["guardian"].error is not None
    assert "RuntimeError" in (by_id["guardian"].error or "")
    assert by_id["guardian"].o2_ready is False
    assert "evaluation_failed" in by_id["guardian"].o2_blockers


def test_T_O1_D_7_config_defaults_are_opt_in():
    """Default values match Phase O1 C4 cedar_drift_sweep pattern (opt-in
    observability) — watcher does not auto-spawn on bridge boot."""
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.operator_initiative_advancement_enabled is False
    assert cfg.operator_initiative_advancement_interval_s == 3600.0
    assert cfg.kms_hsm_production_ready is False
    assert cfg.marketplace_curator_role_assigned is False
    # Curator agent_id is registered as the canonical Step I-FINAL value
    assert cfg.operator_agent_curator_id == (
        "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"
    )
