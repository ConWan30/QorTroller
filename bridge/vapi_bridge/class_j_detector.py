"""Phase 81 — ClassJDetector: per-device GaussianHMM ML-bot risk assessment.

Polls pitl_session_proofs every 5 min for new sessions.
Maintains rolling deque of class_j_entropy_windows x 120-frame entropy windows per device.
Publishes class_j_high_risk_detected to bus when risk crosses HIGH.

Risk levels:
  LOW:    entropy_variance > 0.15 (human-consistent — game events create clustering)
  MEDIUM: 0.05 < entropy_variance <= 0.15 (ambiguous)
  HIGH:   entropy_variance <= 0.05 (Class J signature — HMM uniform transitions)

Discriminating signal: temporal_state_transition_entropy_variance
  Human psychomotor control: rhythmically structured state transitions (variance > 0.15)
  HMM sampling: pathologically uniform transitions (variance < 0.02)

Feature slot: index 12 — expands feature space beyond current 12-feature L4.
Calibration: run threshold_calibrator.py against N=74 + 15 Class J sessions.
"""

import asyncio
import json
import logging
from collections import defaultdict, deque

log = logging.getLogger(__name__)

# Phase 235.x-STABILITY-9 stage 4b 2026-05-17: poll interval lengthened
# 300s → 1800s. ML-bot pattern accumulation is N-window analysis bound;
# trigger threshold (Phase 81 default n_windows=10) cannot accumulate faster
# than the session arrival rate. Event-driven conversion (subscribe to a
# `ruling_completed` bus event with class_j_ml_bot_risk=HIGH) deferred —
# see agent_rationalization_v1.md §3.5.
_POLL_INTERVAL_S = 1800       # 30 minutes (was 300s = 5 min)
_HIGH_RISK_THRESHOLD = 0.05   # entropy_variance <= this → HIGH
_MEDIUM_RISK_THRESHOLD = 0.15  # entropy_variance <= this → MEDIUM (else LOW)


class ClassJDetector:
    """Phase 81 — Per-device GaussianHMM ML-bot risk assessment via entropy variance."""

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus
        self._n_windows = int(getattr(cfg, "class_j_entropy_windows", 10))
        # Per-device deque of entropy values (one per session window)
        self._entropy_windows: dict = defaultdict(lambda: deque(maxlen=self._n_windows))
        # Per-device: last processed session id to avoid reprocessing
        self._last_session_id: dict = {}

    async def run_poll_loop(self) -> None:
        """Background polling loop — checks for new sessions every 5 minutes."""
        log.info(
            "ClassJDetector started (Phase 81) poll=%ds n_windows=%d",
            _POLL_INTERVAL_S, self._n_windows,
        )
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                if getattr(self._cfg, "class_j_detection_enabled", True):
                    await self._process_new_sessions()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "ClassJDetector: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("ClassJDetector: cycle error: %s", exc)

    async def _process_new_sessions(self) -> None:
        """Fetch new PITL sessions and update entropy windows per device."""
        try:
            with self._store._conn() as conn:
                rows = conn.execute(
                    "SELECT id, device_id, l4_features_json FROM pitl_session_proofs "
                    "ORDER BY created_at DESC LIMIT 200"
                ).fetchall()
        except Exception as exc:
            log.debug("ClassJDetector: pitl_session_proofs query failed: %s", exc)
            return

        if not rows:
            return

        # Group features by device
        device_sessions: dict = defaultdict(list)
        for row in rows:
            row_dict = dict(row) if hasattr(row, "keys") else {
                "id": row[0], "device_id": row[1], "l4_features_json": row[2]
            }
            did = row_dict.get("device_id", "")
            fj = row_dict.get("l4_features_json", "")
            sid = row_dict.get("id", 0)
            if did and fj:
                device_sessions[did].append((sid, fj))

        for device_id, sessions in device_sessions.items():
            try:
                await self._update_device_assessment(device_id, sessions)
            except Exception as exc:
                log.debug("ClassJDetector: device assessment failed for %s: %s",
                          str(device_id)[:12], exc)

    async def _update_device_assessment(self, device_id: str, sessions: list) -> None:
        """Update entropy windows for a device and emit assessment."""
        for session_id, features_json in sessions:
            last = self._last_session_id.get(device_id, 0)
            if session_id <= last:
                continue
            self._last_session_id[device_id] = session_id

            try:
                features = (
                    json.loads(features_json)
                    if isinstance(features_json, str)
                    else (features_json or {})
                )
                window_entropy = self._compute_session_entropy(features)
                self._entropy_windows[device_id].append(window_entropy)
            except Exception as exc:
                log.debug("ClassJDetector: feature parse error for %s: %s",
                          str(device_id)[:12], exc)
                continue

        # Need at least 2 windows to compute variance
        windows = list(self._entropy_windows[device_id])
        if len(windows) < 2:
            return

        variance = self._temporal_state_transition_entropy_variance(windows)
        risk_level = self._classify_risk(variance)

        try:
            self._store.insert_class_j_assessment(
                device_id=device_id,
                entropy_variance=variance,
                risk_level=risk_level,
                window_count=len(windows),
            )
        except Exception as exc:
            log.debug("ClassJDetector: insert_class_j_assessment failed: %s", exc)

        if risk_level == "HIGH" and self._bus is not None:
            try:
                await self._bus.publish(
                    "class_j_high_risk_detected",
                    {
                        "device_id": device_id,
                        "entropy_variance": variance,
                        "risk_level": risk_level,
                        "window_count": len(windows),
                    },
                    "class_j_detector",
                )
                log.warning(
                    "ClassJDetector: HIGH Class J risk device=%s variance=%.4f",
                    str(device_id)[:12], variance,
                )
            except Exception as exc:
                log.debug("ClassJDetector: bus publish failed: %s", exc)

    @staticmethod
    def _compute_session_entropy(features: dict) -> float:
        """Compute a single entropy value for this session window.

        Uses L5 entropy as the primary signal. Human sessions have entropy
        that varies according to game events; HMM sessions are artificially uniform.
        Returns 0.0 if insufficient data.
        """
        l5_entropy = float(features.get("l5_entropy_bits", 0.0) or 0.0)
        if l5_entropy > 0.0:
            return l5_entropy
        # Fallback: use L4 Mahalanobis distance as proxy (normalize to entropy-like scale)
        l4_dist = float(features.get("l4_distance", 0.0) or 0.0)
        return min(l4_dist / 10.0, 9.0)

    @staticmethod
    def _temporal_state_transition_entropy_variance(entropy_windows: list) -> float:
        """Variance of Shannon entropy across N entropy windows.

        Human: variance > 0.15 (game events create clustering — rhythmic structure)
        Class J: variance < 0.02 (HMM uniform transitions — no cognitive structure)
        Returns 0.0 if < 2 windows available.

        Feature slot: index 12 — expands _BIO_FEATURE_DIM 12->13 (11 active features).
        """
        n = len(entropy_windows)
        if n < 2:
            return 0.0
        mean = sum(entropy_windows) / n
        variance = sum((x - mean) ** 2 for x in entropy_windows) / (n - 1)
        return round(variance, 6)

    @staticmethod
    def _classify_risk(entropy_variance: float) -> str:
        """Classify entropy variance into LOW/MEDIUM/HIGH risk."""
        if entropy_variance <= _HIGH_RISK_THRESHOLD:
            return "HIGH"
        if entropy_variance <= _MEDIUM_RISK_THRESHOLD:
            return "MEDIUM"
        return "LOW"

    def assess(self, device_id: str) -> dict:
        """Synchronous assessment for a device. Returns current risk level.

        Never raises — returns LOW on error.
        """
        try:
            windows = list(self._entropy_windows.get(str(device_id) if device_id else "", []))
            if len(windows) < 2:
                return {
                    "device_id": device_id,
                    "entropy_variance": 0.0,
                    "risk_level": "LOW",
                    "window_count": len(windows),
                    "note": "Insufficient windows for assessment",
                }
            variance = self._temporal_state_transition_entropy_variance(windows)
            risk = self._classify_risk(variance)
            return {
                "device_id": device_id,
                "entropy_variance": variance,
                "risk_level": risk,
                "window_count": len(windows),
            }
        except Exception as exc:
            log.warning("ClassJDetector.assess: %s", exc)
            return {
                "device_id": device_id,
                "entropy_variance": 0.0,
                "risk_level": "LOW",
                "window_count": 0,
                "error": str(exc),
            }
