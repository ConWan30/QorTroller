"""EdgeReflexAdapter tests - make grok r02 break-test + FIX list MECHANICAL (injected fakes only, no rig).

Covers: dual-open refuse, one-shot stash, no-clean-peak honest fail (never band-filled), no-write ->
real_hardware=False, amplitude clamp, env-gated factory, and END-TO-END through the SEALED challenge_live
(the fused-behind-split adapter really drives the real fire path). The real HID path is # pragma no cover.
"""
import re
from pathlib import Path

import pytest

from l9_presence.poep_gameplay_live import (
    LIVE_FIRE_ENV,
    ImuWindow,
    challenge_live,
    poll_bridge_activity,
    start_live_session,
)
from l9_presence.poep_gameplay_session import ChallengeKind, LOW_AMPLITUDE_FORCE_MAX
from l9_presence.poep_rig_reflex_adapter import (
    EdgeReflexAdapter,
    make_edge_reflex_adapter,
)

_MOD = Path(__file__).resolve().parents[1] / "poep_rig_reflex_adapter.py"


# ── fake injected hardware deps (no rig) ──────────────────────────────────────
def _probe_ok(t_challenge=1_000_000):
    """fire_probe that 'fires' successfully and hands an opaque payload to analyze."""
    def _fp(amp, nonce, delay_s):
        return t_challenge, {"amp": amp, "nonce": nonce}
    return _fp


def _probe_raises(exc=RuntimeError("driver missing")):
    def _fp(amp, nonce, delay_s):
        raise exc
    return _fp


def _analyze_pass(payload):      # clean reflex -> in-band latency
    return 250.0, 3000.0, 5.0


def _analyze_no_peak(payload):   # honest no-response: no clean peak -> latency None, MEASURED low peak
    return None, 180.0, None


def _analyze_raises(payload):
    raise ValueError("scoring failed")


def _adapter(*, probe=None, analyze=_analyze_pass, bridge=lambda: False, t_challenge=1_000_000):
    return EdgeReflexAdapter(
        fire_probe=probe or _probe_ok(t_challenge), analyze=analyze,
        bridge_running=bridge, delay_fn=lambda: 0.0,
    )


# ── FIX #1: refuse to fire while the bridge holds the pad (no dual-open) ───────
def test_dual_open_refused_when_bridge_running():
    a = _adapter(bridge=lambda: True)
    fr = a.fire_fn(60, "n")
    assert fr.fired is False and fr.real_hardware is False
    assert "bridge_running_dual_writer" in fr.error
    assert a.imu_capture_fn(1_000_000) is None   # nothing stashed


# ── FIX #3: any abort pre/at write -> fired=False, real_hardware=False ─────────
def test_no_write_means_not_real_hardware():
    a = _adapter(probe=_probe_raises())
    fr = a.fire_fn(60, "n")
    assert fr.fired is False and fr.real_hardware is False
    assert "aborted pre/at write" in fr.error


# ── successful fire -> real_hardware=True + one-shot stashed window ────────────
def test_successful_fire_is_real_hardware_and_stashes():
    a = _adapter(t_challenge=42)
    fr = a.fire_fn(60, "n")
    assert fr.fired is True and fr.real_hardware is True and fr.t_fire_ns == 42
    win = a.imu_capture_fn(42)
    assert isinstance(win, ImuWindow) and win.latency_ms == 250.0 and win.peak_lsb == 3000.0


# ── FIX #2: one-shot stash - second read (replay) -> None ─────────────────────
def test_one_shot_stash_no_replay():
    a = _adapter(t_challenge=7)
    a.fire_fn(60, "n")
    assert a.imu_capture_fn(7) is not None
    assert a.imu_capture_fn(7) is None            # consumed
    assert a.imu_capture_fn(0) is None            # NO_GO's imu_capture_fn(0) never returns a GO window


# ── FIX #4: no clean peak -> latency 0, MEASURED peak, NEVER band-filled ───────
def test_no_peak_is_zero_latency_measured_peak_not_bandfilled():
    a = _adapter(analyze=_analyze_no_peak, t_challenge=9)
    fr = a.fire_fn(60, "n")
    assert fr.real_hardware is True               # a real force still fired
    win = a.imu_capture_fn(9)
    assert win.latency_ms == 0.0                  # not clamped into the human band
    assert win.peak_lsb == 180.0                  # measured, not zeroed
    assert win.t_response_ns == 9                 # t_fire + 0


# ── analyze failure after a real write -> real_hardware=True, NO window ────────
def test_analyze_failure_keeps_real_hardware_but_no_window():
    a = _adapter(analyze=_analyze_raises, t_challenge=11)
    fr = a.fire_fn(60, "n")
    assert fr.fired is True and fr.real_hardware is True
    assert "analyze failed" in fr.error
    assert a.imu_capture_fn(11) is None           # no fabricated window


# ── FIX #5: gameplay LOW amplitude - never desk 255 ───────────────────────────
def test_amplitude_clamped_to_gameplay_band():
    a = _adapter()
    assert a.fire_fn(255, "n").amplitude == LOW_AMPLITUDE_FORCE_MAX   # 80, not 255
    a2 = _adapter()
    assert a2.fire_fn(60, "n").amplitude == 60


# ── FIX #7: factory gated on POEP_LIVE_FIRE_ENABLED=1 (raise before any HID import)
def test_factory_env_gated(monkeypatch):
    monkeypatch.delenv(LIVE_FIRE_ENV, raising=False)
    with pytest.raises(RuntimeError, match="real fire gated"):
        make_edge_reflex_adapter(device_id="x")


# ── FIX #12: the adapter never assigns the sealed presence bits (source purity) ─
def test_adapter_never_assigns_presence_bits():
    src = _MOD.read_text(encoding="utf-8")
    hit = re.search(r"(presence_session_candidate_ok|effective_live|live_hardware)[\"'\]\s]*=(?!=)", src)
    assert hit is None, f"adapter assigns a sealed presence bit: {hit and hit.group(0)!r}"


# ── END-TO-END through the SEALED challenge_live: pass reflex -> live GO verify ─
def _live_session():
    session, seal = start_live_session(
        device_id="dev", player_label="P1", t_start_ns=1_000, process_nonce="pn")
    poll_bridge_activity(session, lambda: {"gameplay_context": "ACTIVE_GAMEPLAY"})
    return session, seal


def _pcc_ok():
    return {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}


def test_end_to_end_challenge_live_records_live_hardware_and_verify():
    a = _adapter(analyze=_analyze_pass, t_challenge=5_000)
    session, seal = _live_session()
    out = challenge_live(
        session, seal=seal, process_nonce="pn", nonce="c1", kind=ChallengeKind.GO,
        fire_fn=a.fire_fn, imu_capture_fn=a.imu_capture_fn, pcc_sample=_pcc_ok(), amplitude=60)
    assert out["issued"] is True and out["kind"] == "GO"
    ev = session.challenges[-1]
    assert ev.live_hardware is True          # a real force fired (adapter set real_hardware)
    assert ev.go_verify_pass is True         # sealed verify passed on the in-band reflex


def test_end_to_end_no_peak_fires_but_verify_fails_honestly():
    a = _adapter(analyze=_analyze_no_peak, t_challenge=6_000)
    session, seal = _live_session()
    out = challenge_live(
        session, seal=seal, process_nonce="pn", nonce="c2", kind=ChallengeKind.GO,
        fire_fn=a.fire_fn, imu_capture_fn=a.imu_capture_fn, pcc_sample=_pcc_ok(), amplitude=60)
    ev = session.challenges[-1]
    assert ev.live_hardware is True          # the force fired
    assert ev.go_verify_pass is False        # but no clean reflex -> honest fail (no fabricated pass)


def test_end_to_end_bridge_running_refuses_fire():
    a = _adapter(bridge=lambda: True)
    session, seal = _live_session()
    out = challenge_live(
        session, seal=seal, process_nonce="pn", nonce="c3", kind=ChallengeKind.GO,
        fire_fn=a.fire_fn, imu_capture_fn=a.imu_capture_fn, pcc_sample=_pcc_ok(), amplitude=60)
    assert out["issued"] is False and out["refused"] == "fire_failed"
    assert len(session.challenges) == 0      # nothing recorded
