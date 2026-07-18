"""(ii) R2-onset Increment-0 — unit tests for the offline actuator-coupling study analyzer.

Pure-function tests for analyze_fire (scripts/poep_ring_coupling_study.py): it must separate the
challenge's own commanded R2 force (actuator window) from the operator's reaction (post window) using
the device clock, and honestly report NO onset when R2 doesn't move. No bridge, no corpus, no claim.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from poep_ring_coupling_study import analyze_fire  # noqa: E402

_PROBE = 1_000_000
_TPMS = 3000


def _fr(r2, rel_ms):
    return {"r2": r2, "device_ts": int(_PROBE + rel_ms * _TPMS)}


def test_analyze_fire_separates_actuator_tug_from_human_onset():
    # tug (r2=200) inside the actuator window [0, hold+settle], then a SUSTAINED human onset ~210ms in the
    # actuator-blind post window. The naive "first movement" detector must FALSE-fire on the tug; the gated
    # detector must place the human onset in the post window; T_mech re-quiet must be found.
    rec = {
        "schema": "qortroller-poep-ring-dump-v0", "nonce": "t1",
        "probe_r2_force": 200, "probe_mode": "pulse", "probe_hold_ms": 15,
        "probe_device_ts": _PROBE, "device_ticks_per_ms": _TPMS,
        "pre_series": [{"r2": 0, "device_ts": _PROBE - 5000 + i * 1000} for i in range(5)],
        "post_series": [_fr(200, 8), _fr(190, 20), _fr(0, 50), _fr(0, 120),
                        _fr(60, 210), _fr(66, 211), _fr(70, 212)],
    }
    out = analyze_fire(rec)
    assert out["pre_mean_r2"] == 0.0
    assert out["max_dR2_actuator"] >= 190.0           # the commanded tug dominates the actuator window
    assert out["gated_onset_ms"] is not None and out["gated_onset_ms"] > 45.0   # human onset is post-window
    assert out["naive_in_actuator"] is True           # naive detector wrongly fires on the actuator tug
    assert out["t_mech_ms"] is not None               # R2 re-quiet (settle) detected


def test_analyze_fire_reports_no_onset_when_r2_stays_quiet():
    # tug then quiet, no operator reaction -> honest NO gated onset (a no-go signal, never fabricated).
    rec = {
        "schema": "qortroller-poep-ring-dump-v0", "nonce": "t2", "probe_hold_ms": 15,
        "probe_device_ts": _PROBE, "device_ticks_per_ms": _TPMS,
        "pre_series": [{"r2": 0, "device_ts": _PROBE - 1000}],
        "post_series": [_fr(180, 10), _fr(0, 50), _fr(1, 200), _fr(0, 210)],
    }
    out = analyze_fire(rec)
    assert out["gated_onset_ms"] is None              # no sustained post-window movement -> honest no-go
    assert out["max_dR2_post"] <= 5.0


def test_analyze_fire_handles_missing_device_ts_frames():
    # frames without device_ts must not crash and must not be counted as timed (n_post_with_dev_ts).
    rec = {
        "schema": "qortroller-poep-ring-dump-v0", "nonce": "t3", "probe_hold_ms": 15,
        "probe_device_ts": _PROBE, "device_ticks_per_ms": _TPMS,
        "pre_series": [{"r2": 0, "device_ts": _PROBE - 1000}],
        "post_series": [{"r2": 90}, {"r2": 90}, _fr(90, 200)],   # first two lack device_ts
    }
    out = analyze_fire(rec)
    assert out["n_post_with_dev_ts"] == 1             # only the one timed frame counts
