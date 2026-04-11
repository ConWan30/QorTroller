"""
Phase 185 — ReEnrollmentAttestationAgent (agent #29)

Subscribes to the persona_break bus event (via polling store). When
PersonaBreakDetectorAgent records persona_break_detected=True for any player
and no active attestation already exists for that player, issues a time-bound
HMAC-SHA256 attestation hash that cryptographically authorizes the re-enrollment
window.

WIF-032 W1 CLOSED:
  The re-enrollment window is now gated by an unforgeable HMAC token.
  Adversary cannot forge the attestation without the operator secret
  (REAUTH_ATTESTATION_SECRET env var), even with full API read access to
  persona-break-status, age-weight-analysis-status, etc.

Hash formula:
  msg = f"{player_id}:{ts_ns}:{loo_trend:.6f}:{tdi:.6f}:{ttl_days}"
  When secret set:  HMAC-SHA256(secret, msg.encode()) → "hmac:<hex>"
  When secret empty: SHA-256(msg.encode()) → "sha256:<hex>"  (test mode only)

TTL: configurable (default 7 days). Operator must complete re-enrollment within
this window. After expiry, a fresh persona_break detection event is required.

Poll interval: 600s (10 minutes).
Fail-open: errors → warning logged, no attestation issued (never block on error).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac as _hmac_mod
import logging
import time

log = logging.getLogger(__name__)

# Default TTL in days for re-enrollment attestation tokens
_DEFAULT_TTL_DAYS = 7.0

# Poll interval in seconds
_POLL_INTERVAL_S = 600


class ReEnrollmentAttestationAgent:
    """
    Agent #29 — ReEnrollmentAttestationAgent.

    Reads:
        - store.get_persona_break_status(): latest persona break detection
        - store.get_active_attestation(player_id): existing active attestation

    Computes:
        - attestation_hash: HMAC-SHA256(secret, msg) or SHA-256(msg) in test mode
        - hmac_mode: True when operator secret is configured

    Stores:
        - persona_break_attestation_log (Phase 185)

    Publishes (via bus.publish_sync):
        - reenrollment_authorized bus event when new attestation issued
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus
        secret_str = getattr(cfg, "reauth_attestation_secret", "") or ""
        self._secret = secret_str.encode() if secret_str else b""

    # ------------------------------------------------------------------
    # Attestation hash computation
    # ------------------------------------------------------------------

    def _compute_attestation_hash(
        self,
        player_id: str,
        ts_ns: int,
        loo_trend: float,
        tdi: float,
        ttl_days: float,
    ) -> tuple[str, bool]:
        """Return (attestation_hash, hmac_mode).

        HMAC-SHA256 when operator secret configured (hmac_mode=True).
        Falls back to SHA-256 when secret empty (test mode, hmac_mode=False).
        Prefix encodes hash type for downstream consumers.
        """
        msg = f"{player_id}:{ts_ns}:{loo_trend:.6f}:{tdi:.6f}:{ttl_days}".encode()
        if self._secret:
            h = _hmac_mod.new(self._secret, msg, hashlib.sha256).hexdigest()
            return (f"hmac:{h}", True)
        else:
            h = hashlib.sha256(msg).hexdigest()
            return (f"sha256:{h}", False)

    # ------------------------------------------------------------------
    # Attestation issuance
    # ------------------------------------------------------------------

    def _issue_attestation_if_needed(self, player_id: str, break_status: dict) -> bool:
        """Check if player needs a fresh attestation; issue one if so.

        Returns True when a new attestation was issued.
        Skips when an active non-expired attestation already exists.
        """
        try:
            existing = self._store.get_active_attestation(player_id)
            if existing.get("active", False):
                log.debug(
                    "ReEnrollmentAttestationAgent: player %s already has active attestation "
                    "(expires=%.0f)", player_id, existing.get("expires_at", 0.0),
                )
                return False

            loo_trend = float(break_status.get("loo_accuracy_trend", 0.0))
            tdi = float(break_status.get("tdi_current", 0.0))
            ttl = float(getattr(self._cfg, "reauth_attestation_ttl_days", _DEFAULT_TTL_DAYS))
            ts_ns = time.time_ns()
            attest_hash, hmac_mode = self._compute_attestation_hash(
                player_id, ts_ns, loo_trend, tdi, ttl
            )
            now = time.time()
            expires_at = now + ttl * 86400.0

            self._store.insert_persona_break_attestation(
                player_id=player_id,
                hash=attest_hash,
                loo_trend=loo_trend,
                tdi=tdi,
                ttl_days=ttl,
                issued_at=now,
                expires_at=expires_at,
            )

            log.info(
                "ReEnrollmentAttestationAgent: issued attestation for player=%s "
                "hmac_mode=%s ttl_days=%.1f expires=%.0f",
                player_id, hmac_mode, ttl, expires_at,
            )

            # Publish bus event
            if self._bus is not None:
                try:
                    self._bus.publish_sync("reenrollment_authorized", {
                        "player_id":        player_id,
                        "attestation_hash": attest_hash,
                        "expires_at":       expires_at,
                        "hmac_mode":        hmac_mode,
                        "ts":               now,
                    }, source="reenrollment_attestation_agent")
                except Exception as exc:
                    log.debug("ReEnrollmentAttestationAgent: bus publish error: %s", exc)

            return True
        except Exception as exc:
            log.warning(
                "ReEnrollmentAttestationAgent: attestation issuance failed for player=%s: %s",
                player_id, exc,
            )
            return False

    def _run_cycle(self) -> dict:
        """Execute one assessment cycle. Called from run_poll_loop. Never raises."""
        if not getattr(self._cfg, "reauth_attestation_enabled", True):
            return {"reauth_attestation_enabled": False}

        issued_count = 0
        expired_count = 0
        try:
            # Expire stale attestations
            expired_count = self._store.expire_stale_attestations()
            if expired_count:
                log.info("ReEnrollmentAttestationAgent: expired %d stale attestations", expired_count)

            # Check latest persona break status (per-player and overall)
            break_status = self._store.get_persona_break_status()
            if break_status.get("persona_break_detected", False):
                player_id = break_status.get("player_id", "")
                if player_id:
                    if self._issue_attestation_if_needed(player_id, break_status):
                        issued_count += 1
        except Exception as exc:
            log.error(
                "ReEnrollmentAttestationAgent: unhandled error in _run_cycle: %s", exc,
                exc_info=True,
            )

        return {
            "reauth_attestation_enabled": True,
            "attestations_issued":        issued_count,
            "attestations_expired":       expired_count,
        }

    async def run_poll_loop(self) -> None:
        """Async poll loop — 600s interval. Never raises."""
        log.info("ReEnrollmentAttestationAgent starting (interval=%ss)", _POLL_INTERVAL_S)
        while True:
            try:
                self._run_cycle()
            except Exception as exc:
                log.error(
                    "ReEnrollmentAttestationAgent: unhandled error in poll: %s", exc,
                    exc_info=True,
                )
            await asyncio.sleep(_POLL_INTERVAL_S)
