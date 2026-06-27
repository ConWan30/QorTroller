"""Cycle-37 — PoEP Track-1 activation layer (two-key gate -> co-capture poep_present contract).

The load-bearing tests are the TWO-KEY gate: poep_present is None (ABSTAIN) unless BOTH the operator
flip (poep_enabled) AND the data gate (N>=50, verdict not calibration_incomplete) pass.
"""
from __future__ import annotations

from vapi_bridge.poep_activation import poep_activation_status, poep_present_signal


# --- operator gate (key 1) ---

def test_operator_gate_off_abstains_even_when_present():
    # even a PRESENT verdict must abstain until the operator flips poep_enabled
    assert poep_present_signal({"verdict": "PRESENT"}, poep_enabled=False) is None
    assert poep_present_signal({"verdict": "REJECT"}, poep_enabled=False) is None


# --- data gate (key 2) ---

def test_data_gate_incomplete_abstains_even_when_enabled():
    # operator flipped, but N<50 (calibration_incomplete) -> still abstain (hard rule)
    v = {"status": "calibration_incomplete", "n_reactions": 12, "min_n": 50}
    assert poep_present_signal(v, poep_enabled=True) is None


# --- both keys pass ---

def test_both_keys_present_true():
    assert poep_present_signal({"verdict": "PRESENT"}, poep_enabled=True) is True


def test_both_keys_reject_false():
    assert poep_present_signal({"verdict": "REJECT"}, poep_enabled=True) is False


def test_liveness_score_shape_fallback():
    # a liveness_score()-shaped dict (no combined verdict) falls back to liveness_pass
    assert poep_present_signal({"liveness_pass": True}, poep_enabled=True) is True
    assert poep_present_signal({"liveness_pass": False}, poep_enabled=True) is False


def test_none_and_unrecognized_abstain():
    assert poep_present_signal(None, poep_enabled=True) is None
    assert poep_present_signal({}, poep_enabled=True) is None
    assert poep_present_signal({"foo": "bar"}, poep_enabled=True) is None


# --- activation status ---

def test_status_calibration_incomplete():
    r = {"calibration_complete": False, "total_in_band_reactions": 12, "min_n": 50, "reactions_needed": 38}
    s = poep_activation_status(r, poep_enabled=False)
    assert s["status"] == "CALIBRATION_INCOMPLETE"
    assert s["activated"] is False
    assert s["reactions_needed"] == 38


def test_status_ready_to_activate_operator_gate():
    # data ready (N>=50) but the operator hasn't flipped -> waiting on the two-key
    r = {"calibration_complete": True, "total_in_band_reactions": 55, "min_n": 50, "reactions_needed": 0}
    s = poep_activation_status(r, poep_enabled=False)
    assert s["status"] == "READY_TO_ACTIVATE_OPERATOR_GATE"
    assert s["activated"] is False
    assert s["data_gate_n_ready"] is True


def test_status_activated_only_with_both_keys():
    r = {"calibration_complete": True, "total_in_band_reactions": 55, "min_n": 50, "reactions_needed": 0}
    s = poep_activation_status(r, poep_enabled=True)
    assert s["status"] == "ACTIVATED"
    assert s["activated"] is True


# --- Stage 2: session verdict file read (fresh/stale gate) ---

def test_read_verdict_missing_file_abstains(tmp_path):
    from vapi_bridge.poep_activation import read_session_poep_verdict
    assert read_session_poep_verdict(str(tmp_path / "nope.json")) is None


def test_read_verdict_fresh_returns_it(tmp_path):
    import json as _j, time as _t
    from vapi_bridge.poep_activation import read_session_poep_verdict
    p = tmp_path / "v.json"
    p.write_text(_j.dumps({"verdict": "PRESENT", "ts_ns": _t.time_ns(), "cert_scope": "developer_self"}))
    v = read_session_poep_verdict(str(p), max_age_s=7200)
    assert v is not None and v["verdict"] == "PRESENT"


def test_read_verdict_stale_abstains(tmp_path):
    import json as _j, time as _t
    from vapi_bridge.poep_activation import read_session_poep_verdict
    p = tmp_path / "v.json"
    old = _t.time_ns() - 10_000 * 1_000_000_000   # 10000s old
    p.write_text(_j.dumps({"verdict": "PRESENT", "ts_ns": old}))
    assert read_session_poep_verdict(str(p), max_age_s=7200) is None


def test_read_verdict_future_dated_abstains(tmp_path):
    import json as _j, time as _t
    from vapi_bridge.poep_activation import read_session_poep_verdict
    p = tmp_path / "v.json"
    p.write_text(_j.dumps({"verdict": "PRESENT", "ts_ns": _t.time_ns() + 3600 * 1_000_000_000}))
    assert read_session_poep_verdict(str(p), max_age_s=7200) is None


def test_read_verdict_malformed_abstains(tmp_path):
    from vapi_bridge.poep_activation import read_session_poep_verdict
    p = tmp_path / "v.json"
    p.write_text("{not json")
    assert read_session_poep_verdict(str(p)) is None


def test_read_verdict_feeds_present_signal_end_to_end(tmp_path):
    # the verdict file -> read -> poep_present_signal (two-key) -> True
    import json as _j, time as _t
    from vapi_bridge.poep_activation import read_session_poep_verdict, poep_present_signal
    p = tmp_path / "v.json"
    p.write_text(_j.dumps({"verdict": "PRESENT", "ts_ns": _t.time_ns()}))
    v = read_session_poep_verdict(str(p))
    assert poep_present_signal(v, poep_enabled=True) is True
    assert poep_present_signal(v, poep_enabled=False) is None   # operator key still required
