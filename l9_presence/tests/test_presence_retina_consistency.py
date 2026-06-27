"""Tests for the L9 x Trio-Retina presence-consistency fusion.

SCOPE HONESTY: these are SYNTHETIC fixtures. They prove the LATTICE LOGIC, the
BINDING fail-closure, the FAIL-OPEN posture, and the UNCALIBRATED honesty rail.
They do NOT prove the disagreement signal SEPARATES cheat from skill -- that
requires an adversarial capture (aim-assist / bot-in-loop / relay) and is
[UNVALIDATED]. No fixture here should ever be read as evidence of discrimination
power; they test that the instrument behaves as specified.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from l9_presence.presence_retina_consistency import (  # noqa: E402
    CALIBRATION_STATUS,
    ConsistencyVerdict,
    L4Signal,
    L4State,
    PresenceSignal,
    PresenceState,
    TrajectorySignal,
    TrajectoryState,
    assemble_consistency,
    check_binding,
    classify_presence,
    classify_trajectory,
)

_DEV = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
_RH = "7c01ef05630fe72e210ee2d43ccef7be2f90eddcbe4c09d6bcfa7fc145089c35"
_TS = 1_782_000_000_000_000_000


def _presence(state, ts=_TS, dev=_DEV):
    return PresenceSignal(device_id=dev, ts_ns=ts, state=state,
                          liveness_pass=(state is PresenceState.PRESENT),
                          device_auth_pass=(state is PresenceState.PRESENT), nonce="n")


def _traj(state, ts=_TS, dev=_DEV, anomaly=0):
    return TrajectorySignal(device_id=dev, record_hash=_RH, ts_ns=ts, state=state,
                            anomaly_count=anomaly, residual=0.1)


# ---- adapters ----------------------------------------------------------

def test_classify_presence_present():
    assert classify_presence({"verdict": "PRESENT"}) is PresenceState.PRESENT


def test_classify_presence_reject():
    assert classify_presence({"verdict": "REJECT"}) is PresenceState.REJECT


def test_classify_presence_calibration_incomplete_is_unknown():
    assert classify_presence({"status": "calibration_incomplete"}) is PresenceState.UNKNOWN


def test_classify_presence_none_and_garbage_are_unknown():
    assert classify_presence(None) is PresenceState.UNKNOWN
    assert classify_presence({}) is PresenceState.UNKNOWN
    assert classify_presence({"verdict": "WAT"}) is PresenceState.UNKNOWN


def test_classify_trajectory_states():
    assert classify_trajectory(enabled=True, buffer_filled=True, anomaly_count=0) is TrajectoryState.PLAUSIBLE
    assert classify_trajectory(enabled=True, buffer_filled=True, anomaly_count=3) is TrajectoryState.IMPLAUSIBLE
    # absence of a verdict is NOT an anomaly (rail #2)
    assert classify_trajectory(enabled=False, buffer_filled=True, anomaly_count=5) is TrajectoryState.UNKNOWN
    assert classify_trajectory(enabled=True, buffer_filled=False, anomaly_count=5) is TrajectoryState.UNKNOWN
    assert classify_trajectory(enabled=True, buffer_filled=True, anomaly_count=None) is TrajectoryState.UNKNOWN


# ---- binding (the security boundary) -----------------------------------

def test_binding_happy():
    b = check_binding(_presence(PresenceState.PRESENT), _traj(TrajectoryState.PLAUSIBLE))
    assert b.bound is True


def test_binding_device_mismatch():
    b = check_binding(_presence(PresenceState.PRESENT, dev="a" * 64),
                      _traj(TrajectoryState.PLAUSIBLE, dev="b" * 64))
    assert b.bound is False and "mismatch" in b.reason


def test_binding_missing_record_hash():
    t = TrajectorySignal(device_id=_DEV, record_hash="", ts_ns=_TS, state=TrajectoryState.PLAUSIBLE)
    assert check_binding(_presence(PresenceState.PRESENT), t).bound is False


def test_binding_outside_window():
    b = check_binding(_presence(PresenceState.PRESENT, ts=_TS),
                      _traj(TrajectoryState.PLAUSIBLE, ts=_TS + 10_000_000_000))  # +10s
    assert b.bound is False and "window" in b.reason


def test_binding_non_integer_ts():
    p = PresenceSignal(device_id=_DEV, ts_ns="oops", state=PresenceState.PRESENT)  # type: ignore[arg-type]
    assert check_binding(p, _traj(TrajectoryState.PLAUSIBLE)).bound is False


# ---- the consistency lattice -------------------------------------------

def test_consistent_human():
    r = assemble_consistency(_presence(PresenceState.PRESENT), _traj(TrajectoryState.PLAUSIBLE))
    assert r.verdict is ConsistencyVerdict.CONSISTENT_HUMAN
    assert r.security_flag is False and r.severity == "NONE"


def test_machine_assist_catch_present_but_implausible():
    """THE novel catch: a live human is present, continuous trajectory is not human."""
    r = assemble_consistency(_presence(PresenceState.PRESENT),
                             _traj(TrajectoryState.IMPLAUSIBLE, anomaly=4))
    assert r.verdict is ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY
    assert r.security_flag is True and r.severity == "HIGH"


def test_replay_or_unexercised_trajectory_without_presence():
    r = assemble_consistency(_presence(PresenceState.REJECT), _traj(TrajectoryState.PLAUSIBLE))
    assert r.verdict is ConsistencyVerdict.INCONSISTENT_AUTHENTIC_TRAJECTORY_WITHOUT_PRESENCE
    assert r.security_flag is True and r.severity == "MEDIUM"


def test_consistent_inactive():
    r = assemble_consistency(_presence(PresenceState.REJECT), _traj(TrajectoryState.IMPLAUSIBLE, anomaly=2))
    assert r.verdict is ConsistencyVerdict.CONSISTENT_INACTIVE
    assert r.security_flag is False


def test_l4_2v1_split_flips_consistent_human():
    """presence+trajectory say human, but the optional L4 oracle disagrees."""
    r = assemble_consistency(_presence(PresenceState.PRESENT), _traj(TrajectoryState.PLAUSIBLE),
                             L4Signal(state=L4State.ANOMALOUS, distance=9.9))
    assert r.verdict is ConsistencyVerdict.INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY
    assert r.security_flag is True


def test_single_oracle_is_indeterminate():
    assert assemble_consistency(_presence(PresenceState.PRESENT),
                                _traj(TrajectoryState.UNKNOWN)).verdict is ConsistencyVerdict.INDETERMINATE
    assert assemble_consistency(_presence(PresenceState.UNKNOWN),
                                _traj(TrajectoryState.PLAUSIBLE)).verdict is ConsistencyVerdict.INDETERMINATE


def test_no_signal_is_unverifiable():
    r = assemble_consistency(_presence(PresenceState.UNKNOWN), _traj(TrajectoryState.UNKNOWN))
    assert r.verdict is ConsistencyVerdict.UNVERIFIABLE


# ---- fail-open: binding overrides accusation (rail #2 + #4) -------------

def test_unbound_never_accuses_even_when_states_would_be_inconsistent():
    """The strongest rail: a PRESENT + IMPLAUSIBLE pair WOULD be the HIGH security
    catch -- but if the two oracles are not bound (different devices), the result
    MUST be UNVERIFIABLE with security_flag False. A desynchronised signal can
    never accuse (this is what defeats the relay-via-desync attack)."""
    r = assemble_consistency(_presence(PresenceState.PRESENT, dev="a" * 64),
                             _traj(TrajectoryState.IMPLAUSIBLE, dev="b" * 64, anomaly=9))
    assert r.verdict is ConsistencyVerdict.UNVERIFIABLE
    assert r.security_flag is False


def test_outside_window_never_accuses():
    r = assemble_consistency(_presence(PresenceState.PRESENT, ts=_TS),
                             _traj(TrajectoryState.IMPLAUSIBLE, ts=_TS + 10_000_000_000, anomaly=9))
    assert r.verdict is ConsistencyVerdict.UNVERIFIABLE and r.security_flag is False


# ---- honesty rail #3: never claims a calibrated score -------------------

def test_calibration_status_always_uncalibrated():
    for p in (PresenceState.PRESENT, PresenceState.REJECT, PresenceState.UNKNOWN):
        for t in (TrajectoryState.PLAUSIBLE, TrajectoryState.IMPLAUSIBLE, TrajectoryState.UNKNOWN):
            r = assemble_consistency(_presence(p), _traj(t))
            assert r.calibration_status == CALIBRATION_STATUS == "UNCALIBRATED_SYNTHETIC"
            # the result dict carries NO probability/confidence field
            d = r.to_dict()
            assert "confidence" not in d and "probability" not in d and "score" not in d


def test_to_dict_round_trip_shape():
    d = assemble_consistency(_presence(PresenceState.PRESENT), _traj(TrajectoryState.IMPLAUSIBLE, anomaly=1)).to_dict()
    assert d["verdict"] == "INCONSISTENT_PRESENCE_WITHOUT_AUTHENTIC_TRAJECTORY"
    assert d["security_flag"] is True
    assert d["binding"]["bound"] is True
    assert d["evidence"]["record_hash"] == _RH
