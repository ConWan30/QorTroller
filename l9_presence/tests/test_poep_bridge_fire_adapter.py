"""BridgeFireCaptureAdapter tests - the weakest-seam pins (grok r02 F), fake bridge only (no live bridge).

Pins: a real fire requires the bridge to confirm fired+real_hardware+nonce-match; a 200 without them is
NOT a fire; no band-filled latency; one-shot stash; bridge-unreachable -> honest fail; and END-TO-END
through the SEALED challenge_live (a confirmed bridge fire drives a live GO verify).
"""
import re
from pathlib import Path

from l9_presence.poep_bridge_fire_adapter import BridgeFireCaptureAdapter
from l9_presence.poep_gameplay_live import (
    ImuWindow, challenge_live, poll_bridge_activity, start_live_session,
)
from l9_presence.poep_gameplay_session import ChallengeKind, LOW_AMPLITUDE_FORCE_MAX

_MOD = Path(__file__).resolve().parents[1] / "poep_bridge_fire_adapter.py"


def _resp_ok(*, t=1000, latency=250.0, peak=3000.0, precursor=5.0):
    """A bridge response confirming a real nonce-bound fire (echoes the request nonce)."""
    def _post(amp, nonce):
        return {"fired": True, "real_hardware": True, "nonce": nonce, "t_fire_ns": t,
                "latency_ms": latency, "peak_lsb": peak, "precursor_gap_ms": precursor}
    return _post


def _resp(overrides):
    def _post(amp, nonce):
        base = {"fired": True, "real_hardware": True, "nonce": nonce, "t_fire_ns": 1000,
                "latency_ms": 250.0, "peak_lsb": 3000.0, "precursor_gap_ms": 5.0}
        base.update(overrides)
        return base
    return _post


def _adapter(post):
    return BridgeFireCaptureAdapter(post_fire=post)


# ── confirmed real fire -> real_hardware=True + one-shot window ────────────────
def test_confirmed_fire_is_real_and_stashes():
    a = _adapter(_resp_ok(t=42))
    fr = a.fire_fn(60, "n")
    assert fr.fired is True and fr.real_hardware is True and fr.t_fire_ns == 42
    win = a.imu_capture_fn(42)
    assert isinstance(win, ImuWindow) and win.latency_ms == 250.0 and win.peak_lsb == 3000.0
    assert a.imu_capture_fn(42) is None      # one-shot consumed
    assert a.imu_capture_fn(0) is None       # NO_GO never steals a GO window


# ── weakest-seam pins: a 200 without a confirmed real nonce-bound fire is NOT a fire ──
def test_missing_real_hardware_refused():
    fr = _adapter(_resp({"real_hardware": False})).fire_fn(60, "n")
    assert fr.fired is False and fr.real_hardware is False
    assert "did not confirm" in fr.error


def test_not_fired_refused():
    fr = _adapter(_resp({"fired": False})).fire_fn(60, "n")
    assert fr.fired is False and fr.real_hardware is False


def test_nonce_mismatch_refused():
    fr = _adapter(_resp({"nonce": "WRONG"})).fire_fn(60, "n")
    assert fr.fired is False and fr.real_hardware is False
    a = _adapter(_resp({"nonce": "WRONG"}))
    a.fire_fn(60, "n")
    assert a.imu_capture_fn(1000) is None    # nothing stashed on a refused fire


# ── bridge unreachable / malformed -> honest fail ─────────────────────────────
def test_bridge_unreachable_refused():
    def _boom(amp, nonce):
        raise ConnectionError("bridge down")
    fr = _adapter(_boom).fire_fn(60, "n")
    assert fr.fired is False and fr.real_hardware is False and "failed" in fr.error


def test_malformed_response_refused():
    assert _adapter(lambda a, n: "not a dict").fire_fn(60, "n").fired is False
    assert _adapter(_resp({"t_fire_ns": None})).fire_fn(60, "n").fired is False   # missing feature


# ── no band-fill: no clean peak -> latency 0, MEASURED peak ────────────────────
def test_no_peak_zero_latency_measured_peak():
    a = _adapter(_resp({"latency_ms": None, "peak_lsb": 180.0, "t_fire_ns": 9}))
    a.fire_fn(60, "n")
    win = a.imu_capture_fn(9)
    assert win.latency_ms == 0.0 and win.peak_lsb == 180.0 and win.t_response_ns == 9


# ── gameplay LOW amplitude clamp ──────────────────────────────────────────────
def test_amplitude_clamped():
    assert _adapter(_resp_ok()).fire_fn(255, "n").amplitude == LOW_AMPLITUDE_FORCE_MAX


# ── source purity: the client never assigns the sealed presence bits ──────────
def test_client_never_assigns_presence_bits():
    src = _MOD.read_text(encoding="utf-8")
    hit = re.search(r"(presence_session_candidate_ok|effective_live|live_hardware)[\"'\]\s]*=(?!=)", src)
    assert hit is None, f"client assigns a sealed presence bit: {hit and hit.group(0)!r}"


# ── END-TO-END through the SEALED challenge_live ──────────────────────────────
def _live():
    session, seal = start_live_session(device_id="dev", player_label="P1", t_start_ns=1, process_nonce="pn")
    poll_bridge_activity(session, lambda: {"gameplay_context": "ACTIVE_GAMEPLAY"})
    return session, seal


def test_end_to_end_confirmed_bridge_fire_drives_live_verify():
    a = _adapter(_resp_ok(t=5000, latency=250.0, peak=3000.0))
    session, seal = _live()
    out = challenge_live(session, seal=seal, process_nonce="pn", nonce="c1", kind=ChallengeKind.GO,
                         fire_fn=a.fire_fn, imu_capture_fn=a.imu_capture_fn,
                         pcc_sample={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}, amplitude=60)
    assert out["issued"] is True
    ev = session.challenges[-1]
    assert ev.live_hardware is True and ev.go_verify_pass is True


def test_end_to_end_unconfirmed_fire_refused():
    a = _adapter(_resp({"real_hardware": False}))
    session, seal = _live()
    out = challenge_live(session, seal=seal, process_nonce="pn", nonce="c2", kind=ChallengeKind.GO,
                         fire_fn=a.fire_fn, imu_capture_fn=a.imu_capture_fn,
                         pcc_sample={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}, amplitude=60)
    assert out["issued"] is False and out["refused"] == "fire_failed"
    assert len(session.challenges) == 0
