"""Adapt a LabeledWindow -> (PresenceSignal, TrajectorySignal, L4Signal) and run
the real fusion engine. Also provides the two STANDALONE-oracle baselines used for
the contextual-lift comparison (retina-alone, presence-alone).

Binding is by ``session_id`` -> a synthetic ``record_hash`` (sha256) with both
signals stamped at the same ts, so ``check_binding`` passes by construction. This
is the experiment-only binding the operator chose; production record_hash binding
is out of scope (see plan).
"""
from __future__ import annotations

import hashlib

from l9_presence.presence_retina_consistency import (
    L4Signal,
    L4State,
    PresenceSignal,
    PresenceState,
    TrajectorySignal,
    TrajectoryState,
    assemble_consistency,
    classify_presence,
    classify_trajectory,
)

from .session_class import LabeledWindow
from .synthetic_sessions import L4_ANOMALY, L4_CONTINUITY


def _record_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _l4_state(distance) -> L4State:
    if distance is None:
        return L4State.UNKNOWN
    if distance >= L4_ANOMALY:
        return L4State.ANOMALOUS
    if distance < L4_CONTINUITY:
        return L4State.NOMINAL
    return L4State.UNKNOWN  # between thresholds = no clear call


def window_to_signals(w: LabeledWindow):
    """Convert a window to the three typed signals using the REAL engine adapters."""
    rh = _record_hash(w.session_id)

    if not w.presence_challenged:
        poep_result = None  # no challenge bound to this window -> classify_presence -> UNKNOWN
    else:
        verdict = "PRESENT" if (w.presence_reacted and w.presence_in_band and w.device_auth_pass) else "REJECT"
        poep_result = {"verdict": verdict}
    presence = PresenceSignal(
        device_id=w.session_id, ts_ns=w.ts_ns, state=classify_presence(poep_result),
        liveness_pass=(w.presence_reacted and w.presence_in_band) if w.presence_challenged else None,
        device_auth_pass=w.device_auth_pass if w.presence_challenged else None,
    )

    trajectory = TrajectorySignal(
        device_id=w.session_id, record_hash=rh, ts_ns=w.ts_ns,
        state=classify_trajectory(enabled=True, buffer_filled=True,
                                  anomaly_count=w.retina_anomaly_count),
        anomaly_count=w.retina_anomaly_count,
    )

    l4 = L4Signal(state=_l4_state(w.l4_distance), distance=w.l4_distance)
    return presence, trajectory, l4


def evaluate_window(w: LabeledWindow):
    """Run the fusion engine on a window. Returns a ConsistencyResult."""
    presence, trajectory, l4 = window_to_signals(w)
    return assemble_consistency(presence, trajectory, l4)


# --- standalone-oracle baselines (for the contextual-lift comparison) ----------

def retina_alone_security(w: LabeledWindow) -> bool:
    """What retina-alone (no presence context) would accuse: any IMPLAUSIBLE window.
    Cannot distinguish human+assist from bot, nor frame relay/replay."""
    _, trajectory, _ = window_to_signals(w)
    return trajectory.state is TrajectoryState.IMPLAUSIBLE


def presence_alone_security(w: LabeledWindow) -> bool:
    """What presence-alone would accuse: any non-PRESENT window. Catches no-human,
    but MISSES aim-assist and pro-skill (both PRESENT)."""
    presence, _, _ = window_to_signals(w)
    return presence.state is not PresenceState.PRESENT
