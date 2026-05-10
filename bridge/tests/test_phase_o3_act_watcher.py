"""Phase O3-ACT-WATCHER -- O3 readiness gate evaluation tests.

Builds on test_phase_o1_d_advancement_watcher.py to lock the O3-specific
behaviors shipped in Phase O3-ACT-WATCHER (2026-05-10):

  T-O3-ACT-WATCHER-1: bundle_filename `*_o3_acting_v1.json` resolves to phase=O3_ACT
                       (the critical bug fix -- pre-watcher this fell through to UNKNOWN)
  T-O3-ACT-WATCHER-2: O3 readiness flips True when ALL gates met (clean fixture)
  T-O3-ACT-WATCHER-3: draft_payload_count_min blocker fires when below 50
  T-O3-ACT-WATCHER-4: disagreement_rate blocker fires when above 5%
  T-O3-ACT-WATCHER-5: Curator-specific false_positive_rate blocker (>0%)
  T-O3-ACT-WATCHER-6: Guardian-specific github_app_oauth_tokens blocker
  T-O3-ACT-WATCHER-7: operator_dual_key_present blocker fires for all 3 agents
  T-O3-ACT-WATCHER-8: store helpers missing -> safe wrappers return 0/0.0 placeholders
                       (forward-compat invariant -- pre-O2-drafting bridge code unaffected)
"""

from __future__ import annotations

import sys
import time
import types
from pathlib import Path

import pytest

# Mirror the path setup used elsewhere in bridge/tests.
BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

from vapi_bridge.operator_initiative_advancement import (
    INITIATIVE_AGENTS,
    PHASE_O3_DRAFT_PAYLOAD_MIN,
    PHASE_O3_DISAGREEMENT_RATE_MAX,
    PHASE_O3_FALSE_POSITIVE_RATE_MAX,
    PHASE_O3_SUGGEST_MIN_HOURS,
    _evaluate_agent_readiness,
    _count_drafts_safe,
    _disagreement_rate_safe,
    _false_positive_rate_safe,
    evaluate_fleet_advancement_sync,
)


def _make_stub_store(
    *,
    activations: dict,
    eval_counts: dict | None = None,
    drift_counts: dict | None = None,
    drafts: dict | None = None,
    disagreement: dict | None = None,
    false_positive: dict | None = None,
):
    """Stub store that exposes ALL methods _evaluate_agent_readiness reads,
    including the new Phase O3-ACT-WATCHER helpers."""
    eval_counts = eval_counts or {}
    drift_counts = drift_counts or {}
    drafts = drafts or {}
    disagreement = disagreement or {}
    false_positive = false_positive or {}

    s = types.SimpleNamespace()
    s.get_latest_operator_agent_activation = lambda agent_id: activations.get(agent_id)
    s.get_first_operator_agent_activation = lambda agent_id: activations.get(agent_id)
    s.count_cedar_shadow_evaluations = lambda agent_id: eval_counts.get(agent_id, 0)
    s.count_operator_agent_drift_findings = (
        lambda agent_id, drift_type, since_seconds: drift_counts.get((agent_id, drift_type), 0)
    )
    # New Phase O3-ACT-WATCHER helpers
    s.count_operator_agent_drafts = lambda agent_id, since_seconds: drafts.get(agent_id, 0)
    s.compute_operator_agent_disagreement_rate = (
        lambda agent_id, since_seconds: disagreement.get(agent_id, 0.0)
    )
    s.compute_operator_agent_false_positive_rate = (
        lambda agent_id, since_seconds: false_positive.get(agent_id, 0.0)
    )
    return s


def _make_o3_ready_cfg(**overrides):
    """Config defaulting to ALL O3 gates open. Tests override one gate at a time
    to verify each blocker fires individually."""
    cfg = types.SimpleNamespace()
    cfg.kms_hsm_production_ready = overrides.get("kms_hsm_production_ready", True)
    cfg.marketplace_curator_role_assigned = overrides.get(
        "marketplace_curator_role_assigned", True
    )
    cfg.operator_dual_key_present = overrides.get("operator_dual_key_present", True)
    cfg.github_app_oauth_tokens_valid = overrides.get(
        "github_app_oauth_tokens_valid", True
    )
    return cfg


def _o2_anchor_clean(now: float) -> float:
    """Anchor timestamp 504h+epsilon ago -- clears O3 shadow_age gate."""
    return now - (PHASE_O3_SUGGEST_MIN_HOURS + 1) * 3600.0


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-1: bundle_filename `*_o3_acting_v1.json` resolves to O3_ACT
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_1_o3_acting_filename_resolves_to_O3_ACT():
    """The critical bug fix: pre-Phase-O3-ACT-WATCHER, the watcher only
    matched `_o3_act_` substring, so the Phase O3-ACT-DRAFT bundles
    (`*_o3_acting_v1.json`) would have resolved to phase=UNKNOWN when
    anchored. Now both substrings resolve to O3_ACT."""
    now = time.time()
    for fname in (
        "anchor_sentry_o3_acting_v1.json",
        "guardian_o3_acting_v1.json",
        "curator_o3_acting_v1.json",
    ):
        store = _make_stub_store(
            activations={
                "anchor_sentry": {
                    "bundle_filename": fname,
                    "anchored_at_unix": now - 100,
                }
            },
        )
        result = _evaluate_agent_readiness(
            "anchor_sentry", cfg=_make_o3_ready_cfg(), store=store
        )
        assert result.current_phase == "O3_ACT", (
            f"{fname} must resolve to phase=O3_ACT (Phase O3-ACT-WATCHER fix); "
            f"got {result.current_phase}"
        )


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-2: O3 readiness flips True when ALL gates met
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_2_o3_ready_when_all_gates_clean():
    """Sentry currently at O2_SUGGEST with shadow_age >504h, drafts=>=50,
    disagreement=0, dual_key + KMS HSM provisioned -> o3_ready=True."""
    now = time.time()
    activations = {
        "anchor_sentry": {
            "bundle_filename": "anchor_sentry_o2_suggest_v1.json",
            "anchored_at_unix": _o2_anchor_clean(now),
        }
    }
    store = _make_stub_store(
        activations=activations,
        drafts={"anchor_sentry": PHASE_O3_DRAFT_PAYLOAD_MIN + 5},
        disagreement={"anchor_sentry": 0.0},
    )
    result = _evaluate_agent_readiness(
        "anchor_sentry", cfg=_make_o3_ready_cfg(), store=store
    )
    assert result.current_phase == "O2_SUGGEST"
    assert result.o3_ready is True, (
        f"Expected o3_ready=True with all gates clean; got blockers={result.o3_blockers}"
    )
    assert len(result.o3_blockers) == 0


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-3: draft_payload_count_min blocker fires below 50
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_3_draft_count_blocker():
    """When drafts<50, the o3 blocker mentions draft_payload_count."""
    now = time.time()
    activations = {
        "anchor_sentry": {
            "bundle_filename": "anchor_sentry_o2_suggest_v1.json",
            "anchored_at_unix": _o2_anchor_clean(now),
        }
    }
    store = _make_stub_store(
        activations=activations,
        drafts={"anchor_sentry": 10},  # well below min=50
        disagreement={"anchor_sentry": 0.0},
    )
    result = _evaluate_agent_readiness(
        "anchor_sentry", cfg=_make_o3_ready_cfg(), store=store
    )
    assert result.o3_ready is False
    assert any("draft_payload_count" in b for b in result.o3_blockers), (
        f"expected draft_payload_count blocker; got {result.o3_blockers}"
    )


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-4: disagreement_rate blocker fires above 5%
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_4_disagreement_rate_blocker():
    """When operator-vs-agent disagreement rate >5%, o3 blocker fires."""
    now = time.time()
    activations = {
        "guardian": {
            "bundle_filename": "guardian_o2_suggest_v1.json",
            "anchored_at_unix": _o2_anchor_clean(now),
        }
    }
    store = _make_stub_store(
        activations=activations,
        drafts={"guardian": 100},
        disagreement={"guardian": 0.08},  # 8% > 5% max
    )
    result = _evaluate_agent_readiness(
        "guardian", cfg=_make_o3_ready_cfg(), store=store
    )
    assert result.o3_ready is False
    assert any("disagreement_rate" in b for b in result.o3_blockers), (
        f"expected disagreement_rate blocker; got {result.o3_blockers}"
    )


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-5: Curator-specific false_positive_rate blocker
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_5_curator_false_positive_rate_blocker():
    """Curator's _o3_gates require false_positive_rate_30d_max=0.0 (zero
    tolerance for marketplace verdicts overturned by operator review).
    Any positive rate fires the blocker."""
    now = time.time()
    activations = {
        "curator": {
            "bundle_filename": "curator_o2_suggest_v1.json",
            "anchored_at_unix": _o2_anchor_clean(now),
        }
    }
    store = _make_stub_store(
        activations=activations,
        drafts={"curator": 100},
        disagreement={"curator": 0.0},
        false_positive={"curator": 0.01},  # ANY positive rate >0.0 fires blocker
    )
    result = _evaluate_agent_readiness(
        "curator", cfg=_make_o3_ready_cfg(), store=store
    )
    assert result.o3_ready is False
    assert any("false_positive_rate" in b for b in result.o3_blockers), (
        f"expected false_positive_rate blocker; got {result.o3_blockers}"
    )

    # And the Curator-specific role gate fires if not assigned
    cfg_no_role = _make_o3_ready_cfg(marketplace_curator_role_assigned=False)
    store_clean = _make_stub_store(
        activations=activations,
        drafts={"curator": 100},
        disagreement={"curator": 0.0},
        false_positive={"curator": 0.0},
    )
    result_no_role = _evaluate_agent_readiness("curator", cfg=cfg_no_role, store=store_clean)
    assert result_no_role.o3_ready is False
    assert any(
        "marketplace_setCurator_role_not_assigned" in b for b in result_no_role.o3_blockers
    ), f"expected setCurator role blocker; got {result_no_role.o3_blockers}"


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-6: Guardian-specific github_app_oauth_tokens blocker
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_6_guardian_github_app_oauth_blocker():
    """Guardian's _o3_gates require github_app_oauth_tokens_valid in addition
    to kms_hsm_production_ready (Sentry only requires KMS HSM)."""
    now = time.time()
    activations = {
        "guardian": {
            "bundle_filename": "guardian_o2_suggest_v1.json",
            "anchored_at_unix": _o2_anchor_clean(now),
        }
    }
    store = _make_stub_store(
        activations=activations,
        drafts={"guardian": 100},
        disagreement={"guardian": 0.0},
    )

    # KMS HSM ready but GitHub App tokens invalid -> Guardian o3_ready=False
    cfg_no_tokens = _make_o3_ready_cfg(github_app_oauth_tokens_valid=False)
    result = _evaluate_agent_readiness("guardian", cfg=cfg_no_tokens, store=store)
    assert result.o3_ready is False
    assert any(
        "github_app_oauth_tokens_not_valid" in b for b in result.o3_blockers
    ), f"expected github_app_oauth_tokens blocker; got {result.o3_blockers}"

    # Sentry should NOT be gated by github_app_oauth_tokens (Guardian-specific)
    activations_s = {
        "anchor_sentry": {
            "bundle_filename": "anchor_sentry_o2_suggest_v1.json",
            "anchored_at_unix": _o2_anchor_clean(now),
        }
    }
    store_s = _make_stub_store(
        activations=activations_s,
        drafts={"anchor_sentry": 100},
        disagreement={"anchor_sentry": 0.0},
    )
    result_s = _evaluate_agent_readiness("anchor_sentry", cfg=cfg_no_tokens, store=store_s)
    # Sentry passes if KMS HSM + dual_key set -- github_app_oauth NOT a Sentry gate
    assert result_s.o3_ready is True, (
        f"Sentry should not be gated by github_app_oauth_tokens; "
        f"got blockers={result_s.o3_blockers}"
    )


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-7: operator_dual_key_present blocker fires for all 3
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_7_dual_key_blocker_all_three():
    """All three agents' _o3_gates require operator_dual_key_present.
    When cfg.operator_dual_key_present=False, ALL three flag the blocker."""
    now = time.time()
    cfg_no_dk = _make_o3_ready_cfg(operator_dual_key_present=False)
    for agent in INITIATIVE_AGENTS:
        bundle_prefix = "anchor_sentry" if agent == "anchor_sentry" else agent
        store = _make_stub_store(
            activations={
                agent: {
                    "bundle_filename": f"{bundle_prefix}_o2_suggest_v1.json",
                    "anchored_at_unix": _o2_anchor_clean(now),
                }
            },
            drafts={agent: 100},
            disagreement={agent: 0.0},
            false_positive={agent: 0.0},
        )
        result = _evaluate_agent_readiness(agent, cfg=cfg_no_dk, store=store)
        assert result.o3_ready is False, f"{agent} should fail dual-key gate"
        assert any(
            "operator_dual_key_not_present" in b for b in result.o3_blockers
        ), f"{agent} expected dual_key blocker; got {result.o3_blockers}"


# ---------------------------------------------------------------------------
# T-O3-ACT-WATCHER-8: missing store helpers => safe-wrapper placeholders
# ---------------------------------------------------------------------------

def test_T_O3_ACT_WATCHER_8_safe_wrappers_return_zero_when_helpers_missing():
    """Forward-compat invariant: pre-Phase-O3-ACT-WATCHER bridge stores
    don't have the new helpers. Safe wrappers must return 0/0.0
    placeholders (NOT raise) so legacy bridges keep functioning."""
    bare_store = types.SimpleNamespace()
    # No helpers attached -- getattr returns None
    assert _count_drafts_safe(bare_store, "any") == 0
    assert _disagreement_rate_safe(bare_store, "any") == 0.0
    assert _false_positive_rate_safe(bare_store, "any") == 0.0

    # Helpers that raise should be swallowed too (defense-in-depth)
    erroring = types.SimpleNamespace()
    def _boom(*a, **kw):
        raise RuntimeError("simulated store outage")
    erroring.count_operator_agent_drafts = _boom
    erroring.compute_operator_agent_disagreement_rate = _boom
    erroring.compute_operator_agent_false_positive_rate = _boom
    assert _count_drafts_safe(erroring, "any") == 0
    assert _disagreement_rate_safe(erroring, "any") == 0.0
    assert _false_positive_rate_safe(erroring, "any") == 0.0
