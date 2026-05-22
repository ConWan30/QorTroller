"""Tests for PoEP P1 pure logic (no hardware)."""
from l9_presence.poep import (
    PoEPSession, compute_poep_commitment, extract_reflex_features, load_poep_session,
    nonce_schedule, save_poep_session,
)

_BASE = {"RX": 128, "RY": 128, "R2": 0, "L2": 0, "accel_mag": 1.0}


def test_nonce_schedule_deterministic_with_seed():
    a = nonce_schedule(5, seed=7)
    b = nonce_schedule(5, seed=7)
    assert a == b                          # seed -> reproducible (tests only)
    assert len({n for n, _ in a}) == 5     # distinct nonces
    assert all(1.0 <= g <= 3.0 for _, g in a)
    assert all(len(n) == 32 for n, _ in a)  # 16-byte hex


def _window_with_reaction(onset_ms=300, deflection=72):
    w = []
    for t in range(0, 600, 5):
        rx = 128 + (deflection if t >= onset_ms else 0)
        w.append({"t_ms": float(t), "RX": rx, "RY": 128, "R2": 0, "L2": 0, "accel_mag": 1.0})
    return w


def test_extract_features_detects_in_band_reaction():
    f = extract_reflex_features(_window_with_reaction(300), 0.0, _BASE)
    assert f["reacted"] is True
    assert 290 <= f["reaction_latency_ms"] <= 310
    assert f["in_band"] is True
    assert f["peak_stick_deflection"] >= 70


def test_extract_features_flat_window_no_reaction():
    flat = [{"t_ms": float(t), "RX": 128, "RY": 128, "R2": 0, "L2": 0, "accel_mag": 1.0}
            for t in range(0, 600, 5)]
    f = extract_reflex_features(flat, 0.0, _BASE)
    assert f["reacted"] is False and f["in_band"] is False


def test_commitment_deterministic_and_sensitive():
    recs = [{"nonce": "ab" * 16, "stim_t_ms": 0.0,
             "features": {"reaction_latency_ms": 300, "peak_stick_deflection": 72,
                          "peak_r2": 0, "grip_micro_adjustment": 0.1, "force_response_auc": 5.0}}]
    kw = dict(player="P1", device_id="Edge", challenge_records=recs, ts_ns=123)
    a = compute_poep_commitment(**kw)
    assert a == compute_poep_commitment(**kw) and len(a) == 64
    recs2 = [{**recs[0], "features": {**recs[0]["features"], "reaction_latency_ms": 301}}]
    assert compute_poep_commitment(**{**kw, "challenge_records": recs2}) != a


def test_session_roundtrip(tmp_path):
    s = PoEPSession("P1", "Edge", [{"nonce": "cd" * 16, "stim_t_ms": 0.0, "features": {}}],
                    "deadbeef", 999)
    p = str(tmp_path / "P1_01.poep.json")
    save_poep_session(p, s)
    r = load_poep_session(p)
    assert r.player == "P1" and r.commitment == "deadbeef" and r.poep_enabled is False
