"""NQPV offline humanity adapter (cycle-35): hw_* 1000 Hz session -> human-positive NqpvCorpusRecord.

Turns the validated real N=10 1000 Hz biometric corpus (sessions/human/hw_nqpv_*.json) into
human-positive corpus records the RETINA-EXCL-2 harness consumes — the bridge between the captured
1000 Hz corpus and a study run with REAL human data (vs the synthetic humans in the cycle-31 demo).

WHY OFFLINE: the spectral biometric features (accel_magnitude_spectral_entropy, tremor FFT) require
1000 Hz; the live bridge polls ~120 Hz so they are degenerate there (see
project_dualconnection_capture_blind_finding). This module replays the canonical
``BiometricFeatureExtractor`` over 1000 Hz reports, computes the L4 Mahalanobis verdict, and emits the
record. It NEVER runs in the live loop.

p_L4 RE-ANCHOR — STUDY-ONLY (the load-bearing discipline from the cycle-35 scope note): the LIVE bridge
formula ``_p_l4 = exp(-(d-2))`` (dualshock_integration.py) under-scores real human distances (corpus
mean d~2.45 -> p_L4~0.05) because its anchor (2.0) is far tighter than the measured L4 NOMINAL scale
(anomaly threshold 5.579 = mean+3sigma). This module uses a RE-ANCHORED p_L4 (``0.5 ** (d/threshold)``
so d==threshold -> 0.5, d~2.45 -> ~0.74) computed against the measured profile. It lives ONLY here — it
does NOT edit the hard-rule-gated live formula (a separate deferred decision). ``p_l4_fn`` is injectable
so the eventual live-formula decision can adopt a validated anchor.

HONESTY: the corpus is ONE human (the operator) at N=10 ("low confidence", target N>=50) -> this measures
human-TAR for one human, NOT a population/tournament claim. The L4 oracle is the only biometric computed
offline here; cco/poep/coupled-retina ABSTAIN (None) -> the harness lands in the regime it already proved
needs the presence oracles. Value: a REAL human-positive substrate + the p_L4 anchor validated on real
data + the pipeline proven end-to-end. No FROZEN-v1 / 228B PoAC / chain / live-loop touch.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Callable, Optional

import numpy as np

from vapi_bridge.nqpv_corpus_loader import LABEL_HUMAN, NqpvCorpusRecord

# N=10 profile mean+3sigma of per-session L4 Mahalanobis distance (calibration_profile.json).
DEFAULT_ANOMALY_THRESHOLD: float = 5.579
# Variance floor so a structurally-zero feature (e.g. touchpad in gameplay) can't explode the distance
# via division by ~0. Matches the spirit of the extractor's accel-entropy variance guard.
_VAR_FLOOR: float = 1e-3

_CONTROLLER_DIR = Path(__file__).resolve().parents[2] / "controller"


def _load_controller():
    """Import the canonical extractor from controller/ (sys.path pattern per dualshock_integration)."""
    if str(_CONTROLLER_DIR) not in sys.path:
        sys.path.insert(0, str(_CONTROLLER_DIR))
    import tinyml_biometric_fusion as T  # noqa: WPS433
    cwf = getattr(T, "CALIBRATION_WINDOW_FRAMES", 1025)
    return T.BiometricFeatureExtractor, T._InputSnapshotLike, cwf


def _snap(snap_cls, f: dict):
    return snap_cls(
        left_stick_x=f.get("left_stick_x", 128), left_stick_y=f.get("left_stick_y", 128),
        right_stick_x=f.get("right_stick_x", 128), right_stick_y=f.get("right_stick_y", 128),
        l2_trigger=f.get("l2_trigger", 0), r2_trigger=f.get("r2_trigger", 0),
        gyro_x=f.get("gyro_x", 0), gyro_y=f.get("gyro_y", 0), gyro_z=f.get("gyro_z", 0),
        accel_x=f.get("accel_x", 0), accel_y=f.get("accel_y", 0), accel_z=f.get("accel_z", 1),
    )


def session_fingerprint(reports: list[dict]) -> np.ndarray:
    """Mean 13-dim L4 feature vector over a session's calibration windows (the session's biometric
    fingerprint). Reuses the canonical BiometricFeatureExtractor at CALIBRATION_WINDOW_FRAMES."""
    ext_cls, snap_cls, cwf = _load_controller()
    snaps = [_snap(snap_cls, r["features"]) for r in reports]
    ext = ext_cls()
    vecs = []
    for i in range(0, max(0, len(snaps) - cwf) + 1, cwf):
        fr = ext.extract(snaps[i:i + cwf], window_frames=cwf)
        vecs.append(np.asarray(fr.to_vector(), dtype=np.float64))
    if not vecs:
        # session shorter than one window — single best-effort extract
        fr = ext.extract(snaps, window_frames=cwf)
        vecs.append(np.asarray(fr.to_vector(), dtype=np.float64))
    return np.mean(np.vstack(vecs), axis=0)


def diag_mahalanobis(vec: np.ndarray, mean: np.ndarray, var: np.ndarray) -> float:
    """Diagonal Mahalanobis distance with a variance floor (no full-cov; matches the N<500 regime)."""
    v = np.asarray(var, dtype=np.float64)
    v = np.where(v < _VAR_FLOOR, _VAR_FLOOR, v)
    diff = np.asarray(vec, dtype=np.float64) - np.asarray(mean, dtype=np.float64)
    return float(np.sqrt(np.sum((diff * diff) / v)))


def reanchored_p_l4(d: float, anomaly_threshold: float = DEFAULT_ANOMALY_THRESHOLD) -> float:
    """Study-only p_L4: 0.5**(d/threshold). d=0 -> 1.0; d==threshold -> 0.5; larger d -> lower.
    Replaces the live exp(-(d-2)) which anchors far tighter than the measured L4 NOMINAL scale."""
    if anomaly_threshold <= 0:
        return 0.0
    return float(0.5 ** (d / anomaly_threshold))


def _synth_binding(path: str, kind: str) -> str:
    return hashlib.sha256(f"offline1khz:{path}:{kind}".encode()).hexdigest()[:32]


def build_human_corpus(
    session_paths: list[str],
    *,
    anomaly_threshold: float = DEFAULT_ANOMALY_THRESHOLD,
    p_l4_fn: Optional[Callable[[float, float], float]] = None,
    loo: bool = True,
) -> list[NqpvCorpusRecord]:
    """Build human-positive NqpvCorpusRecords from hw_* sessions.

    Per session: fingerprint -> L4 Mahalanobis distance vs the population centroid (LOO by default, so a
    session is not scored against a centroid that includes itself) -> l4_l5_l6_ok = (d < threshold) and
    humanity_prob = re-anchored p_L4. cco/poep/coupled-retina abstain (None) -- only L4 is computed
    offline here. ``p_l4_fn(d, threshold)`` overrides the anchor for the study to inject a calibrated one.
    """
    fps = [(p, session_fingerprint(json.load(open(p, encoding="utf-8"))["reports"])) for p in session_paths]
    return records_from_fingerprints(
        fps, anomaly_threshold=anomaly_threshold, p_l4_fn=p_l4_fn, loo=loo,
    )


def records_from_fingerprints(
    fingerprints: list[tuple[str, np.ndarray]],
    *,
    anomaly_threshold: float = DEFAULT_ANOMALY_THRESHOLD,
    p_l4_fn: Optional[Callable[[float, float], float]] = None,
    loo: bool = True,
) -> list[NqpvCorpusRecord]:
    """Pure record-builder over (label, fingerprint) pairs — no file/extractor I/O (testable).

    Per fingerprint: L4 Mahalanobis distance vs the population centroid (LOO by default) ->
    l4_l5_l6_ok = (d < threshold) + humanity_prob = re-anchored p_L4. cco/poep/coupled-retina abstain.
    """
    p_l4_fn = p_l4_fn or reanchored_p_l4
    mat = np.vstack([fp for _, fp in fingerprints])
    records: list[NqpvCorpusRecord] = []
    for i, (path, fp) in enumerate(fingerprints):
        ref = np.delete(mat, i, axis=0) if (loo and len(fingerprints) > 1) else mat
        mean, var = ref.mean(axis=0), ref.var(axis=0)
        dist = diag_mahalanobis(fp, mean, var)
        records.append(NqpvCorpusRecord(
            device_id=_synth_binding(path, "dev"),
            record_hash=_synth_binding(path, "rec"),
            ts_ns=0,
            label=LABEL_HUMAN,
            source="offline_1khz",
            cco_tier=None,            # abstain: not computed offline
            l4_l5_l6_ok=bool(dist < anomaly_threshold),  # the real L4 NOMINAL verdict
            poep_present=None,        # abstain
            retina_coupled_verdict=None,  # abstain (no camera witness)
            retina_controller_signal=None,
            consent_ok=True,
            humanity_prob=round(p_l4_fn(dist, anomaly_threshold), 4),
        ))
    return records
