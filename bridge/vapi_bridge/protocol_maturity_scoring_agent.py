"""
Phase 177 — ProtocolMaturityScoringAgent (agent #26)
Phase 191 — Threat Succession Protocol (TSP) v2 rebalance

Synthesises 8 agent signals into a unified maturity_score (0.0–1.0) that
reflects VAPI's overall protocol readiness.

Component weights v2 (sum = 1.0, Phase 191 TSP rebalance):
    separation_component               0.20  — inter-person ratio vs 1.0 target
    chain_integrity_component          0.20  — PoAC chain intact fraction
    consent_component                  0.15  — active consent corpus coverage
    biometric_freshness_component      0.12  — credential TTL not expired
    agent_calibration_component        0.12  — ACIM pass rate across agent fleet
    enrollment_component               0.10  — sessions_needed_total == 0
    threat_forecast_accuracy_component 0.07  — PIR harness_score (Phase 189 TSP)
    biometric_stationarity_component   0.04  — BSO confidence (Phase 188)

Maturity tiers:
    ALPHA              maturity_score < 0.50
    BETA               0.50 <= maturity_score < 0.85
    PRODUCTION_CANDIDATE maturity_score >= 0.85  (requires separation_ratio > 1.0 + all gates)

W2 opportunity: maturity_score >= 0.85 as composable tournament primitive
and DePIN data-marketplace trustworthiness oracle.

Poll interval: 600s (10 minutes).
Fail-safe: errors → ALPHA-tier score=0.0 returned (never raises, never blocks).
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

_BETA_THRESHOLD        = 0.50
_PRODUCTION_THRESHOLD  = 0.85

_WEIGHTS = {
    "separation_component":               0.20,  # Phase 177; was 0.25, reduced Phase 191
    "chain_integrity_component":          0.20,  # Phase 176; unchanged
    "consent_component":                  0.15,  # Phase 160; unchanged
    "biometric_freshness_component":      0.12,  # Phase 178; was 0.15, reduced Phase 191
    "agent_calibration_component":        0.12,  # Phase 148; was 0.15, reduced Phase 191
    "enrollment_component":               0.10,  # Phase 156; unchanged
    "threat_forecast_accuracy_component": 0.07,  # Phase 191 TSP — PIR harness score
    "biometric_stationarity_component":   0.04,  # Phase 191 TSP — BSO confidence
}


def _tier(score: float) -> str:
    if score >= _PRODUCTION_THRESHOLD:
        return "PRODUCTION_CANDIDATE"
    if score >= _BETA_THRESHOLD:
        return "BETA"
    return "ALPHA"


class ProtocolMaturityScoringAgent:
    """Agent #26 — ProtocolMaturityScoringAgent.

    Reads (all from store, no external calls):
        separation_ratio_snapshots  → separation_component
        poac_chain_audit_log        → chain_integrity_component
        consent_ledger              → consent_component
        biometric_renewal_log       → biometric_freshness_component
        agent_calibration_health    → agent_calibration_component
        enrollment_auto_guidance    → enrollment_component

    Stores:
        protocol_maturity_log (Phase 177)

    Publishes:
        maturity_elevation_available bus event when gap_to_next_tier < 0.05
    """

    _POLL_INTERVAL_S = 600

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Component readers
    # ------------------------------------------------------------------

    def _separation_component(self) -> float:
        """Separation ratio clamped to [0.0, 1.0]. 1.0 when ratio >= 1.0."""
        try:
            rows = self._store.get_separation_ratio_status(limit=1)
            if not rows:
                return 0.0
            ratio = float(rows[0].get("pooled_ratio", 0.0))
            return round(min(1.0, max(0.0, ratio)), 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: separation read error: %s", exc)
            return 0.0

    def _chain_integrity_component(self) -> float:
        """Latest PoAC chain integrity_score (0.0–1.0)."""
        try:
            rows = self._store.get_poac_chain_audit_status(limit=1)
            if not rows:
                return 1.0   # vacuously intact when no audit yet
            return round(float(rows[0].get("integrity_score", 1.0)), 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: chain integrity read error: %s", exc)
            return 1.0   # fail-open

    def _consent_component(self) -> float:
        """1.0 when consent corpus is defensible (zero revocations); else fractional."""
        try:
            cov = self._store.get_consent_corpus_coverage()
            if cov.get("consent_corpus_defensible"):
                return 1.0
            total = int(cov.get("active_consent_count", 0))
            revoked = int(cov.get("revoked_count", 0)) + int(cov.get("erasure_requested_count", 0))
            if total <= 0:
                return 0.0
            return round(max(0.0, (total - revoked) / total), 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: consent read error: %s", exc)
            return 1.0   # fail-open: unknown consent → assume covered

    def _biometric_freshness_component(self) -> float:
        """1.0 when biometric credential is not expired; 0.0 when TTL expired."""
        try:
            ttl_days = float(getattr(self._cfg, "biometric_credential_ttl_days", 90.0))
            status = self._store.get_biometric_credential_age_status(ttl_days=ttl_days)
            if not status:
                return 1.0   # no credential yet → not expired
            if status.get("ttl_expired"):
                return 0.0
            # Partial freshness: linear decay as credential ages toward TTL
            age_days = float(status.get("age_days", 0.0))
            if ttl_days <= 0:
                return 1.0
            return round(max(0.0, 1.0 - age_days / ttl_days), 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: freshness read error: %s", exc)
            return 1.0   # fail-open

    def _agent_calibration_component(self) -> float:
        """ACIM pass_rate across the agent fleet (0.0–1.0)."""
        try:
            rows = self._store.get_agent_calibration_health(limit=1)
            if not rows:
                return 0.5   # unknown → neutral
            row = rows[0]
            healthy = int(row.get("healthy_agents", 0))
            total   = int(row.get("total_agents", 1))
            if total <= 0:
                return 0.5
            return round(healthy / total, 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: calibration read error: %s", exc)
            return 0.5

    def _enrollment_component(self) -> float:
        """1.0 when sessions_needed_total == 0 (all players enrolled)."""
        try:
            status = self._store.get_enrollment_guidance_status()
            if not status:
                return 0.0
            needed = int(status.get("sessions_needed_total", 1))
            if needed <= 0:
                return 1.0
            # Partial credit: normalise against 30-session target (3 players × 10)
            target = 30
            progress = max(0, target - needed)
            return round(min(1.0, progress / target), 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: enrollment read error: %s", exc)
            return 0.0

    def _threat_forecast_accuracy_component(self) -> float:
        """Latest PIR harness_score as threat forecast accuracy proxy (Phase 191 TSP).

        Reads protocol_intelligence_record_log.harness_score via store.
        Returns 0.5 (neutral) when no PIR data exists or on error.
        """
        try:
            return self._store.get_threat_forecast_accuracy()
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: threat forecast read error: %s", exc)
            return 0.5  # neutral

    def _biometric_stationarity_component(self) -> float:
        """Latest biometric_stationarity_confidence from BiometricStationarityOracleAgent (Phase 191 TSP).

        Returns 0.5 (neutral) when no stationarity data exists (session_count_used == 0) or on error.
        The store returns confidence=0.0 with session_count_used=0 for empty tables;
        we convert this to the neutral prior rather than penalising an absent BSO assessment.
        """
        try:
            status = self._store.get_biometric_stationarity_status()
            if not status:
                return 0.5  # neutral when no dict returned
            if int(status.get("session_count_used", 0)) == 0:
                return 0.5  # no BSO data yet — neutral prior
            return round(float(status.get("biometric_stationarity_confidence", 0.5)), 6)
        except Exception as exc:
            log.debug("ProtocolMaturityScoringAgent: stationarity read error: %s", exc)
            return 0.5

    # ------------------------------------------------------------------
    # Poll logic
    # ------------------------------------------------------------------

    def _run_scoring(self) -> dict:
        """Run one maturity scoring cycle.

        Returns summary dict. Fail-safe: any error → ALPHA defaults.
        """
        enabled = bool(getattr(self._cfg, "protocol_maturity_enabled", True))
        if not enabled:
            return {"protocol_maturity_enabled": False, "maturity_tier": "ALPHA", "maturity_score": 0.0}

        try:
            components = {
                "separation_component":               self._separation_component(),
                "chain_integrity_component":          self._chain_integrity_component(),
                "consent_component":                  self._consent_component(),
                "biometric_freshness_component":      self._biometric_freshness_component(),
                "agent_calibration_component":        self._agent_calibration_component(),
                "enrollment_component":               self._enrollment_component(),
                "threat_forecast_accuracy_component": self._threat_forecast_accuracy_component(),
                "biometric_stationarity_component":   self._biometric_stationarity_component(),
            }

            maturity_score = round(
                sum(components[k] * w for k, w in _WEIGHTS.items()), 6
            )
            maturity_tier  = _tier(maturity_score)

            self._store.insert_protocol_maturity_log(
                separation_component=components["separation_component"],
                chain_integrity_component=components["chain_integrity_component"],
                consent_component=components["consent_component"],
                biometric_freshness_component=components["biometric_freshness_component"],
                agent_calibration_component=components["agent_calibration_component"],
                enrollment_component=components["enrollment_component"],
                threat_forecast_accuracy_component=components["threat_forecast_accuracy_component"],
                biometric_stationarity_component=components["biometric_stationarity_component"],
            )

            # Gap to next tier — fire bus event when within striking distance
            if maturity_tier == "ALPHA":
                gap = round(_BETA_THRESHOLD - maturity_score, 4)
            elif maturity_tier == "BETA":
                gap = round(_PRODUCTION_THRESHOLD - maturity_score, 4)
            else:
                gap = 0.0

            if gap < 0.05 and self._bus is not None:
                try:
                    self._bus.publish("maturity_elevation_available", {
                        "maturity_score": maturity_score,
                        "maturity_tier":  maturity_tier,
                        "gap_to_target":  gap,
                        "ts":             time.time(),
                    })
                except Exception as exc:
                    log.debug("ProtocolMaturityScoringAgent: bus publish error: %s", exc)

            log.info(
                "ProtocolMaturityScoringAgent: score=%.4f tier=%s "
                "sep=%.3f chain=%.3f consent=%.3f fresh=%.3f cal=%.3f enroll=%.3f "
                "tfa=%.3f bso=%.3f",
                maturity_score, maturity_tier,
                components["separation_component"],
                components["chain_integrity_component"],
                components["consent_component"],
                components["biometric_freshness_component"],
                components["agent_calibration_component"],
                components["enrollment_component"],
                components["threat_forecast_accuracy_component"],
                components["biometric_stationarity_component"],
            )

            return {
                "protocol_maturity_enabled": True,
                "maturity_score":            maturity_score,
                "maturity_tier":             maturity_tier,
                **components,
            }

        except Exception as exc:
            log.error(
                "ProtocolMaturityScoringAgent: scoring error: %s", exc, exc_info=True
            )
            return {
                "protocol_maturity_enabled":          True,
                "maturity_score":                     0.0,
                "maturity_tier":                      "ALPHA",
                "separation_component":               0.0,
                "chain_integrity_component":          1.0,
                "consent_component":                  1.0,
                "biometric_freshness_component":      1.0,
                "agent_calibration_component":        0.5,
                "enrollment_component":               0.0,
                "threat_forecast_accuracy_component": 0.5,
                "biometric_stationarity_component":   0.5,
            }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Async poll loop — 600s interval. Never raises."""
        log.info("ProtocolMaturityScoringAgent starting (interval=%ss)", self._POLL_INTERVAL_S)
        while True:
            try:
                self._run_scoring()
            except Exception as exc:
                log.error(
                    "ProtocolMaturityScoringAgent: unhandled poll error: %s", exc, exc_info=True
                )
            await asyncio.sleep(self._POLL_INTERVAL_S)
