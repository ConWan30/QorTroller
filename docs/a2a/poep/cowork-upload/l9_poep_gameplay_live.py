"""L1+L2 live dual-connect PoEP challenge path (arc poep-gameplay-live).

Design: docs/a2a/poep/poep-gameplay-live-design.md sections 5-7.
Does NOT edit poep_gameplay_session.py (round-04/05 PASS honesty model) — composition only.

Topology: PS5/console <-BT- Edge -USB-> PC (bridge UP; USB challenge+IMU; BT play).
Live seal is local bookkeeping (not FROZEN-v1). poep_enabled stays False.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from l9_presence.poep_catch_trials import score_trial as _score_trial
from l9_presence.poep_gameplay_session import (
    ActivityState,
    ChallengeKind,
    LOW_AMPLITUDE_FORCE_DEFAULT,
    LOW_AMPLITUDE_FORCE_MAX,
    PlaySession,
    SessionChallengeEvent,
    TRUSTED_ACTIVITY_SOURCE,
    summarize_session,
)
from l9_presence.poep_live_verify import (
    ChallengeResponse,
    LiveChallenge,
    poep_commitment,
    response_feature_digest,
    verify_live_response,
)

_LIVE_SEAL_DOMAIN = b"QORTROLLER-POEP-GAMEPLAY-LIVESEAL-v0-CANDIDATE"
DEFAULT_ACTIVITY_POLL_HZ = 1.0
_PCC_OK_CAPTURE = frozenset({"NOMINAL"})
_PCC_OK_HOST = frozenset({"EXCLUSIVE_USB", "UNKNOWN"})
LIVE_FIRE_ENV = "POEP_LIVE_FIRE_ENABLED"

BridgeActivityFetcher = Callable[[], Optional[dict]]
FireFn = Callable[[int, str], "FireResult"]
ImuCaptureFn = Callable[[int], Optional["ImuWindow"]]
CatchScoreFn = Callable[[Optional["ImuWindow"]], dict]


def compute_live_seal(
    session_id: str, device_id: str, t_start_ns: int, process_nonce: str
) -> str:
    if not (session_id and device_id and process_nonce):
        raise ValueError("session_id, device_id, process_nonce required")
    body = (
        _LIVE_SEAL_DOMAIN
        + b"|"
        + session_id.encode()
        + b"|"
        + device_id.encode()
        + b"|"
        + str(int(t_start_ns)).encode()
        + b"|"
        + process_nonce.encode()
    )
    return hashlib.sha256(body).hexdigest()


def verify_live_seal(session: PlaySession, seal: str, process_nonce: str) -> bool:
    if not seal or not process_nonce:
        return False
    try:
        expect = compute_live_seal(
            session.session_id, session.device_id, session.t_start_ns, process_nonce
        )
    except (ValueError, AttributeError, TypeError):
        return False
    return expect == seal


def start_live_session(
    *,
    device_id: str,
    player_label: str,
    t_start_ns: int,
    process_nonce: str,
    session_id: Optional[str] = None,
) -> tuple[PlaySession, str]:
    """Only path that mints mode=live + activity_source=bridge + seal at birth."""
    sid = session_id or hashlib.sha256(
        f"{player_label}|{device_id}|{int(t_start_ns)}".encode()
    ).hexdigest()[:16]
    session = PlaySession(
        session_id=sid,
        device_id=device_id,
        player_label=player_label,
        t_start_ns=int(t_start_ns),
        mode="live",
        activity_source=TRUSTED_ACTIVITY_SOURCE,
    )
    seal = compute_live_seal(sid, device_id, int(t_start_ns), process_nonce)
    return session, seal


def poll_bridge_activity(
    session: PlaySession, fetcher: BridgeActivityFetcher
) -> ActivityState:
    sample = None
    try:
        sample = fetcher()
    except Exception:
        sample = None
    if not isinstance(sample, dict):
        return session.record_activity({})
    return session.record_activity(sample)


def pcc_allows_challenge(sample: Optional[dict]) -> bool:
    if not isinstance(sample, dict):
        return False
    cap = str(sample.get("capture_state", "")).upper()
    host = str(sample.get("host_state", "")).upper()
    return cap in _PCC_OK_CAPTURE and host in _PCC_OK_HOST


@dataclass(frozen=True)
class FireResult:
    fired: bool
    real_hardware: bool
    t_fire_ns: int
    amplitude: int
    error: str = ""


@dataclass(frozen=True)
class ImuWindow:
    t_response_ns: int
    latency_ms: float
    peak_lsb: float
    precursor_gap_ms: float


def clamp_amplitude(requested: int) -> int:
    if requested <= 0:
        return LOW_AMPLITUDE_FORCE_DEFAULT
    return min(int(requested), LOW_AMPLITUDE_FORCE_MAX)


def default_catch_scorer(window: Optional[ImuWindow]) -> dict:
    peak = float(window.peak_lsb) if window is not None else 0.0
    lat = float(window.latency_ms) if window is not None else None
    sc = _score_trial(
        "NO_GO",
        peak_lsb=peak,
        latency_ms=lat,
        live_verify_ok=False,
    )
    return {
        "kind": sc.kind,
        "peak_lsb": sc.peak_lsb,
        "latency_ms": sc.latency_ms,
        "human_ok": sc.human_ok,
        "reason": sc.reason,
        "always_fire_caught": sc.always_fire_caught,
    }


def challenge_live(
    session: PlaySession,
    *,
    seal: str,
    process_nonce: str,
    nonce: str,
    kind: ChallengeKind,
    fire_fn: FireFn,
    imu_capture_fn: ImuCaptureFn,
    pcc_sample: Optional[dict],
    amplitude: int = LOW_AMPLITUDE_FORCE_DEFAULT,
    catch_score_fn: CatchScoreFn = default_catch_scorer,
) -> dict:
    """GO fires low-amp force; NO_GO never writes force. Refuse seal/activity/PCC fail-closed."""
    if not verify_live_seal(session, seal, process_nonce):
        return {"issued": False, "refused": "refused_seal"}
    last = session.activity_samples[-1] if session.activity_samples else ActivityState.UNKNOWN
    if last is not ActivityState.ACTIVE_GAMEPLAY:
        return {
            "issued": False,
            "refused": "refused_activity",
            "activity": last.value,
        }
    if not pcc_allows_challenge(pcc_sample):
        return {"issued": False, "refused": "refused_pcc"}

    amp = clamp_amplitude(amplitude)

    if kind == ChallengeKind.NO_GO:
        window = imu_capture_fn(0) if imu_capture_fn else None
        catch = catch_score_fn(window)
        ts = _now_from(session)
        ev = SessionChallengeEvent(
            kind=ChallengeKind.NO_GO,
            ts_ns=ts,
            nonce=nonce,
            verify={"ok": False, "no_go": True, "poep_enabled": False},
            catch=catch,
            amplitude_force=0,
            live_hardware=False,
        )
        session.record_challenge(ev)
        return {
            "issued": True,
            "kind": "NO_GO",
            "catch": catch,
            "amplitude_force": 0,
        }

    fire = fire_fn(amp, nonce)
    if not fire.fired:
        return {
            "issued": False,
            "refused": "fire_failed",
            "error": fire.error,
        }
    window = imu_capture_fn(fire.t_fire_ns)
    ch = LiveChallenge(
        device_id=session.device_id, nonce=nonce, t_challenge_ns=fire.t_fire_ns
    )
    if window is None:
        verify: dict[str, Any] = {
            "ok": False,
            "reasons": ["no_imu_window (no response captured)"],
            "poep_enabled": False,
            "is_presence_verdict": False,
        }
    else:
        fd = response_feature_digest(
            window.latency_ms, window.peak_lsb, window.precursor_gap_ms
        )
        resp = ChallengeResponse(
            t_response_ns=window.t_response_ns,
            latency_ms=window.latency_ms,
            peak_lsb=window.peak_lsb,
            precursor_gap_ms=window.precursor_gap_ms,
            nonce=nonce,
            commitment=poep_commitment(
                device_id=session.device_id,
                nonce=nonce,
                feature_digest=fd,
                ts_ns=window.t_response_ns,
            ),
        )
        verify = verify_live_response(ch, resp)
    ev = SessionChallengeEvent(
        kind=ChallengeKind.GO,
        ts_ns=fire.t_fire_ns,
        nonce=nonce,
        verify=verify,
        amplitude_force=fire.amplitude,
        live_hardware=bool(fire.real_hardware),
    )
    session.record_challenge(ev)
    return {
        "issued": True,
        "kind": "GO",
        "verify_ok": bool(verify.get("ok")),
        "amplitude_force": fire.amplitude,
        "live_hardware": ev.live_hardware,
    }


def _now_from(session: PlaySession) -> int:
    last_ts = max([session.t_start_ns] + [c.ts_ns for c in session.challenges])
    return last_ts + 1


def summarize_live_session(
    session: PlaySession, *, seal: str, process_nonce: str
) -> dict:
    summary = summarize_session(session)
    seal_valid = verify_live_seal(session, seal, process_nonce)
    summary["live_seal_valid"] = seal_valid
    if summary.get("presence_session_candidate_ok") and not seal_valid:
        summary["presence_session_candidate_ok"] = False
        summary["candidate_refused_reason"] = (
            "live_seal_invalid (state not born via start-live)"
        )
    summary["poep_enabled"] = False
    summary["is_presence_verdict"] = False
    return summary


def real_hid_fire_available() -> bool:
    return os.environ.get(LIVE_FIRE_ENV, "") == "1"


def make_real_hid_fire() -> FireFn:
    if not real_hid_fire_available():
        raise RuntimeError(
            f"real HID fire gated: set {LIVE_FIRE_ENV}=1 on the operator rig (never CI)"
        )

    def _fire(amplitude: int, nonce: str) -> FireResult:
        amp = clamp_amplitude(amplitude)
        try:
            from bridge.controller.l6_trigger_driver import L6TriggerDriver  # noqa: F401
        except ImportError as e:
            return FireResult(
                fired=False,
                real_hardware=False,
                t_fire_ns=0,
                amplitude=amp,
                error=f"l6_trigger_driver unavailable: {e!r}",
            )
        # L3 rig: concrete DualSense write + exclusive USB ownership (document dual-writer risk).
        return FireResult(
            fired=False,
            real_hardware=False,
            t_fire_ns=0,
            amplitude=amp,
            error="real fire wiring is L3 rig work; not executable without operator pad path",
        )

    return _fire
