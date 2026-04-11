"""
Phase 176 — PoACChainIntegrityMonitor (agent #25)

Audits PoAC record chain linkage across the local DB.
For each device, verifies that records form a contiguous counter sequence
(counter N is followed by counter N+1). Gaps in the sequence indicate
missing or dropped records — a potential chain break.

integrity_score = valid_links / total_records  (1.0 = fully intact)
audit_passed    = (broken_links == 0)
vacuous case    = total_records == 0 → integrity_score = 1.0, audit_passed = True

W1 mitigation (WIF-026): only aggregate counts are returned — no broken
record IDs are exposed to the API, preventing adversaries from learning
which specific records were dropped.

Poll interval: 600s (10 minutes).
Fail-safe: errors → full integrity defaults (fail-open; never blocks tournament gate).
"""

from __future__ import annotations

import asyncio
import logging
import time

log = logging.getLogger(__name__)


class PoACChainIntegrityMonitor:
    """Agent #25 — PoACChainIntegrityMonitor.

    Reads:
        store records table — device_id, counter, record_hash columns.

    Computes:
        total_records   = total rows for device (or all devices)
        valid_links     = consecutive (counter, counter+1) pairs
        broken_links    = total_records - valid_links - 1  (first record has no prev)
        integrity_score = valid_links / max(total_records - 1, 1)
        audit_passed    = (broken_links == 0)

    Stores:
        poac_chain_audit_log (Phase 176)

    Publishes:
        pir_chain_broken bus event when audit_passed=False
    """

    _POLL_INTERVAL_S = 600

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # Chain audit logic
    # ------------------------------------------------------------------

    def _audit_device(self, device_id: str | None) -> dict:
        """Audit chain integrity for one device (or all if device_id=None).

        Returns dict with total_records, valid_links, broken_links,
        integrity_score, audit_passed.
        """
        try:
            with self._store._connect() as conn:
                if device_id:
                    rows = conn.execute(
                        "SELECT counter FROM records "
                        "WHERE device_id = ? ORDER BY counter ASC",
                        (device_id,),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT counter FROM records ORDER BY counter ASC"
                    ).fetchall()
        except Exception as exc:
            log.warning("PoACChainIntegrityMonitor: DB read error: %s", exc)
            return {
                "total_records":  0,
                "valid_links":    0,
                "broken_links":   0,
                "integrity_score": 1.0,
                "audit_passed":   True,
            }

        counters = [r[0] for r in rows]
        total    = len(counters)

        if total <= 1:
            return {
                "total_records":  total,
                "valid_links":    max(0, total - 1),
                "broken_links":   0,
                "integrity_score": 1.0,
                "audit_passed":   True,
            }

        valid_links = sum(
            1 for i in range(len(counters) - 1)
            if counters[i + 1] == counters[i] + 1
        )
        # Each consecutive pair is one potential link; there are total-1 pairs.
        possible_links = total - 1
        broken_links   = possible_links - valid_links
        integrity_score = round(valid_links / possible_links, 6) if possible_links > 0 else 1.0
        audit_passed    = (broken_links == 0)

        return {
            "total_records":  total,
            "valid_links":    valid_links,
            "broken_links":   broken_links,
            "integrity_score": integrity_score,
            "audit_passed":   audit_passed,
        }

    def _get_primary_device_id(self) -> str | None:
        """Return the most-recently-seen device_id, or None for all."""
        try:
            with self._store._connect() as conn:
                row = conn.execute(
                    "SELECT device_id FROM records "
                    "ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                return row[0] if row else None
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Poll logic
    # ------------------------------------------------------------------

    def _run_audit(self) -> dict:
        """Run one chain integrity audit cycle.

        Returns summary dict. Fail-safe: errors → full integrity defaults.
        """
        enabled = bool(getattr(self._cfg, "chain_integrity_enabled", True))
        if not enabled:
            return {"chain_integrity_enabled": False, "audit_passed": True}

        try:
            device_id = self._get_primary_device_id()
            result    = self._audit_device(device_id)

            self._store.insert_poac_chain_audit_log(
                device_id=device_id or "all",
                total_records=result["total_records"],
                valid_links=result["valid_links"],
                broken_links=result["broken_links"],
            )

            if not result["audit_passed"] and self._bus is not None:
                try:
                    self._bus.publish("pir_chain_broken", {
                        "source":         "PoACChainIntegrityMonitor",
                        "device_id":      device_id or "all",
                        "broken_links":   result["broken_links"],
                        "integrity_score": result["integrity_score"],
                        "ts":             time.time(),
                    })
                except Exception as exc:
                    log.debug("PoACChainIntegrityMonitor: bus publish error: %s", exc)

            log.info(
                "PoACChainIntegrityMonitor: device=%s total=%d valid=%d broken=%d score=%.4f passed=%s",
                device_id or "all",
                result["total_records"],
                result["valid_links"],
                result["broken_links"],
                result["integrity_score"],
                result["audit_passed"],
            )

            return {
                "chain_integrity_enabled": True,
                **result,
                "device_id": device_id or "all",
            }

        except Exception as exc:
            log.error(
                "PoACChainIntegrityMonitor: audit error: %s", exc, exc_info=True
            )
            return {
                "chain_integrity_enabled": True,
                "total_records":  0,
                "valid_links":    0,
                "broken_links":   0,
                "integrity_score": 1.0,
                "audit_passed":   True,
            }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """Async poll loop — 600s interval. Never raises."""
        log.info("PoACChainIntegrityMonitor starting (interval=%ss)", self._POLL_INTERVAL_S)
        while True:
            try:
                self._run_audit()
            except Exception as exc:
                log.error(
                    "PoACChainIntegrityMonitor: unhandled poll error: %s", exc, exc_info=True
                )
            await asyncio.sleep(self._POLL_INTERVAL_S)
