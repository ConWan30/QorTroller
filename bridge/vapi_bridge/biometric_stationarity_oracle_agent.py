"""
BiometricStationarityOracleAgent — Phase 188, agent #32.

Classifies P1 biometric non-stationarity into two mutually exclusive causes:
  - P(genuine_drift): physiological drift over time (different physical state across days)
  - P(adversarial_window): adversary exploiting re-enrollment window (different player captured)

Both causes produce the same observable signal from Agents 23/24:
  TDI > 0.05, trend_velocity < -0.05, LOO classification below random.

The discriminator is Agent 25 (PoACChainIntegrityMonitor):
  Genuine physiological drift does NOT produce PoAC chain integrity anomalies.
  Adversarial window exploitation DOES — session count jumps, timestamp clustering,
  potential chain linkage gaps all coincide with the drift period.

stationarity_verdict:
  ADVERSARIAL_WINDOW  — P(adversarial) > stationarity_adversarial_threshold (default 0.60)
                        → fires biometric_window_alert bus event
  GENUINE_DRIFT       — P(genuine) > stationarity_adversarial_threshold
                        → logs RE_ENROLLMENT_REQUIRED recommendation
  AMBIGUOUS           — neither probability > threshold
  STABLE              — no drift signal detected (TDI ≈ 0, velocity ≈ 0)

Infrastructure-first default: biometric_stationarity_enabled=False.
Fail-open: exceptions → WARNING logged, no classification stored.
"""

import asyncio
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 600  # 10-minute poll cycle


class BiometricStationarityOracleAgent:
    """Agent #32 — Phase 188 biometric non-stationarity cause classifier.

    Reads signals from:
      - separation_ratio_recovery_log (Agent 23: trend_velocity, recovery_action)
      - age_weight_analysis_log (Agent 24: temporal_drift_index, drift_direction)
      - poac_chain_audit_log (Agent 25: integrity_score, broken_links)

    Computes P(genuine_drift) and P(adversarial_window) independently.
    Publishes biometric_window_alert bus event when adversarial signature detected.
    """

    def __init__(self, store, cfg, bus=None):
        self._store = store
        self._cfg = cfg
        self._bus = bus
        self._adversarial_threshold = float(getattr(cfg, "stationarity_adversarial_threshold", 0.60))
        self._chain_integrity_floor = float(getattr(cfg, "stationarity_chain_integrity_floor", 0.95))

    # ------------------------------------------------------------------
    # Classification logic
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_p_genuine_drift(
        trend_velocity: float,
        temporal_drift_index: float,
        chain_integrity_score: float,
        drift_direction: str,
    ) -> float:
        """Compute P(genuine_drift) from multi-agent signals.

        Genuine physiological drift:
          - Strong negative velocity (< -0.05 per snapshot)
          - TDI > 0.05 (old sessions inflate ratio → old sessions cluster differently)
          - Chain integrity ≈ 1.0 (no chain anomalies — genuine drift is continuous)
          - drift_direction = P1_NONSTATIONARITY
        """
        score = 0.0
        # Velocity signal (weight 0.35)
        if trend_velocity <= -0.10:
            score += 0.35
        elif trend_velocity <= -0.05:
            score += 0.20
        # TDI signal (weight 0.25)
        if temporal_drift_index > 0.10:
            score += 0.25
        elif temporal_drift_index > 0.05:
            score += 0.15
        # Chain integrity (weight 0.25) — genuine drift: intact chain
        if chain_integrity_score >= 0.98:
            score += 0.25
        elif chain_integrity_score >= 0.95:
            score += 0.12
        # Drift direction label (weight 0.15)
        if drift_direction in ("P1_NONSTATIONARITY",):
            score += 0.15
        return min(1.0, round(score, 4))

    def _compute_p_adversarial_window(
        self,
        trend_velocity: float,
        temporal_drift_index: float,
        chain_integrity_score: float,
        recovery_action: str,
    ) -> float:
        """Compute P(adversarial_window) from multi-agent signals.

        Adversarial window exploitation:
          - Drift present (velocity negative, TDI elevated)
          - Chain integrity below floor — anomalies coincide with drift period
          - Recovery action P1_RE_ENROLLMENT fired with compromised chain
        """
        score = 0.0
        # Drift must be present for adversarial window to be relevant
        drift_present = trend_velocity <= -0.05 or temporal_drift_index > 0.05
        if not drift_present:
            return 0.0
        # Chain integrity anomaly (weight 0.45 — primary discriminator)
        if chain_integrity_score < self._chain_integrity_floor:
            gap = self._chain_integrity_floor - chain_integrity_score
            score += min(0.45, 0.45 * (gap / 0.10))
        # Velocity magnitude (weight 0.30) — adversarial insertion is sudden
        if trend_velocity <= -0.15:
            score += 0.30  # very sudden drop
        elif trend_velocity <= -0.08:
            score += 0.15
        # Re-enrollment action fired coincident with integrity anomaly (weight 0.25)
        if recovery_action in ("P1_RE_ENROLLMENT",) and chain_integrity_score < self._chain_integrity_floor:
            score += 0.25
        return min(1.0, round(score, 4))

    def _classify(
        self,
        p_genuine: float,
        p_adversarial: float,
        trend_velocity: float,
        temporal_drift_index: float,
    ) -> str:
        """Determine stationarity_verdict from probability pair."""
        # STABLE: no drift signal
        if abs(trend_velocity) < 0.02 and temporal_drift_index < 0.03:
            return "STABLE"
        # ADVERSARIAL_WINDOW: adversarial probability exceeds threshold
        if p_adversarial >= self._adversarial_threshold:
            return "ADVERSARIAL_WINDOW"
        # GENUINE_DRIFT: genuine probability exceeds threshold
        if p_genuine >= self._adversarial_threshold:
            return "GENUINE_DRIFT"
        # AMBIGUOUS: drift present but neither cause dominates
        return "AMBIGUOUS"

    # ------------------------------------------------------------------
    # Run cycle
    # ------------------------------------------------------------------

    def _run_cycle(self) -> "dict | None":
        """Execute one classification cycle. Returns result dict or None on error."""
        try:
            # Read Agent 23 signal
            _recovery_rows = self._store.get_separation_ratio_recovery_status(limit=1)
            _rec23 = _recovery_rows[0] if _recovery_rows else {}
            _velocity = float(_rec23.get("trend_velocity", 0.0))
            _recovery_action = str(_rec23.get("recovery_action", "STABLE"))
            _player_id = str(_rec23.get("player_id", ""))

            # Read Agent 24 signal
            _age_rows = self._store.get_age_weight_analysis_status(limit=1)
            _rec24 = _age_rows[0] if _age_rows else {}
            _tdi = float(_rec24.get("temporal_drift_index", 0.0))
            _drift_direction = str(_rec24.get("drift_direction", "STABLE"))

            # Read Agent 25 signal
            _chain_status = self._store.get_poac_chain_audit_status()
            _chain_integrity = float(_chain_status.get("integrity_score", 1.0))
            _session_count = int(_chain_status.get("total_records", 0))

            # Compute probabilities
            _p_genuine = self._compute_p_genuine_drift(
                trend_velocity=_velocity,
                temporal_drift_index=_tdi,
                chain_integrity_score=_chain_integrity,
                drift_direction=_drift_direction,
            )
            _p_adversarial = self._compute_p_adversarial_window(
                trend_velocity=_velocity,
                temporal_drift_index=_tdi,
                chain_integrity_score=_chain_integrity,
                recovery_action=_recovery_action,
            )

            # Classify
            _verdict = self._classify(_p_genuine, _p_adversarial, _velocity, _tdi)
            _confidence = max(_p_genuine, _p_adversarial)

            # Persist
            self._store.insert_biometric_stationarity_log(
                player_id=_player_id,
                p_genuine_drift=_p_genuine,
                p_adversarial_window=_p_adversarial,
                stationarity_verdict=_verdict,
                chain_integrity_score=_chain_integrity,
                trend_velocity=_velocity,
                temporal_drift_index=_tdi,
                session_count_used=_session_count,
            )

            log.debug(
                "BiometricStationarityOracleAgent: verdict=%s P(genuine)=%.3f P(adversarial)=%.3f "
                "chain_integrity=%.3f velocity=%.3f TDI=%.3f",
                _verdict, _p_genuine, _p_adversarial, _chain_integrity, _velocity, _tdi,
            )

            # Publish bus event when adversarial signature detected
            if _verdict == "ADVERSARIAL_WINDOW" and self._bus is not None:
                _event = {
                    "player_id":             _player_id,
                    "p_adversarial_window":  _p_adversarial,
                    "stationarity_verdict":  _verdict,
                    "chain_integrity_score": _chain_integrity,
                    "trend_velocity":        _velocity,
                    "tdi":                   _tdi,
                    "timestamp":             time.time(),
                }
                try:
                    self._bus.publish_sync("biometric_window_alert", _event)
                    log.warning(
                        "BiometricStationarityOracleAgent: ADVERSARIAL_WINDOW detected "
                        "P(adversarial)=%.3f chain_integrity=%.3f player_id=%s",
                        _p_adversarial, _chain_integrity, _player_id,
                    )
                except Exception as _bus_exc:
                    log.warning("BiometricStationarityOracleAgent bus publish error: %s", _bus_exc)

            return {
                "verdict":        _verdict,
                "p_genuine":      _p_genuine,
                "p_adversarial":  _p_adversarial,
                "confidence":     _confidence,
            }

        except Exception as exc:
            log.warning("BiometricStationarityOracleAgent._run_cycle error: %s", exc)
            return None

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Poll every 10 minutes, classify biometric stationarity cause."""
        log.info(
            "BiometricStationarityOracleAgent started (agent #32, Phase 188; "
            "poll=%ds, adversarial_threshold=%.2f, chain_floor=%.2f)",
            _POLL_INTERVAL_S, self._adversarial_threshold, self._chain_integrity_floor,
        )
        while True:
            await asyncio.sleep(_POLL_INTERVAL_S)
            self._run_cycle()
