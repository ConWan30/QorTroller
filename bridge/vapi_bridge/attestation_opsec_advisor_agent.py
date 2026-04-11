"""
Phase 187 — AttestationOpSecAdvisorAgent (agent #31)

Provides real-time operational security monitoring for attestation hash
front-running risk (WIF-033 W1 closure).

WIF-033 W1 CLOSED:
  The adversary can monitor the IoTeX mempool for registerAttestation()
  transactions and extract the attestation_hash from calldata before confirmation.
  While HMAC secrecy prevents forgery, the mempool disclosure reveals:
    (a) which player is re-enrolling
    (b) the 7-day window when biometric gate is reconfiguring
    (c) optimal timing for adversarial tournament attempts

  This agent makes the disclosure risk operationally visible and advises operators
  to USE_PRIVATE_MEMPOOL_OR_DELAY_TX when risk is HIGH.

Risk computation:
  HIGH:   active_attestations > 0 AND attestation_bound_renewal_enabled=True
           (on-chain registration is occurring — mempool exposes hash + timing)
  MEDIUM: active_attestations > 0 AND attestation_bound_renewal_enabled=False
           (off-chain only, but re-enrollment window still a timing signal)
  LOW:    active_attestations == 0
           (no re-enrollment window open — no timing signal to leak)

Poll interval: 600s (10 minutes).
Publishes: opsec_risk_high bus event when risk=HIGH.
Fail-open: exceptions log WARNING, do not block any operation.
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 600


class AttestationOpSecAdvisorAgent:
    """
    Agent #31 — AttestationOpSecAdvisorAgent.

    Reads:
        - store.get_active_attestation(player_id): active re-enrollment tokens
        - store.get_attestation_opsec_status(): prior advisory records

    Computes:
        - timing_disclosure_risk: HIGH/MEDIUM/LOW
        - recommendation: operator action guidance

    Stores:
        - attestation_opsec_log (Phase 187) — per-cycle advisory records

    Publishes (via bus.publish_sync):
        - opsec_risk_high bus event when timing_disclosure_risk=HIGH
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Risk computation
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_risk_level(active_attestations: int, bound_renewal_enabled: bool) -> str:
        """Compute timing_disclosure_risk from active attestation count and config state.

        HIGH:   active windows + on-chain binding enabled (mempool reveals hash + timing)
        MEDIUM: active windows but on-chain binding disabled (off-chain timing signal only)
        LOW:    no active re-enrollment windows
        """
        if active_attestations <= 0:
            return "LOW"
        if bound_renewal_enabled:
            return "HIGH"
        return "MEDIUM"

    @staticmethod
    def _compute_recommendation(risk: str) -> str:
        """Return operator recommendation string for the given risk level."""
        if risk == "HIGH":
            return "USE_PRIVATE_MEMPOOL_OR_DELAY_TX"
        if risk == "MEDIUM":
            return "MONITOR_REENROLLMENT_WINDOW"
        return "STANDARD_TX_OK"

    # ------------------------------------------------------------------
    # Poll cycle
    # ------------------------------------------------------------------

    def _run_cycle(self) -> dict:
        """Assess attestation op-sec risk and log advisory. Called from run_poll_loop."""
        if not getattr(self._cfg, "mempool_opsec_enabled", False):
            return {"mempool_opsec_enabled": False}

        try:
            # Count active (non-expired) attestations across all players.
            # Query persona_break_attestation_log directly for active+non-expired rows.
            with self._store._conn() as _conn:
                active_count = _conn.execute(
                    "SELECT COUNT(*) FROM persona_break_attestation_log"
                    " WHERE active=1 AND expires_at > strftime('%s','now')"
                ).fetchone()[0] or 0
                # Get all distinct player_ids with active attestations for logging.
                active_rows = _conn.execute(
                    "SELECT player_id FROM persona_break_attestation_log"
                    " WHERE active=1 AND expires_at > strftime('%s','now')"
                ).fetchall()

            bound_renewal_enabled = bool(
                getattr(self._cfg, "attestation_bound_renewal_enabled", False)
            )
            risk = self._compute_risk_level(active_count, bound_renewal_enabled)
            recommendation = self._compute_recommendation(risk)
            window_active = active_count > 0

            # Log advisory for each active player, or one aggregate record.
            if active_rows:
                for _row in active_rows:
                    player_id = str(_row["player_id"]) if _row["player_id"] else ""
                    self._store.insert_attestation_opsec_log(
                        player_id=player_id,
                        timing_disclosure_risk=risk,
                        active_attestations=active_count,
                        re_enrollment_window_active=window_active,
                        recommendation=recommendation,
                    )
            else:
                self._store.insert_attestation_opsec_log(
                    player_id="",
                    timing_disclosure_risk=risk,
                    active_attestations=0,
                    re_enrollment_window_active=False,
                    recommendation=recommendation,
                )

            log.info(
                "AttestationOpSecAdvisorAgent: risk=%s active_attestations=%d recommendation=%s",
                risk, active_count, recommendation,
            )

            # Publish bus event when HIGH risk.
            if risk == "HIGH" and self._bus is not None:
                try:
                    self._bus.publish_sync("opsec_risk_high", {
                        "timing_disclosure_risk": risk,
                        "active_attestations":    active_count,
                        "recommendation":         recommendation,
                        "ts":                     time.time(),
                    })
                except Exception as _bus_exc:
                    log.warning(
                        "AttestationOpSecAdvisorAgent: bus publish failed: %s", _bus_exc
                    )

            return {
                "mempool_opsec_enabled":    True,
                "timing_disclosure_risk":   risk,
                "active_attestations":      active_count,
                "recommendation":           recommendation,
            }

        except Exception as exc:
            log.error(
                "AttestationOpSecAdvisorAgent: _run_cycle error: %s", exc, exc_info=True
            )
            return {"mempool_opsec_enabled": True, "error": str(exc)}

    async def run_poll_loop(self) -> None:
        """Async poll loop — 600s interval. Never raises."""
        log.info("AttestationOpSecAdvisorAgent starting (interval=%ss)", _POLL_INTERVAL_S)
        while True:
            try:
                self._run_cycle()
            except Exception as exc:
                log.error(
                    "AttestationOpSecAdvisorAgent: unhandled error in poll: %s", exc,
                    exc_info=True,
                )
            await asyncio.sleep(_POLL_INTERVAL_S)
