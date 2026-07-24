"""L1+L2 live dual-connect tests (design section 8 bars)."""
from __future__ import annotations

import secrets
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from l9_presence.poep_gameplay_live import (
    FireResult,
    ImuWindow,
    challenge_live,
    clamp_amplitude,
    compute_live_seal,
    pcc_allows_challenge,
    poll_bridge_activity,
    start_live_session,
    summarize_live_session,
    verify_live_seal,
)
from l9_presence.poep_gameplay_session import (
    ActivityState,
    ChallengeKind,
    PlaySession,
    SessionChallengeEvent,
    summarize_session,
)


def _live_go_event(session, *, real=True, ok=True, ts=None):
    ts = ts or session.t_start_ns + 10
    return SessionChallengeEvent(
        kind=ChallengeKind.GO,
        ts_ns=ts,
        nonce=secrets.token_hex(4),
        verify={"ok": ok, "poep_enabled": False},
        amplitude_force=60,
        live_hardware=real,
    )


def test_l1_seal_roundtrip():
    nonce = secrets.token_hex(8)
    s, seal = start_live_session(
        device_id="dev1", player_label="P1", t_start_ns=100, process_nonce=nonce
    )
    assert s.mode == "live"
    assert s.activity_source == "bridge"
    assert verify_live_seal(s, seal, nonce)
    assert not verify_live_seal(s, seal, "wrong")
    assert not verify_live_seal(s, "00" * 32, nonce)


def test_l1_dry_cannot_candidate():
    dry = PlaySession(
        session_id="d1",
        device_id="dev",
        player_label="P1",
        t_start_ns=1,
        mode="dry",
        activity_source="cli_inject",
    )
    for _ in range(3):
        dry.record_activity({"gameplay_context": "ACTIVE_GAMEPLAY"})
    dry.record_challenge(_live_go_event(dry, real=False, ts=2))
    dry.record_challenge(_live_go_event(dry, real=False, ts=3))
    sm = summarize_session(dry)
    assert sm["dry_plumbing_ok"] is True
    assert sm["presence_session_candidate_ok"] is False


def test_l1_menu_poll_unknown_on_fetch_fail():
    s, seal = start_live_session(
        device_id="d", player_label="P1", t_start_ns=1, process_nonce="n"
    )
    st = poll_bridge_activity(s, lambda: None)
    assert st == ActivityState.UNKNOWN


def test_l1_pcc_gate():
    assert pcc_allows_challenge(
        {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}
    )
    assert not pcc_allows_challenge(
        {"capture_state": "CONTESTED", "host_state": "EXCLUSIVE_USB"}
    )
    assert not pcc_allows_challenge(None)


def test_l2_amplitude_clamp_255():
    assert clamp_amplitude(255) == 80
    assert clamp_amplitude(60) == 60
    assert clamp_amplitude(0) == 60


def test_l2_refuse_seal_activity_pcc():
    s, seal = start_live_session(
        device_id="d", player_label="P1", t_start_ns=1, process_nonce="nonce1"
    )
    fire = lambda a, n: FireResult(True, True, 99, a)
    imu = lambda t: ImuWindow(t + 1, 250.0, 2000.0, 5.0)
    pcc = {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}
    # bad seal
    r = challenge_live(
        s,
        seal="deadbeef",
        process_nonce="nonce1",
        nonce="n",
        kind=ChallengeKind.GO,
        fire_fn=fire,
        imu_capture_fn=imu,
        pcc_sample=pcc,
    )
    assert r["refused"] == "refused_seal"
    # good seal, no activity
    r = challenge_live(
        s,
        seal=seal,
        process_nonce="nonce1",
        nonce="n",
        kind=ChallengeKind.GO,
        fire_fn=fire,
        imu_capture_fn=imu,
        pcc_sample=pcc,
    )
    assert r["refused"] == "refused_activity"
    s.record_activity({"gameplay_context": "ACTIVE_GAMEPLAY"})
    r = challenge_live(
        s,
        seal=seal,
        process_nonce="nonce1",
        nonce="n",
        kind=ChallengeKind.GO,
        fire_fn=fire,
        imu_capture_fn=imu,
        pcc_sample={"capture_state": "CONTESTED", "host_state": "EXCLUSIVE_USB"},
    )
    assert r["refused"] == "refused_pcc"


def test_l2_nogo_never_fires():
    s, seal = start_live_session(
        device_id="d", player_label="P1", t_start_ns=1, process_nonce="n1"
    )
    s.record_activity({"gameplay_context": "ACTIVE_GAMEPLAY"})
    fired = []

    def fire(a, n):
        fired.append(1)
        return FireResult(True, True, 50, a)

    r = challenge_live(
        s,
        seal=seal,
        process_nonce="n1",
        nonce="x",
        kind=ChallengeKind.NO_GO,
        fire_fn=fire,
        imu_capture_fn=lambda t: ImuWindow(1, 0.0, 40.0, 0.0),
        pcc_sample={"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"},
    )
    assert r["issued"] and r["kind"] == "NO_GO"
    assert fired == []


def test_l2_go_mock_not_candidate():
    """Mock real_hardware=False cannot mint presence candidate."""
    s, seal = start_live_session(
        device_id="d", player_label="P1", t_start_ns=1, process_nonce="n1"
    )
    for _ in range(4):
        s.record_activity({"gameplay_context": "ACTIVE_GAMEPLAY"})
    pcc = {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}

    def fire(a, n):
        return FireResult(True, False, s.t_start_ns + 100, a)

    def imu(t):
        return ImuWindow(t + int(250e6), 250.0, 2500.0, 5.0)

    for i in range(2):
        r = challenge_live(
            s,
            seal=seal,
            process_nonce="n1",
            nonce=f"g{i}",
            kind=ChallengeKind.GO,
            fire_fn=fire,
            imu_capture_fn=imu,
            pcc_sample=pcc,
        )
        assert r["issued"]
        assert r["live_hardware"] is False
    sm = summarize_live_session(s, seal=seal, process_nonce="n1")
    assert sm["live_seal_valid"] is True
    assert sm["presence_session_candidate_ok"] is False  # mock fire
    assert sm["poep_enabled"] is False


def test_l2_go_live_double_can_candidate():
    """Test double with real_hardware=True + seal + bridge activity can mint candidate."""
    s, seal = start_live_session(
        device_id="d", player_label="P1", t_start_ns=1, process_nonce="n1"
    )
    for _ in range(4):
        s.record_activity({"gameplay_context": "ACTIVE_GAMEPLAY"})
    pcc = {"capture_state": "NOMINAL", "host_state": "EXCLUSIVE_USB"}
    tbase = [s.t_start_ns + 1000]

    def fire(a, n):
        tbase[0] += 10_000_000
        return FireResult(True, True, tbase[0], a)

    def imu(t):
        return ImuWindow(t + int(250e6), 250.0, 2500.0, 5.0)

    for i in range(2):
        r = challenge_live(
            s,
            seal=seal,
            process_nonce="n1",
            nonce=f"L{i}",
            kind=ChallengeKind.GO,
            fire_fn=fire,
            imu_capture_fn=imu,
            pcc_sample=pcc,
        )
        assert r["issued"] and r["live_hardware"] is True
        assert r.get("verify_ok") is True
    sm = summarize_live_session(s, seal=seal, process_nonce="n1")
    assert sm["presence_session_candidate_ok"] is True
    assert sm["is_presence_verdict"] is False
    assert sm["poep_enabled"] is False


def test_l2_bad_seal_kills_candidate():
    s, seal = start_live_session(
        device_id="d", player_label="P1", t_start_ns=1, process_nonce="n1"
    )
    for _ in range(4):
        s.record_activity({"gameplay_context": "ACTIVE_GAMEPLAY"})
    s.record_challenge(_live_go_event(s, real=True, ts=10))
    s.record_challenge(_live_go_event(s, real=True, ts=20))
    sm = summarize_live_session(s, seal="00" * 32, process_nonce="n1")
    assert sm["presence_session_candidate_ok"] is False
    assert sm.get("candidate_refused_reason")
