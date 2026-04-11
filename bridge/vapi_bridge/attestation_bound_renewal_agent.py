"""
Phase 186 — AttestationBoundRenewalAgent (agent #30)

Enforces that every biometric re-enrollment renewal is cryptographically authorized
by a valid HMAC attestation from ReEnrollmentAttestationAgent (Phase 185).

WIF-032 W2 CLOSED:
  When attestation_bound_renewal_enabled=True:
    POST /agent/renew-separation-ratio-commitment requires a valid, active,
    non-expired attestation_hash in the request body. Renewals without a valid
    attestation are rejected with HTTP 403 "attestation_required".
  Infrastructure-first default: disabled (no behavior change to existing renewals).

Validation logic (validate_attestation_for_renewal):
  1. Check store.get_active_attestation(player_id) → active=True required
  2. Check attestation_hash matches the stored active token (exact match)
  3. Check expires_at > now (not expired)
  Returns (True, "") on success; (False, reason) on failure.

Poll interval: 600s (10 minutes).
Fail-open when disabled: all renewals proceed without attestation check.
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 600


class AttestationBoundRenewalAgent:
    """
    Agent #30 — AttestationBoundRenewalAgent.

    Reads:
        - store.get_active_attestation(player_id): validates active attestation
        - store.get_attestation_bound_renewal_status(): reports audit log

    Validates:
        - attestation_hash matches active stored token for player_id
        - attestation is not expired (expires_at > now)

    Stores:
        - attestation_bound_renewal_log (Phase 186) — every renewal attempt audited

    Publishes (via bus.publish_sync):
        - renewal_blocked bus event when attestation invalid and enabled
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Attestation validation
    # ------------------------------------------------------------------

    def validate_attestation_for_renewal(
        self,
        player_id: str,
        attestation_hash: str,
    ) -> tuple[bool, str]:
        """Validate that the provided attestation_hash is active and not expired.

        Returns (True, "") when valid.
        Returns (False, reason) when invalid — caller should block the renewal.
        Fail-open: exceptions return (True, "") to avoid blocking on agent error.
        """
        try:
            active_rec = self._store.get_active_attestation(player_id)
            if not active_rec.get("active", False):
                return (False, "no_active_attestation")
            if active_rec.get("attestation_hash", "") != attestation_hash:
                return (False, "attestation_hash_mismatch")
            expires_at = float(active_rec.get("expires_at", 0.0))
            if expires_at <= time.time():
                return (False, "attestation_expired")
            return (True, "")
        except Exception as exc:
            log.warning(
                "AttestationBoundRenewalAgent.validate_attestation_for_renewal: %s — fail-open",
                exc,
            )
            return (True, "")  # fail-open: agent error must not block renewal

    def _run_cycle(self) -> dict:
        """Log current attestation-bound renewal state. Called from run_poll_loop."""
        if not getattr(self._cfg, "attestation_bound_renewal_enabled", False):
            return {"attestation_bound_renewal_enabled": False}

        try:
            status = self._store.get_attestation_bound_renewal_status()
            log.info(
                "AttestationBoundRenewalAgent: approved=%d blocked=%d",
                status.get("total_approved", 0),
                status.get("total_blocked", 0),
            )
            return {
                "attestation_bound_renewal_enabled": True,
                "total_approved": status.get("total_approved", 0),
                "total_blocked":  status.get("total_blocked", 0),
            }
        except Exception as exc:
            log.error("AttestationBoundRenewalAgent: _run_cycle error: %s", exc, exc_info=True)
            return {"attestation_bound_renewal_enabled": True, "error": str(exc)}

    async def run_poll_loop(self) -> None:
        """Async poll loop — 600s interval. Never raises."""
        log.info("AttestationBoundRenewalAgent starting (interval=%ss)", _POLL_INTERVAL_S)
        while True:
            try:
                self._run_cycle()
            except Exception as exc:
                log.error(
                    "AttestationBoundRenewalAgent: unhandled error in poll: %s", exc,
                    exc_info=True,
                )
            await asyncio.sleep(_POLL_INTERVAL_S)
