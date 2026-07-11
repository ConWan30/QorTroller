"""WMP Verifiable Derived-Claim (VDC-1) — C1 pinning tests.

First derivation: trigger_engagement_fraction (the Phase 235-GAD ACTIVE_GAMEPLAY
signal made verifiable). Verification is RE-DERIVATION — recompute over the
bundle + byte-compare — never trust of the stored value. Data-floor rail reuses
the AH-1-hardened forbidden set.

Design: docs/wmp-derived-claim-vdc1-2026-07-11.md
"""
from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

import pytest

from sdk.wmp_derived import (build_claim, verify_claim, _claim_hash,
                             DERIVATIONS, CEILING, SCHEMA, PARENT_SCHEMA)

_UC1 = REPO_ROOT / "wmp_corpus_real" / "wmp_corpus.jsonl"
_DERIV = "TRIGGER_ENGAGEMENT_FRACTION_v1"
_DERIVS = ("TRIGGER_ENGAGEMENT_FRACTION_v1", "ACTION_ENTROPY_v1",
           "INPUT_TEMPO_v1", "STICK_ENGAGEMENT_FRACTION_v1",
           "BUTTON_PRESS_COUNT_v1")


def _base() -> dict:
    return json.loads(_UC1.read_text(encoding="utf-8").splitlines()[0])


def _check(res: dict, name: str):
    for c in res["checks"]:
        if c["name"] == name:
            return c["ok"]
    return None


# ── build + verify ─────────────────────────────────────────────────────────

@pytest.mark.parametrize("deriv", _DERIVS)
def test_build_and_verify_roundtrip(deriv):
    b = _base()
    res = verify_claim(build_claim(b, deriv), b)
    assert res["ok"] is True
    assert all(c["ok"] for c in res["checks"])


def test_real_trigger_fraction_value_pinned():
    """Regression pin: the derivation's output on the real M17 bundle."""
    v = build_claim(_base(), _DERIV)["value"]
    assert v["ticks"] == 1730
    assert v["active_ticks"] == 173
    assert v["fraction"] == 0.1
    assert v["channels_read"] == ["trigger_L_state", "trigger_R_state"]


def test_claim_schema_and_binding_fields():
    claim = build_claim(_base(), _DERIV)
    assert claim["schema"] == SCHEMA
    assert claim["parent_schema"] == PARENT_SCHEMA
    assert len(claim["parent_bundle_hash"]) == 64
    assert len(claim["claim_hash"]) == 64
    assert claim["ceiling"] == CEILING


# ── tamper rails (fail-closed) ─────────────────────────────────────────────

def test_parent_swap_fails_binding():
    """A claim verified against a DIFFERENT bundle -> parent_binding FAIL."""
    b = _base()
    claim = build_claim(b, _DERIV)
    other = copy.deepcopy(b)
    mh = other["action_trace_matrix_hex"]
    first = mh["trigger_L_state"][0]
    mh["trigger_L_state"] = ("f" if first != "f" else "0") + mh["trigger_L_state"][1:]
    res = verify_claim(claim, other)
    assert res["ok"] is False
    assert _check(res, "parent_binding") is False


def test_value_tamper_fails_claim_hash():
    """Lie about the value without re-hashing -> record integrity FAIL."""
    b = _base()
    claim = build_claim(b, _DERIV)
    claim["value"]["fraction"] = 0.99
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "claim_hash") is False


def test_value_tamper_with_rehash_fails_rederive():
    """Even re-hashing the tampered claim cannot survive re-derivation."""
    b = _base()
    claim = build_claim(b, _DERIV)
    claim["value"]["fraction"] = 0.99
    claim["value"]["active_ticks"] = 9999
    claim["claim_hash"] = _claim_hash(claim)       # fix record integrity
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "claim_hash") is True        # integrity now passes
    assert _check(res, "value_rederive") is False   # but the value cannot re-derive


def test_ceiling_tamper_fails():
    b = _base()
    claim = build_claim(b, _DERIV)
    claim["ceiling"] = {"n_equals_1": "stripped the rest"}
    claim["claim_hash"] = _claim_hash(claim)
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "ceiling_verbatim") is False


# ── data-floor rail (reuses the AH-1-hardened forbidden set) ───────────────

def test_forbidden_parent_refused_at_build():
    b = _base()
    b["ait_rms"] = [0.04, 0.05]                     # smuggle a biometric key
    with pytest.raises(ValueError, match="forbidden"):
        build_claim(b, _DERIV)


def test_forbidden_parent_fails_verify():
    b = _base()
    claim = build_claim(b, _DERIV)
    tainted = copy.deepcopy(b)
    tainted["extra_metadata"] = dict(tainted.get("extra_metadata") or {})
    tainted["extra_metadata"]["l4_mahalanobis_distance"] = [1, 2, 3]
    res = verify_claim(claim, tainted)
    assert res["ok"] is False
    assert _check(res, "data_floor") is False


def test_derivation_reads_only_allowed_channels():
    """The banked derivation declares + reads only non-forbidden channels."""
    from sdk.wmp_verify import _FROZEN_FORBIDDEN_COLUMNS
    v = build_claim(_base(), _DERIV)["value"]
    assert all(c not in _FROZEN_FORBIDDEN_COLUMNS for c in v["channels_read"])


# ── C2: ACTION_ENTROPY_v1 (variety of play) ────────────────────────────────

def test_action_entropy_real_values_pinned():
    """Regression pin: per-channel entropy (integer millibits) on real M17."""
    pc = build_claim(_base(), "ACTION_ENTROPY_v1")["value"]["per_channel"]
    assert pc["stick_L_sector"] == {"entropy_millibits": 3373, "symbols": 17, "normalized_milli": 825}
    assert pc["stick_R_sector"] == {"entropy_millibits": 3300, "symbols": 17, "normalized_milli": 807}
    assert pc["trigger_L_state"] == {"entropy_millibits": 651, "symbols": 16, "normalized_milli": 163}
    assert pc["trigger_R_state"] == {"entropy_millibits": 536, "symbols": 13, "normalized_milli": 145}
    assert pc["button_mask"] == {"entropy_millibits": 125, "symbols": 6, "normalized_milli": 49}


def test_action_entropy_excludes_imu():
    """imu_gravity_sector is postural — excluded from action entropy."""
    v = build_claim(_base(), "ACTION_ENTROPY_v1")["value"]
    assert "imu_gravity_sector" not in v["channels_read"]
    assert "imu_gravity_sector" not in v["per_channel"]
    assert v["channels_read"] == ["stick_L_sector", "stick_R_sector",
                                  "trigger_L_state", "trigger_R_state", "button_mask"]


def test_action_entropy_values_are_integers():
    """Deterministic re-derivation depends on integer millibits (no raw floats)."""
    v = build_claim(_base(), "ACTION_ENTROPY_v1")["value"]
    for d in v["per_channel"].values():
        assert isinstance(d["entropy_millibits"], int)
        assert isinstance(d["normalized_milli"], int)
        assert 0 <= d["normalized_milli"] <= 1000


def test_action_entropy_deterministic():
    b = _base()
    assert build_claim(b, "ACTION_ENTROPY_v1")["value"] == build_claim(b, "ACTION_ENTROPY_v1")["value"]


def test_action_entropy_tamper_fails_rederive():
    b = _base()
    claim = build_claim(b, "ACTION_ENTROPY_v1")
    claim["value"]["per_channel"]["stick_L_sector"]["entropy_millibits"] = 9999
    claim["claim_hash"] = _claim_hash(claim)          # fix record integrity
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "value_rederive") is False


# ── C3: INPUT_TEMPO_v1 (cadence) ───────────────────────────────────────────

def test_input_tempo_real_values_pinned():
    """Regression pin: per-channel transition count + rate on real M17."""
    v = build_claim(_base(), "INPUT_TEMPO_v1")["value"]
    assert v["ticks"] == 1730
    assert v["total_transitions"] == 2225
    pc = v["per_channel"]
    assert pc["stick_L_sector"] == {"transitions": 870, "per_1000_ticks": 503}
    assert pc["stick_R_sector"] == {"transitions": 936, "per_1000_ticks": 541}
    assert pc["trigger_L_state"] == {"transitions": 203, "per_1000_ticks": 117}
    assert pc["trigger_R_state"] == {"transitions": 183, "per_1000_ticks": 106}
    assert pc["button_mask"] == {"transitions": 33, "per_1000_ticks": 19}


def test_input_tempo_excludes_imu():
    v = build_claim(_base(), "INPUT_TEMPO_v1")["value"]
    assert "imu_gravity_sector" not in v["channels_read"]
    assert "imu_gravity_sector" not in v["per_channel"]


def test_input_tempo_integers_and_total_consistent():
    """All integers (deterministic) and total_transitions == sum of per-channel."""
    v = build_claim(_base(), "INPUT_TEMPO_v1")["value"]
    s = 0
    for d in v["per_channel"].values():
        assert isinstance(d["transitions"], int) and isinstance(d["per_1000_ticks"], int)
        s += d["transitions"]
    assert s == v["total_transitions"]


def test_input_tempo_tamper_fails_rederive():
    b = _base()
    claim = build_claim(b, "INPUT_TEMPO_v1")
    claim["value"]["per_channel"]["stick_R_sector"]["transitions"] = 1
    claim["claim_hash"] = _claim_hash(claim)
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "value_rederive") is False


# ── C4: STICK_ENGAGEMENT_FRACTION_v1 (steering/aim) ────────────────────────

def test_stick_engagement_real_value_pinned():
    v = build_claim(_base(), "STICK_ENGAGEMENT_FRACTION_v1")["value"]
    assert v["ticks"] == 1730
    assert v["engaged_ticks"] == 1726
    assert v["fraction"] == 0.997688
    assert v["neutral_sector"] == 16
    assert v["channels_read"] == ["stick_L_sector", "stick_R_sector"]


def test_stick_engagement_neutral_is_16_not_zero():
    """Honesty-critical: sector 0 is a real direction (engaged); only sector 16
    (the deadzone sentinel) is neutral. Uses a crafted 3-tick matrix."""
    from sdk.wmp_derived import derive_stick_engagement_fraction
    mini = {
        "action_trace_ticks": 3,
        "action_trace_matrix_hex": {
            "stick_L_sector": bytes([0, 16, 5]).hex(),   # east, neutral, a direction
            "stick_R_sector": bytes([16, 16, 16]).hex(),  # all neutral
        },
    }
    v = derive_stick_engagement_fraction(mini)
    # tick0 L=0 -> engaged; tick1 both 16 -> idle; tick2 L=5 -> engaged
    assert v["engaged_ticks"] == 2
    assert v["neutral_sector"] == 16


def test_stick_engagement_tamper_fails_rederive():
    b = _base()
    claim = build_claim(b, "STICK_ENGAGEMENT_FRACTION_v1")
    claim["value"]["engaged_ticks"] = 0
    claim["value"]["fraction"] = 0.0
    claim["claim_hash"] = _claim_hash(claim)
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "value_rederive") is False


# ── C5: BUTTON_PRESS_COUNT_v1 (interaction volume) ─────────────────────────

def test_button_press_count_real_values_pinned():
    v = build_claim(_base(), "BUTTON_PRESS_COUNT_v1")["value"]
    assert v["ticks"] == 1730
    assert v["press_events"] == 17
    assert v["distinct_buttons"] == 5
    assert v["active_ticks"] == 23
    assert v["channels_read"] == ["button_mask"]


def test_button_press_count_counts_rising_edges_not_active_ticks():
    """A held button is ONE press, not one-per-tick; a re-press after release
    counts again. (button_mask is 2 bytes/tick, big-endian.)"""
    from sdk.wmp_derived import derive_button_press_count
    # masks per tick: 1, 1, 0, 1  → bit0 rises at t0 and t3 = 2 events; active=3
    mini = {"action_trace_ticks": 4,
            "action_trace_matrix_hex": {"button_mask": bytes([0, 1, 0, 1, 0, 0, 0, 1]).hex()}}
    v = derive_button_press_count(mini)
    assert v["press_events"] == 2
    assert v["active_ticks"] == 3
    assert v["distinct_buttons"] == 1


def test_button_press_count_overlapping_buttons():
    """Simultaneous/overlapping presses each count (per-bit rising edges)."""
    from sdk.wmp_derived import derive_button_press_count
    # masks per tick: 1 (bit0), 3 (bit0+bit1), 2 (bit1) → bit0@t0 + bit1@t1 = 2 events
    mini = {"action_trace_ticks": 3,
            "action_trace_matrix_hex": {"button_mask": bytes([0, 1, 0, 3, 0, 2]).hex()}}
    v = derive_button_press_count(mini)
    assert v["press_events"] == 2
    assert v["distinct_buttons"] == 2


def test_button_press_count_tamper_fails_rederive():
    b = _base()
    claim = build_claim(b, "BUTTON_PRESS_COUNT_v1")
    claim["value"]["press_events"] = 999
    claim["claim_hash"] = _claim_hash(claim)
    res = verify_claim(claim, b)
    assert res["ok"] is False
    assert _check(res, "value_rederive") is False


# ── registry ───────────────────────────────────────────────────────────────

def test_unknown_derivation_raises():
    with pytest.raises(KeyError):
        build_claim(_base(), "NOPE_v1")


def test_wrong_parent_schema_refused():
    b = _base()
    b["schema"] = "not-a-wmp-bundle"
    with pytest.raises(ValueError, match="schema"):
        build_claim(b, _DERIV)
