"""WMP AH-1 — C1 pinning tests (A1 matrix-swap CAUGHT at matrix_root_rehash).

Zero-trust posture: attacks are outside-in on the PUBLISHED UC-1 bundle bytes
(file read, never the assembler). The Poseidon oracle is mocked HONESTLY (real
root only for base's matrix); the full-crypto A1 kill is already banked in
audits/wmp-phase2-first-real-bundle-2026-07-11.md. These tests are the CI-fast
regression pin so the matrix-swap defense can never silently regress.

Design: docs/wmp-adversarial-hardening-ah1-design-2026-07-11.md (+ §9)
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from sdk.wmp_verify import verify_bundle
from sdk.wmp_adversarial import attacks
from sdk.wmp_adversarial.matrix import run_all, run_one, CAUGHT


def _base() -> dict:
    return attacks.load_uc1_bundle()


# ── harness sanity ────────────────────────────────────────────────────────

def test_uc1_bundle_loads_real():
    b = _base()
    assert b["schema"] == "vapi-wmp-provenance-bundle-v1"
    assert b["scope_synthetic"] is False
    assert b["action_trace_matrix_hex"]["stick_L_sector"]
    assert str(b["humanity_proof_public_inputs"]["sanitizedTraceRoot"]).isdigit()


def test_poseidon_mock_is_honest():
    """Mock returns the real root ONLY for base's matrix; any mutation differs."""
    b = _base()
    mock = attacks.poseidon_mock_for(b)
    claimed = str(b["humanity_proof_public_inputs"]["sanitizedTraceRoot"])
    honest_arg = {"ticks": b["action_trace_ticks"],
                  **{c: b["action_trace_matrix_hex"][c] for c in attacks.CHANNELS}}
    assert mock(honest_arg) == claimed
    mutated = dict(honest_arg)
    mutated["stick_L_sector"] = "ff" + honest_arg["stick_L_sector"][2:]
    assert mock(mutated) != claimed


# ── A1: control then kill ─────────────────────────────────────────────────

def test_A1_control_base_verifies_rehash():
    """CONTROL — the UNFORGED base passes rehash under the honest mocks, so the
    swap's REJECT below is attributable to the forgery, not the harness."""
    b = _base()
    res = verify_bundle(b, **attacks.honest_kwargs(b))
    assert res.checks["matrix_root_rehash"]["passed"] is True
    assert res.checks["matrix_root_rehash"]["algorithm"] == "POSEIDON_BN254"
    assert res.overall == "VERIFIED"


def test_A1_matrix_swap_rejected():
    """One flipped matrix nibble under a still-valid proof -> REJECTED at rehash."""
    b = _base()
    forged = attacks.matrix_swap(b)
    res = verify_bundle(forged, **attacks.honest_kwargs(b))
    assert res.overall == "REJECTED"
    assert res.checks["matrix_root_rehash"]["passed"] is False
    assert any("matrix_root_rehash" in r for r in res.reasons)


def test_A1_swap_is_surgical_only_rehash_fails():
    """The forgery is surgical: humanity / consent / scope still pass — only the
    matrix<->root binding catches it (proves the rehash check is load-bearing)."""
    b = _base()
    res = verify_bundle(attacks.matrix_swap(b), **attacks.honest_kwargs(b))
    assert res.checks["humanity"]["passed"] is True
    assert res.checks["consent"]["passed"] is True
    assert res.checks["scope_honesty"]["passed"] is True


def test_A1_swap_each_channel_caught():
    """Flipping ANY matrix channel is caught — not just the default one."""
    b = _base()
    for ch in attacks.CHANNELS:
        res = verify_bundle(attacks.matrix_swap(b, channel=ch), **attacks.honest_kwargs(b))
        assert res.overall == "REJECTED", f"swap of {ch} was not rejected"
        assert res.checks["matrix_root_rehash"]["passed"] is False


# ── A3: gamer-address swap (consent oracle) ────────────────────────────────

def test_A3_gamer_swap_rejected():
    """Repoint consent_gamer_address to a non-consenter -> REJECTED at consent
    (the injected on-chain oracle returns not-granted)."""
    b = _base()
    forged = attacks.gamer_address_swap(b)
    res = verify_bundle(forged, **attacks.honest_kwargs(b))
    assert res.overall == "REJECTED"
    assert res.checks["consent"]["passed"] is False
    assert res.checks["consent"]["stubbed"] is False   # the on-chain oracle actually ran
    assert any("consent" in r for r in res.reasons)


def test_A3_swap_is_surgical_only_consent_fails():
    """Only consent fails — matrix/humanity/scope untouched (surgical forgery)."""
    b = _base()
    res = verify_bundle(attacks.gamer_address_swap(b), **attacks.honest_kwargs(b))
    assert res.checks["matrix_root_rehash"]["passed"] is True
    assert res.checks["humanity"]["passed"] is True
    assert res.checks["scope_honesty"]["passed"] is True


def test_A3_gap_watch_stub_not_at_bar():
    """Design §9.1 / A3 gap-watch: with consent_lookup=None the GRANTED bundle
    passes consent as an HONEST stub (stubbed=True), NOT a silent crypto pass.
    The pure path reports VERIFIED, but the full-verify zero-stub bar
    (wmp_full_verify.py L205) excludes stubbed checks — so a runner without
    --consent-registry is misconfiguration, never CAUGHT. This proves the
    CAUGHT depends on injecting the oracle."""
    b = _base()
    forged = attacks.gamer_address_swap(b)
    kw = attacks.honest_kwargs(b)
    kw["consent_lookup"] = None                          # simulate no --consent-registry
    res = verify_bundle(forged, **kw)
    assert res.checks["consent"]["stubbed"] is True
    assert res.checks["consent"]["passed"] is True       # honest stub, not a crypto pass
    assert res.overall == "VERIFIED"                     # pure path "passes" — why the bar matters


# ── A15: forbidden-key smuggle (post-φ data floor, GAP-FOUND-AND-FIXED) ─────

@pytest.mark.parametrize("where", ["top", "extra_metadata", "channel"])
def test_A15_forbidden_key_smuggle_rejected(where):
    """A smuggled biometric key at any placement -> REJECTED at scope_honesty."""
    b = _base()
    forged = attacks.forbidden_key_smuggle(b, where=where)
    res = verify_bundle(forged, **attacks.honest_kwargs(b))
    assert res.overall == "REJECTED"
    assert res.checks["scope_honesty"]["passed"] is False
    assert any("forbidden" in r for r in res.reasons)


def test_A15_clean_bundle_still_verifies():
    """The fix must not regress: a clean bundle (no forbidden keys) still passes
    scope_honesty and VERIFIES — the fix is additive, not a new false-positive."""
    b = _base()
    res = verify_bundle(b, **attacks.honest_kwargs(b))
    assert res.checks["scope_honesty"]["passed"] is True
    assert res.overall == "VERIFIED"


def test_A15_representative_forbidden_columns_caught():
    """A sample across the L4/L5/E4/AIT/tremor families is caught at top-level."""
    b = _base()
    for key in ("l4_mahalanobis_distance", "ait_rms", "micro_tremor_variance",
                "e4_spectral_entropy", "press_timing_jitter_variance"):
        res = verify_bundle(attacks.forbidden_key_smuggle(b, key=key, where="top"),
                            **attacks.honest_kwargs(b))
        assert res.overall == "REJECTED", f"{key} was not caught"
        assert res.checks["scope_honesty"]["passed"] is False


# ── matrix runner ─────────────────────────────────────────────────────────

def test_matrix_holds_all_vectors_caught():
    m = run_all()
    assert m.holds
    assert len(m.results) == 3
    by_id = {r.id: r for r in m.results}
    assert by_id["A1"].result == CAUGHT and by_id["A1"].ok is True
    assert by_id["A3"].result == CAUGHT and by_id["A3"].ok is True
    assert by_id["A15"].result == "GAP-FOUND-AND-FIXED" and by_id["A15"].ok is True


def test_run_one_all_banked():
    for vid in ("A1", "A3", "A15"):
        assert run_one(vid).ok is True


def test_run_one_unknown_vector_raises():
    with pytest.raises(KeyError):
        run_one("A999")
