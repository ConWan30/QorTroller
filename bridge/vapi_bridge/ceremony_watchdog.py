"""Phase 75 — CeremonyWatchdogAgent.

Monitors on-chain CeremonyRegistry for PitlSessionProof ceremony key rotation every
5 minutes. Detects changes by comparing beacon_block_number + contributor_count against
the last known fingerprint.

On key rotation:
  1. Invalidates _CEREMONY_CACHE in session_adjudicator.py
     (collapses 60-minute blind window to <5 minutes — W1 mitigation from Phase 75 WHAT_IF)
  2. Emits 'ceremony_key_rotated' agent_event
  3. Queues 'ceremony_integrity_recheck_required' events for any FLAG rulings from
     the last 10 minutes — operator is notified to re-review under the new key context

Never raises — all errors logged, watchdog continues polling.
"""

import asyncio
import json
import logging
import time

log = logging.getLogger(__name__)

_POLL_INTERVAL_S = 300  # 5 minutes — must be < _CEREMONY_CACHE_TTL_S (3600) to be useful
_PITL_CIRCUIT_NAME = "PitlSessionProof"

# Module-level last-known ceremony fingerprint (beacon_block_number + contributor_count).
# Populated on first successful poll. Changed => rotation detected.
_LAST_FINGERPRINT: dict = {}


class CeremonyWatchdogAgent:
    """Polls CeremonyRegistry and invalidates SA ceremony cache on key rotation (Phase 75)."""

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg = cfg
        self._store = store
        self._bus = bus
        self._registry_addr = getattr(cfg, "ceremony_registry_address", "")
        self._rpc_url = getattr(cfg, "iotex_rpc_url", "")

    async def run_event_consumer(self) -> None:
        """Background loop — polls CeremonyRegistry every 5 minutes."""
        log.info("CeremonyWatchdogAgent started (Phase 75) poll=%ds", _POLL_INTERVAL_S)
        _consecutive_failures = 0
        while True:
            try:
                await asyncio.sleep(_POLL_INTERVAL_S)
                await self._check_ceremony_integrity()
                _consecutive_failures = 0
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                _consecutive_failures += 1
                if _consecutive_failures >= 3:
                    log.error(
                        "CeremonyWatchdogAgent: %d consecutive failures: %s",
                        _consecutive_failures, exc,
                    )
                else:
                    log.warning("CeremonyWatchdogAgent: cycle error: %s", exc)

    async def _check_ceremony_integrity(self) -> None:
        """Fetch current ceremony fingerprint and detect rotation."""
        if not self._registry_addr or not self._rpc_url:
            log.debug("CeremonyWatchdogAgent: registry/rpc not configured — skipping")
            return

        try:
            from sdk.vapi_sdk import VAPIZKProof
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda: VAPIZKProof.verify_ceremony_integrity(
                    vkey_dict=None,
                    registry_addr=self._registry_addr,
                    rpc_url=self._rpc_url,
                    circuit_name=_PITL_CIRCUIT_NAME,
                ),
            )
        except Exception as exc:
            log.debug("CeremonyWatchdogAgent: registry call failed: %s", exc)
            return

        if result.get("error"):
            log.debug("CeremonyWatchdogAgent: registry unreachable: %s", result["error"])
            return

        current_fingerprint = {
            "beacon_block_number": result.get("beacon_block_number", 0),
            "contributor_count": result.get("contributor_count", 0),
        }

        global _LAST_FINGERPRINT
        if not _LAST_FINGERPRINT:
            _LAST_FINGERPRINT = current_fingerprint
            log.info(
                "CeremonyWatchdogAgent: baseline established "
                "beacon=%d contributors=%d",
                current_fingerprint["beacon_block_number"],
                current_fingerprint["contributor_count"],
            )
            return

        if current_fingerprint == _LAST_FINGERPRINT:
            log.debug("CeremonyWatchdogAgent: ceremony key unchanged")
            return

        # Key rotation detected
        old_fp = dict(_LAST_FINGERPRINT)
        _LAST_FINGERPRINT = current_fingerprint

        log.warning(
            "CeremonyWatchdogAgent: CEREMONY KEY ROTATION DETECTED "
            "old_beacon=%d new_beacon=%d old_contrib=%d new_contrib=%d",
            old_fp.get("beacon_block_number"),
            current_fingerprint["beacon_block_number"],
            old_fp.get("contributor_count"),
            current_fingerprint["contributor_count"],
        )

        self._invalidate_ceremony_cache()
        self._emit_rotation_event(old_fp, current_fingerprint)
        self._escalate_recent_flags()

    def _invalidate_ceremony_cache(self) -> None:
        """Clear _CEREMONY_CACHE via bus publication (Phase 79) or direct import fallback.

        Phase 79: publish ceremony_key_rotated to bus — SessionAdjudicator subscribes
        and clears its own cache, removing the fragile module-level import coupling.
        Fallback: direct import used when bus is unavailable (Phase 75 compatibility).
        """
        if self._bus is not None:
            import asyncio as _asyncio
            try:
                loop = _asyncio.get_event_loop()
                if loop.is_running():
                    _asyncio.ensure_future(
                        self._bus.publish(
                            "ceremony_key_rotated",
                            {
                                "source": "ceremony_watchdog_agent",
                                "ts": time.time(),
                            },
                            "ceremony_watchdog_agent",
                        )
                    )
                    log.info(
                        "CeremonyWatchdogAgent: ceremony_key_rotated published to bus"
                    )
                    return
            except Exception as exc:
                log.debug(
                    "CeremonyWatchdogAgent: bus publish failed, using direct fallback: %s", exc
                )
        # Fallback (Phase 75 compatibility): direct module import
        try:
            from . import session_adjudicator as _sa_mod
            _sa_mod._CEREMONY_CACHE.clear()
            log.info("CeremonyWatchdogAgent: _CEREMONY_CACHE invalidated (direct fallback)")
        except Exception as exc:
            log.warning("CeremonyWatchdogAgent: cache invalidation failed: %s", exc)

    def _emit_rotation_event(self, old_fp: dict, new_fp: dict) -> None:
        """Emit ceremony_key_rotated event to bridge_agent."""
        try:
            self._store.write_agent_event(
                event_type="ceremony_key_rotated",
                payload=json.dumps({
                    "old_beacon_block_number": old_fp.get("beacon_block_number"),
                    "new_beacon_block_number": new_fp["beacon_block_number"],
                    "old_contributor_count": old_fp.get("contributor_count"),
                    "new_contributor_count": new_fp["contributor_count"],
                    "circuit_name": _PITL_CIRCUIT_NAME,
                    "detected_at": time.time(),
                }),
                source="ceremony_watchdog_agent",
                target="bridge_agent",
                device_id="",
            )
        except Exception as exc:
            log.warning("CeremonyWatchdogAgent: event emission failed: %s", exc)

    def _escalate_recent_flags(self) -> None:
        """Queue recheck events for FLAG rulings from the last 10 minutes."""
        try:
            since = time.time() - 600  # last 10 minutes
            with self._store._conn() as conn:
                recent_flags = conn.execute(
                    "SELECT id, device_id FROM agent_rulings "
                    "WHERE verdict='FLAG' AND created_at > ?",
                    (since,),
                ).fetchall()
            for row in recent_flags:
                self._store.write_agent_event(
                    event_type="ceremony_integrity_recheck_required",
                    payload=json.dumps({
                        "ruling_id": row["id"],
                        "device_id": row["device_id"],
                        "reason": "ceremony_key_rotated_after_ruling",
                    }),
                    source="ceremony_watchdog_agent",
                    target="bridge_agent",
                    device_id=row["device_id"],
                )
            if recent_flags:
                log.warning(
                    "CeremonyWatchdogAgent: queued %d recent FLAG ruling(s) for recheck",
                    len(recent_flags),
                )
        except Exception as exc:
            log.warning("CeremonyWatchdogAgent: flag escalation failed: %s", exc)
