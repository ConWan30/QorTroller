"""Data Economy Arc 3 Commit 1 — CuratorPackagingLoop core.

The operational core of the Data Economy flywheel: post-session, the Curator
reads the gamer's local session aggregate, enforces the gamer's consent manifest,
applies the protocol's aggregation / cooling / data floors, and prepares a
listing decision. It NEVER touches raw biometric data and NEVER bypasses the
consent policy.

This Commit-1 file ships the orchestration skeleton + the three floors + the
consent-manifest loader + autonomy routing + audit/session-log writes. The ZK
proof generation, category encryption, and actual marketplace submission are
Commit 2; the pending-listings endpoints are Commit 3.

SAFETY POSTURE (the load-bearing part — mirrors CuratorAttestationModule):
  * DORMANT by default. ``cfg.curator_packaging_enabled`` defaults False; while
    off, on_session_complete() returns a DISABLED result without reading any
    session data or contacting the chain.
  * FAIL-OPEN on operational faults (missing session data, store unavailable,
    aggregation/cooling not met) — these DEFER, they do not error. A deferral is
    a normal, expected outcome, logged at INFO, never a failure.
  * FAIL-CLOSED on consent integrity. If the gamer's consent manifest is missing
    or its claimed hash does not match the on-chain authority, packaging ABORTS.
    A tampered or absent consent policy must never result in a listing.
  * NO autonomous on-chain action. Even at full_autonomy the loop only computes a
    listing DECISION and records listing INTENT locally; the actual marketplace
    submission is dry-run-defaulted + kill-switch-gated + operator-fired (Commit
    2). full_autonomy means "no human approval step in the queue", NOT "broadcast
    a transaction without the operator".

DATA FLOOR (protocol invariant, framework §9.3 — immutable, no consent config
bypasses it): the raw fields below are NEVER packageable. _apply_data_floor
raises ProtocolViolationError if any appears in a session aggregate.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Optional

log = logging.getLogger(__name__)


class ProtocolViolationError(Exception):
    """Raised when the immutable data floor is violated — a raw biometric field
    reached the packaging path. This is never recoverable by configuration."""


class ConsentTamperError(Exception):
    """Raised when a consent manifest is missing or its claimed hash does not
    match the on-chain authority. Packaging fails closed — no listing."""


# ── FROZEN protocol floors (framework §9.3 / §10.5) ──────────────────────────

# Raw biometric fields that may NEVER be packaged under any consent configuration.
FORBIDDEN_FIELDS = frozenset({
    "raw_mahalanobis_vector",
    "raw_trigger_force_curves",
    "raw_imu_samples",
    "raw_hid_frames",
})

MIN_SESSIONS_DEFAULT = 10        # aggregation floor (framework §9.3 / consent floor)
COOLING_HOURS_DEFAULT = 72       # temporal cooling floor

# Autonomy levels (framework §8 Arc 3). approval_required is the DEFAULT for any
# gamer manifest — a new manifest is NEVER initialised at full_autonomy (§10.5).
AUTONOMY_APPROVAL_REQUIRED = "approval_required"
AUTONOMY_NOTIFY_ONLY = "notify_only"
AUTONOMY_FULL = "full_autonomy"
AUTONOMY_MANUAL = "manual"
_VALID_AUTONOMY = frozenset({
    AUTONOMY_APPROVAL_REQUIRED, AUTONOMY_NOTIFY_ONLY,
    AUTONOMY_FULL, AUTONOMY_MANUAL,
})

# on_session_complete outcome codes.
OUTCOME_DISABLED = "DISABLED"
OUTCOME_DEFERRED_AGGREGATION = "DEFERRED_AGGREGATION"
OUTCOME_DEFERRED_COOLING = "DEFERRED_COOLING"
OUTCOME_ABORTED_CONSENT = "ABORTED_CONSENT"
OUTCOME_ABORTED_NO_SESSION = "ABORTED_NO_SESSION"
OUTCOME_PENDING_APPROVAL = "PENDING_APPROVAL"
OUTCOME_READY_FOR_SUBMISSION = "READY_FOR_SUBMISSION"


class CuratorPackagingLoop:
    """Post-session data packaging orchestrator (Arc 3 Commit 1 core).

    Construct with the live ChainClient and Config; pass an optional store for
    session-data reads + durable packaging/audit persistence.
    """

    def __init__(self, chain: Any, cfg: Any, store: Optional[Any] = None) -> None:
        self._chain = chain
        self._cfg = cfg
        self._store = store
        self._enabled = bool(getattr(cfg, "curator_packaging_enabled", False))
        self._registry_address = (getattr(cfg, "consent_registry_address", "") or "")
        # Local audit surface (operational truth alongside any store persistence).
        self.audit_log: list[dict] = []
        if self._enabled:
            log.info(
                "[CURATOR] Packaging loop active. Raw biometric data never "
                "packaged. Consent policy enforced per manifest hash. Listing "
                "submission remains dry-run-defaulted + operator-fired."
            )

    # ── floors ────────────────────────────────────────────────────────────────

    def _apply_data_floor(self, session_data: dict) -> dict:
        """Strip-and-verify the immutable data floor. Raises ProtocolViolationError
        if any forbidden raw field is present. No consent config bypasses this."""
        for field_name in FORBIDDEN_FIELDS:
            if field_name in session_data:
                raise ProtocolViolationError(
                    f"Data floor violation: {field_name} cannot be packaged "
                    "under any configuration (framework §9.3, immutable)"
                )
        return session_data

    def _check_aggregation_floor(
        self, device_id: str, min_sessions: int = MIN_SESSIONS_DEFAULT
    ) -> tuple[bool, int]:
        """Return (ok, have). ok=True iff >= min_sessions packageable sessions
        exist for the device. Below the floor → (False, have): DEFER, do not fail.
        Never packages individual sessions below the floor."""
        have = 0
        if self._store is not None and hasattr(self._store, "count_packageable_sessions"):
            try:
                have = int(self._store.count_packageable_sessions(device_id))
            except Exception:
                log.exception("count_packageable_sessions failed (treat as 0)")
                have = 0
        return (have >= int(min_sessions), have)

    def _check_cooling_period(
        self, session_ended_at: float, cooling_hours: int = COOLING_HOURS_DEFAULT,
        now: Optional[float] = None,
    ) -> tuple[bool, float]:
        """Return (ok, available_at). ok=True iff the session is older than the
        cooling window. Within the window → (False, available_at): DEFER."""
        now = time.time() if now is None else now
        available_at = float(session_ended_at) + int(cooling_hours) * 3600.0
        return (now >= available_at, available_at)

    # ── consent ─────────────────────────────────────────────────────────────

    def _load_consent_manifest(self, device_id: str) -> dict:
        """Load the gamer's consent manifest and verify it against the on-chain
        authority. FAIL-CLOSED: missing manifest or hash mismatch raises
        ConsentTamperError. No listing is ever produced from an unverified policy.

        In Arc 3 (pre-Arc-4) the manifest is the local consent record carrying a
        ``manifest_hash`` claim; the on-chain authority is the VAPIConsentRegistry
        record hash. When the registry address is unset (dormant on-chain consent,
        framework §7 fail-open posture) the local manifest is operational truth and
        the on-chain comparison is skipped — but the manifest must still EXIST.
        Arc 4 replaces the opaque hash with the structured 7-dimension manifest.
        """
        manifest = None
        if self._store is not None and hasattr(self._store, "get_curator_consent_manifest"):
            try:
                manifest = self._store.get_curator_consent_manifest(device_id)
            except Exception:
                log.exception("get_curator_consent_manifest failed")
                manifest = None
        if not manifest:
            raise ConsentTamperError(
                f"no consent manifest for device {device_id[:16]} — fail closed"
            )

        autonomy = str(manifest.get("autonomy_level", AUTONOMY_APPROVAL_REQUIRED))
        if autonomy not in _VALID_AUTONOMY:
            raise ConsentTamperError(
                f"invalid autonomy_level {autonomy!r} in manifest — fail closed"
            )

        claimed_hash = manifest.get("manifest_hash")
        if self._registry_address and claimed_hash is not None:
            on_chain_hash = self._on_chain_consent_hash(device_id)
            if on_chain_hash is not None and str(on_chain_hash) != str(claimed_hash):
                raise ConsentTamperError(
                    f"consent manifest hash mismatch for device {device_id[:16]}: "
                    f"claimed {str(claimed_hash)[:18]} != on-chain "
                    f"{str(on_chain_hash)[:18]} — fail closed"
                )
        return dict(manifest)

    def _on_chain_consent_hash(self, device_id: str) -> Optional[str]:
        """Read the on-chain consent manifest hash (fail-open None on any fault —
        a read error must not block, but a *mismatch* in _load_consent_manifest
        does)."""
        if self._chain is None:
            return None
        getter = getattr(self._chain, "get_consent_manifest_hash", None)
        if getter is None:
            return None
        try:
            return getter(device_id)
        except Exception:
            log.exception("on-chain consent manifest hash read failed (fail-open None)")
            return None

    # ── orchestration ─────────────────────────────────────────────────────────

    async def on_session_complete(self, session_id: str) -> dict:
        """Main entry point — called from the session boundary.

        Returns a result dict {outcome, session_id, ...}. Never raises for normal
        operational outcomes (disabled / deferral / no session); raises only on a
        true protocol fault (data floor) or consent tamper, which the caller logs.
        """
        if not self._enabled:
            return {"outcome": OUTCOME_DISABLED, "session_id": session_id,
                    "reason": "curator_packaging_enabled=False (dormant)"}

        session = self._load_session(session_id)
        if not session:
            self._audit("packaging", session_id, OUTCOME_ABORTED_NO_SESSION, {})
            return {"outcome": OUTCOME_ABORTED_NO_SESSION, "session_id": session_id}

        device_id = str(session.get("device_id", ""))

        # Step 1-2: consent manifest — fail closed on tamper/absence.
        manifest = self._load_consent_manifest(device_id)
        autonomy = str(manifest.get("autonomy_level", AUTONOMY_APPROVAL_REQUIRED))
        min_sessions = int(manifest.get("min_sessions", MIN_SESSIONS_DEFAULT))
        cooling_hours = int(manifest.get("cooling_hours", COOLING_HOURS_DEFAULT))

        # Step 6: data floor — protocol invariant, before any further work.
        self._apply_data_floor(session)

        # Step 4: aggregation floor — defer (not fail) below N.
        agg_ok, have = self._check_aggregation_floor(device_id, min_sessions)
        if not agg_ok:
            log.info("DEFER: insufficient sessions for aggregation (have %d, need %d)",
                     have, min_sessions)
            self._audit("packaging", session_id, OUTCOME_DEFERRED_AGGREGATION,
                        {"have": have, "need": min_sessions})
            return {"outcome": OUTCOME_DEFERRED_AGGREGATION, "session_id": session_id,
                    "have": have, "need": min_sessions}

        # Step 5: temporal cooling — defer (not fail) within window.
        ended_at = float(session.get("ended_at", session.get("created_at", 0.0)) or 0.0)
        cool_ok, available_at = self._check_cooling_period(ended_at, cooling_hours)
        if not cool_ok:
            log.info("DEFER: cooling period active until %s", available_at)
            self._audit("packaging", session_id, OUTCOME_DEFERRED_COOLING,
                        {"available_at": available_at})
            return {"outcome": OUTCOME_DEFERRED_COOLING, "session_id": session_id,
                    "available_at": available_at}

        # Step 7 (Commit 2): ZK proof generation + category encryption — deferred.
        # Step 8: autonomy routing — compute the listing DECISION (no broadcast).
        return self._route_by_autonomy(session_id, device_id, manifest, autonomy)

    def _route_by_autonomy(self, session_id: str, device_id: str,
                           manifest: dict, autonomy: str) -> dict:
        """Compute the listing decision per the gamer's autonomy level. NEVER
        broadcasts — approval_required queues for the gamer; full_autonomy /
        notify_only mark the package READY_FOR_SUBMISSION (the actual marketplace
        tx is Commit 2's dry-run-gated + operator-fired path)."""
        consent_policy_hash = manifest.get("manifest_hash")
        listing_intent = {
            "session_id": session_id,
            "device_id": device_id,
            "autonomy_level": autonomy,
            "consent_policy_hash": consent_policy_hash,
            "allowed_categories": list(manifest.get("allowed_categories", [])),
            "ts_ns": time.time_ns(),
        }
        if autonomy in (AUTONOMY_APPROVAL_REQUIRED, AUTONOMY_MANUAL):
            self._enqueue_pending_listing(listing_intent)
            self._audit("packaging", session_id, OUTCOME_PENDING_APPROVAL,
                        {"consent_policy_hash": consent_policy_hash})
            return {"outcome": OUTCOME_PENDING_APPROVAL, "session_id": session_id,
                    "listing_intent": listing_intent}
        # notify_only / full_autonomy: no human approval step, but still NOT an
        # autonomous broadcast — mark ready for the operator-fired submission.
        self._record_listing_intent(listing_intent)
        self._audit("packaging", session_id, OUTCOME_READY_FOR_SUBMISSION,
                    {"consent_policy_hash": consent_policy_hash, "autonomy": autonomy})
        return {"outcome": OUTCOME_READY_FOR_SUBMISSION, "session_id": session_id,
                "listing_intent": listing_intent}

    # ── persistence helpers (all optional / non-fatal) ────────────────────────

    def _load_session(self, session_id: str) -> Optional[dict]:
        if self._store is not None and hasattr(self._store, "get_curator_session_aggregate"):
            try:
                return self._store.get_curator_session_aggregate(session_id)
            except Exception:
                log.exception("get_curator_session_aggregate failed")
        return None

    def _enqueue_pending_listing(self, listing_intent: dict) -> None:
        if self._store is not None and hasattr(self._store, "insert_pending_listing"):
            try:
                self._store.insert_pending_listing(listing_intent)
            except Exception:
                log.exception("insert_pending_listing failed (non-fatal)")

    def _record_listing_intent(self, listing_intent: dict) -> None:
        if self._store is not None and hasattr(self._store, "record_curator_listing_intent"):
            try:
                self._store.record_curator_listing_intent(listing_intent)
            except Exception:
                log.exception("record_curator_listing_intent failed (non-fatal)")

    def _audit(self, action: str, session_id: str, outcome: str, extra: dict) -> None:
        entry = {
            "action": action,
            "session_id": session_id,
            "outcome": outcome,
            "extra": dict(extra) if extra else {},
            "ts_ns": time.time_ns(),
        }
        self.audit_log.append(entry)
        if self._store is not None and hasattr(self._store, "record_curator_packaging_action"):
            try:
                self._store.record_curator_packaging_action(entry)
            except Exception:
                log.exception("record_curator_packaging_action failed (non-fatal)")
        if self._store is not None and hasattr(self._store, "update_curator_session_status"):
            try:
                self._store.update_curator_session_status(session_id, outcome)
            except Exception:
                log.exception("update_curator_session_status failed (non-fatal)")
