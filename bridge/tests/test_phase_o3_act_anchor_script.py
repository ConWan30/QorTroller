"""Phase O3-ACT-WATCHER -- parallel_o3_act_anchor.py gate-logic tests.

Covers the script's authorization surface (the most safety-critical part).
The full _run() coroutine requires bridge boot + chain RPC + store DB; those
are exercised by the live anchor when 504h gates close. These tests pin the
pure-function gate-logic so a future contributor can't accidentally weaken
the quadruple-gate authorization without a CI-visible failure.

  T-PARALLEL-O3-1: _check_gates() PASS when both env vars set correctly
  T-PARALLEL-O3-2: _check_gates() FAIL on missing CHAIN_SUBMISSION_PAUSED=false
  T-PARALLEL-O3-3: _check_gates() FAIL on missing OPERATOR_INITIATIVE_O3_AUTHORIZED
                    (verifies distinct env var name from O2 -- residual O2
                     authorization MUST NOT carry over)
  T-PARALLEL-O3-4: _check_watcher_veto() FAILS when ANY agent has o3_ready=False
  T-PARALLEL-O3-5: _check_watcher_veto() PASSES when all three o3_ready=True
  T-PARALLEL-O3-6: AGENT_BUNDLE_FILES references *_o3_acting_v1.json filenames
                    (locks against future filename drift; pairs with
                     test_phase_o3_act_draft_bundles.py Merkle pin)
"""

from __future__ import annotations

import importlib.util
import os
import sys
import types
from pathlib import Path

import pytest


# --------------------------------------------------------------------------
# Load scripts/parallel_o3_act_anchor.py as a module without going through
# the bridge package (the script is in scripts/, not bridge/).
# --------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
SCRIPT_PATH = SCRIPTS_DIR / "parallel_o3_act_anchor.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location(
        "parallel_o3_act_anchor", str(SCRIPT_PATH)
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------


def test_T_PARALLEL_O3_1_gates_pass_when_both_envs_set(monkeypatch):
    """Quadruple-gate gates 1+2 (env-level) PASS when both vars set."""
    mod = _load_script_module()
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.setenv("OPERATOR_INITIATIVE_O3_AUTHORIZED", "true")
    ok, reason = mod._check_gates()
    assert ok is True, f"expected gates pass; got reason={reason!r}"
    assert "gates 1+2 aligned" in reason.lower()


def test_T_PARALLEL_O3_2_fails_when_kill_switch_not_lifted(monkeypatch):
    """Gate 1 FAILS unless CHAIN_SUBMISSION_PAUSED=false explicitly."""
    mod = _load_script_module()
    # Default (no env) -> kill-switch active -> Gate 1 fails
    monkeypatch.delenv("CHAIN_SUBMISSION_PAUSED", raising=False)
    monkeypatch.setenv("OPERATOR_INITIATIVE_O3_AUTHORIZED", "true")
    ok, reason = mod._check_gates()
    assert ok is False
    assert "Gate 1 FAILED" in reason
    assert "CHAIN_SUBMISSION_PAUSED" in reason

    # Explicit "true" also fails (only "false" lifts the gate)
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "true")
    ok2, reason2 = mod._check_gates()
    assert ok2 is False
    assert "Gate 1 FAILED" in reason2


def test_T_PARALLEL_O3_3_fails_when_o2_authorization_does_not_carry_over(monkeypatch):
    """Gate 2 uses DISTINCT env var name OPERATOR_INITIATIVE_O3_AUTHORIZED.
    Residual O2 authorization (OPERATOR_INITIATIVE_O2_AUTHORIZED=true) MUST
    NOT carry over into the O3 anchor script."""
    mod = _load_script_module()
    monkeypatch.setenv("CHAIN_SUBMISSION_PAUSED", "false")
    monkeypatch.delenv("OPERATOR_INITIATIVE_O3_AUTHORIZED", raising=False)
    # Set O2 authorization (the OLD env var) -- this must NOT satisfy gate 2
    monkeypatch.setenv("OPERATOR_INITIATIVE_O2_AUTHORIZED", "true")
    ok, reason = mod._check_gates()
    assert ok is False, (
        "O3 script must not accept O2 authorization env var; got pass=True. "
        "Distinct env var name is the defensive layer that prevents residual "
        "authorization carrying over between phases."
    )
    assert "Gate 2 FAILED" in reason
    assert "OPERATOR_INITIATIVE_O3_AUTHORIZED" in reason


def test_T_PARALLEL_O3_4_watcher_veto_fails_on_any_o3_not_ready(monkeypatch):
    """Gate 4 FAILS when ANY of the three agents has o3_ready=False."""
    mod = _load_script_module()

    # Stand up a fake summary with 2/3 ready but Curator NOT ready
    AgentReadiness = types.SimpleNamespace
    summary = types.SimpleNamespace(
        per_agent=(
            AgentReadiness(
                agent_id="anchor_sentry",
                current_phase="O2_SUGGEST",
                o3_ready=True,
                o3_blockers=tuple(),
            ),
            AgentReadiness(
                agent_id="guardian",
                current_phase="O2_SUGGEST",
                o3_ready=True,
                o3_blockers=tuple(),
            ),
            AgentReadiness(
                agent_id="curator",
                current_phase="O2_SUGGEST",
                o3_ready=False,
                o3_blockers=("marketplace_setCurator_role_not_assigned",),
            ),
        )
    )
    ok, reason, blockers_per_agent = mod._check_watcher_veto(summary)
    assert ok is False
    assert "Gate 4 FAILED" in reason
    # Curator's blocker surfaces in per-agent breakdown
    curator_row = next(b for b in blockers_per_agent if b["agent_id"] == "curator")
    assert curator_row["o3_ready"] is False
    assert "marketplace_setCurator_role_not_assigned" in curator_row["o3_blockers"]


def test_T_PARALLEL_O3_5_watcher_veto_passes_when_all_o3_ready(monkeypatch):
    """Gate 4 PASSES when all three agents have o3_ready=True."""
    mod = _load_script_module()
    AgentReadiness = types.SimpleNamespace
    summary = types.SimpleNamespace(
        per_agent=(
            AgentReadiness(agent_id=a, current_phase="O2_SUGGEST",
                           o3_ready=True, o3_blockers=tuple())
            for a in ("anchor_sentry", "guardian", "curator")
        )
    )
    ok, reason, _ = mod._check_watcher_veto(summary)
    assert ok is True
    assert "Gate 4 PASS" in reason
    assert "all 3 agents o3_ready=True" in reason


def test_T_PARALLEL_O3_6_bundle_files_locked_to_o3_acting_filenames():
    """AGENT_BUNDLE_FILES MUST reference the *_o3_acting_v1.json bundles
    locked at Phase O3-ACT-DRAFT (commit 3cb59f46 2026-05-10). Future
    filename changes require an explicit code edit + Merkle re-pin in
    test_phase_o3_act_draft_bundles.py::test_t_o3_act_draft_4_*."""
    mod = _load_script_module()

    expected = {
        "anchor_sentry": "anchor_sentry_o3_acting_v1.json",
        "guardian":      "guardian_o3_acting_v1.json",
        "curator":       "curator_o3_acting_v1.json",
    }
    assert mod.AGENT_BUNDLE_FILES == expected, (
        f"AGENT_BUNDLE_FILES drift: {mod.AGENT_BUNDLE_FILES} != {expected}.  "
        "If this is intentional, update both the script AND the Merkle-pin "
        "test in test_phase_o3_act_draft_bundles.py."
    )

    # Anchor order is fixed for atomicity invariant
    assert mod.AGENT_ANCHOR_ORDER == ("anchor_sentry", "guardian", "curator")

    # Cost guards present and conservative
    assert hasattr(mod, "COST_BUDGET_IOTX")
    assert hasattr(mod, "SAFETY_FLOOR_IOTX")
    assert mod.SAFETY_FLOOR_IOTX > 0
    assert mod.COST_BUDGET_IOTX > mod.SAFETY_FLOOR_IOTX
