"""Tests for F2 recency-bound presence verifier (packaging-only fusion of PoCP + PoSR + GIC)."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vapi_bridge.recency_bound_presence import (  # noqa: E402
    PoCPLeg, PoSRLeg, GICLeg, PresenceVerdict, SCHEMA_VERSION, VPM_VISUAL_STATES,
    verify_pocp_leg, verify_posr_leg, verify_gic_leg,
    verify_recency_bound_presence, verify_attestation,
)
from dataclasses import asdict  # noqa: E402

_H = "ab" * 32
_H2 = "cd" * 32


def _good_pocp():
    return PoCPLeg(coupling_score=0.62, lag_ms=140.0, decoupled_energy=0.3,
                   coupled=True, negative_control=0.04, synthetic=False)


def _good_posr():
    return PoSRLeg(open_block_number=44355456, close_block_number=44355520,  # both % 64 == 0
                   open_commitment_hex=_H, close_commitment_hex=_H2)


def _good_gic():
    return GICLeg(gic_link_hex=_H, grind_session_id="grind_phase235_v1")


# ── leg-level ────────────────────────────────────────────────────────────────

def test_pocp_leg_happy():
    assert verify_pocp_leg(_good_pocp()).ok


def test_pocp_negative_control_must_collapse():
    # apparent coupling but shuffled input keeps it → relay-class → fail
    leg = PoCPLeg(coupling_score=0.62, lag_ms=140.0, decoupled_energy=0.3,
                  coupled=True, negative_control=0.60, synthetic=False)
    r = verify_pocp_leg(leg)
    assert r.ok is False and "negative control" in r.reason


def test_pocp_absent_negative_control_is_strict_fail():
    leg = PoCPLeg(coupling_score=0.62, lag_ms=140.0, decoupled_energy=0.3,
                  coupled=True, negative_control=None, synthetic=False)
    assert verify_pocp_leg(leg).ok is False


def test_pocp_synthetic_rejected():
    leg = PoCPLeg(coupling_score=0.62, lag_ms=140.0, decoupled_energy=0.3,
                  coupled=True, negative_control=0.04, synthetic=True)
    assert verify_pocp_leg(leg).ok is False


def test_pocp_lag_out_of_band():
    leg = PoCPLeg(coupling_score=0.62, lag_ms=900.0, decoupled_energy=0.3,
                  coupled=True, negative_control=0.04, synthetic=False)
    assert verify_pocp_leg(leg).ok is False


def test_posr_forward_ordering_required():
    leg = PoSRLeg(open_block_number=44355520, close_block_number=44355456,  # close <= open
                  open_commitment_hex=_H, close_commitment_hex=_H2)
    r = verify_posr_leg(leg)
    assert r.ok is False and "backdate" in r.reason


def test_posr_cadence_alignment_required():
    leg = PoSRLeg(open_block_number=44355457, close_block_number=44355520,  # open not % 64
                  open_commitment_hex=_H, close_commitment_hex=_H2)
    assert verify_posr_leg(leg).ok is False


def test_posr_identical_commitments_rejected():
    leg = PoSRLeg(open_block_number=44355456, close_block_number=44355520,
                  open_commitment_hex=_H, close_commitment_hex=_H)
    assert verify_posr_leg(leg).ok is False


def test_gic_leg_wellformed():
    assert verify_gic_leg(_good_gic()).ok
    assert verify_gic_leg(GICLeg(gic_link_hex="bad", grind_session_id="x")).ok is False
    assert verify_gic_leg(GICLeg(gic_link_hex=_H, grind_session_id="  ")).ok is False


# ── fusion verdicts ──────────────────────────────────────────────────────────

def test_full_pass_is_recency_bound_present_and_live():
    att = verify_recency_bound_presence(_good_pocp(), _good_posr(), _good_gic(), ts_ns=100)
    assert att.verdict == PresenceVerdict.RECENCY_BOUND_PRESENT.value
    assert att.visual_state == "live"
    ok, reason = verify_attestation(asdict(att))
    assert ok and "verified" in reason


def test_present_but_not_recency_bound():
    bad_posr = PoSRLeg(open_block_number=44355520, close_block_number=44355456,
                       open_commitment_hex=_H, close_commitment_hex=_H2)
    att = verify_recency_bound_presence(_good_pocp(), bad_posr, _good_gic(), ts_ns=100)
    assert att.verdict == PresenceVerdict.PRESENT_NOT_RECENCY_BOUND.value
    assert att.visual_state == "unverified"   # recency claim unbacked → never live


def test_decoupled_review():
    decoupled = PoCPLeg(coupling_score=0.05, lag_ms=140.0, decoupled_energy=0.95,
                        coupled=False, negative_control=0.04, synthetic=False)
    att = verify_recency_bound_presence(decoupled, _good_posr(), _good_gic(), ts_ns=100)
    assert att.verdict == PresenceVerdict.DECOUPLED_REVIEW.value
    assert att.visual_state == "unverified"


def test_synthetic_renders_emulated_not_live():
    synth = PoCPLeg(coupling_score=0.62, lag_ms=140.0, decoupled_energy=0.3,
                    coupled=True, negative_control=0.04, synthetic=True)
    att = verify_recency_bound_presence(synth, _good_posr(), _good_gic(), ts_ns=100)
    assert att.visual_state == "emulated"


# ── honesty rails ────────────────────────────────────────────────────────────

def test_claim_scope_always_present_and_not_tournament_grade():
    att = verify_recency_bound_presence(_good_pocp(), _good_posr(), _good_gic(), ts_ns=100)
    assert "NOT standalone-tournament-grade" in att.claim_scope


def test_label_never_claims_zk_or_anchor():
    att = verify_recency_bound_presence(_good_pocp(), _good_posr(), _good_gic(), ts_ns=100)
    il = att.vpm_label["integrity_label"]
    assert il["zk_verified"] is False and il["on_chain_anchor"] is False
    assert att.vpm_label["anchor_status"] == "none"


def test_overclaim_rejected_on_verify():
    """Hand-edit a decoupled attestation to claim `live` → verify must reject (anti-overclaim)."""
    import hashlib, json
    decoupled = PoCPLeg(coupling_score=0.05, lag_ms=140.0, decoupled_energy=0.95,
                        coupled=False, negative_control=0.04, synthetic=False)
    att = asdict(verify_recency_bound_presence(decoupled, _good_posr(), _good_gic(), ts_ns=100))
    att["visual_state"] = "live"
    body = {k: v for k, v in att.items() if k != "attestation_hash"}
    att["attestation_hash"] = hashlib.sha256(
        json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    ok, reason = verify_attestation(att)
    assert ok is False and "overclaim" in reason


def test_body_tamper_rejected():
    from dataclasses import asdict as _a
    att = _a(verify_recency_bound_presence(_good_pocp(), _good_posr(), _good_gic(), ts_ns=100))
    att["claim_scope"] = "tournament-grade!"          # tamper, keep old hash
    ok, reason = verify_attestation(att)
    assert ok is False and "tamper" in reason


def test_deterministic():
    a = verify_recency_bound_presence(_good_pocp(), _good_posr(), _good_gic(), ts_ns=100)
    b = verify_recency_bound_presence(_good_pocp(), _good_posr(), _good_gic(), ts_ns=100)
    assert a.attestation_hash == b.attestation_hash


def test_module_is_chain_and_numpy_free():
    """Packaging-only: no chain, no numpy, no l9 heavy import in the verifier module."""
    import ast, inspect
    from vapi_bridge import recency_bound_presence as M
    tree = ast.parse(inspect.getsource(M))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert "numpy" not in imported and "web3" not in imported
    assert imported <= {"hashlib", "json", "dataclasses", "enum", "typing", "__future__"}


def test_visual_state_vocab_subset_of_frozen_vpm():
    """Drift guard: mirrored vocab must remain a subset of the FROZEN VPMVisualState enum."""
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts"))
    try:
        from vsd_vpm_wrapper import VPMVisualState
    except Exception as exc:
        import pytest
        pytest.skip(f"vsd_vpm_wrapper not importable: {exc}")
    frozen = {v.value.replace("_", "-") for v in VPMVisualState}
    assert set(VPM_VISUAL_STATES).issubset(frozen)
