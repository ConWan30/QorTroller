"""P-LIVE-0 — nonce-bound reflex capture + verify (A2A-POEP-P3P4, grok round-16 verdict).

The adversarial gate proved offline scoring of stored (latency, peak[, scalars]) CANNOT earn presence:
a scalar-matching macro samples the human joint and clears any offline model (A-SCALAR). grok's
verdict: presence is a PROTOCOL property, not a feature-richness property. The separatrix is a LIVE,
UNPREDICTABLE challenge time cryptographically bound to a FRESH nonce.

P-LIVE-0 (this module) is the smallest honest increment: the nonce-bound commitment + an offline
VERIFY auditor (not an ML 'presence model'). By construction it defeats:
  - A-REPLAY: a replayed response carries the OLD nonce -> commitment mismatch against the fresh one.
  - A-CONST / pre-scheduled macros: the challenge fires at a nonce-derived UNPREDICTABLE time, so a
    fixed-schedule response lands outside the [challenge_ts, challenge_ts + reaction_band] window.

Honest limits (NOT defeated by P-LIVE-0 alone, so poep_enabled STAYS False):
  - A REACTIVE bot (detects the live challenge onset, reacts within 80-300 ms) is not defeated by
    timing/binding alone -- that needs waveform shape + Stage-A. P-LIVE-0 raises the bar to 'must
    react to a live unpredictable stimulus', a much stronger claim than offline scoring, but not yet
    'embodied human'. Candidate tag; no FROZEN promotion; no flip.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

_DOMAIN = b"QORTROLLER-POEP-v0-CANDIDATE"
REACTION_BAND_MS = (80.0, 300.0)          # human sensorimotor reaction window (RBM-v0 band)


def response_feature_digest(latency_ms: float, peak_lsb: float, precursor_gap_ms: float) -> str:
    """Stable digest of the response's extracted scalars (what was measured, bound into the commitment)."""
    body = f"{round(latency_ms, 3)}|{round(peak_lsb, 1)}|{round(precursor_gap_ms, 3)}".encode()
    return hashlib.sha256(body).hexdigest()


def poep_commitment(*, device_id: str, nonce: str, feature_digest: str, ts_ns: int) -> str:
    """Candidate PoEP commitment binding the response to THIS challenge's nonce (grok P-LIVE-0 (3))."""
    body = _DOMAIN + b"|" + device_id.encode() + b"|" + nonce.encode() + b"|" + \
        feature_digest.encode() + b"|" + str(int(ts_ns)).encode()
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class LiveChallenge:
    device_id: str
    nonce: str                 # fresh per-challenge (unpredictable)
    t_challenge_ns: int        # when the stimulus fired (nonce-scheduled)


@dataclass(frozen=True)
class ChallengeResponse:
    t_response_ns: int
    latency_ms: float
    peak_lsb: float
    precursor_gap_ms: float
    nonce: str                 # the nonce the response claims to answer
    commitment: str            # SHA-256 the responder produced


def verify_live_response(ch: LiveChallenge, resp: ChallengeResponse) -> dict:
    """Offline auditor (NOT an ML model). Fail-closed. Returns {ok, reasons, commitment_ok}.

    Checks, in order (each independently defeats an attack class):
      1. nonce match          -- resp answers THIS challenge's fresh nonce (defeats A-REPLAY)
      2. temporal ordering    -- response strictly AFTER the challenge (defeats pre-recorded)
      3. reaction-band gate    -- latency within [80,300]ms of the challenge (defeats pre-scheduled A-CONST)
      4. IMU corroboration     -- peak above floor (defeats no-response)
      5. commitment integrity  -- recomputed commitment == claimed (binding is not forged)
    """
    reasons = []
    if resp.nonce != ch.nonce:
        reasons.append("nonce_mismatch (replay / stale challenge)")
    if resp.t_response_ns <= ch.t_challenge_ns:
        reasons.append("response_not_after_challenge (pre-recorded)")
    lo, hi = REACTION_BAND_MS
    obs_latency = (resp.t_response_ns - ch.t_challenge_ns) / 1e6
    if not (lo <= obs_latency <= hi):
        reasons.append(f"latency_out_of_reaction_band ({obs_latency:.0f}ms; pre-scheduled/too-slow)")
    if resp.peak_lsb < 1000.0:
        reasons.append("no_imu_corroboration (peak < floor)")
    fd = response_feature_digest(resp.latency_ms, resp.peak_lsb, resp.precursor_gap_ms)
    recomputed = poep_commitment(device_id=ch.device_id, nonce=ch.nonce,
                                 feature_digest=fd, ts_ns=resp.t_response_ns)
    commitment_ok = (recomputed == resp.commitment)
    if not commitment_ok:
        reasons.append("commitment_mismatch (binding forged)")
    return {"ok": len(reasons) == 0, "reasons": reasons, "commitment_ok": commitment_ok,
            "observed_latency_ms": obs_latency, "poep_enabled": False, "is_presence_verdict": False,
            "claim": "response causally bound to a live unpredictable nonce challenge (defeats "
                     "replay + pre-scheduled macro); NOT yet anti-reactive-bot (Stage-A/waveform gated)"}
