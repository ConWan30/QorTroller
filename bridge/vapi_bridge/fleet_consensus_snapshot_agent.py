"""
Phase 157 — FleetConsensusSnapshotAgent (agent #21)

Computes PoFC (Proof of Fleet Consensus) snapshots: a SHA-256 hash of the
current agent fleet's verdict state + separation ratio + timestamp.

PoFC_hash = SHA-256(
    JSON(sorted((device_id, verdict) pairs from recent agent_rulings))
    + "|" + str(separation_ratio)
    + "|" + str(ts_ns)
)

This is the third composable proof primitive alongside PoAC (physiological
cognition) and PoAd (adjudication registry). Composable quadruple with
PoHBG (Phase 158) as fourth.

Poll interval: 30 minutes (fleet_consensus_snapshot_interval_s=1800).
Never raises from run_poll_loop().
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time

log = logging.getLogger(__name__)


class FleetConsensusSnapshotAgent:
    """
    Agent #21 — FleetConsensusSnapshotAgent.

    Reads:
        - store.get_agent_rulings(): recent autonomous ruling verdicts
        - store.get_separation_defensibility_status(): current separation ratio

    Computes:
        - PoFC_hash = SHA-256(sorted_verdicts_json | ratio_str | ts_ns_str)
        - verdict_summary = per-verdict count breakdown

    Stores:
        - fleet_consensus_snapshot_log (Phase 157)

    Publishes:
        - fleet_consensus_snapshot_created bus event
    """

    def __init__(self, cfg, store, bus=None) -> None:
        self._cfg   = cfg
        self._store = store
        self._bus   = bus

    # ------------------------------------------------------------------
    # PoFC computation
    # ------------------------------------------------------------------

    @staticmethod
    def compute_pofc_hash(
        sorted_verdicts: list[tuple[str, str]],
        separation_ratio: float,
        ts_ns: int,
    ) -> str:
        """Compute PoFC hash (Phase 157/WIF-013).

        Args:
            sorted_verdicts: list of (device_id, verdict) tuples, pre-sorted
            separation_ratio: current separation ratio from defensibility log
            ts_ns: current time in nanoseconds

        Returns:
            64-char lowercase hex SHA-256 digest
        """
        payload = (
            json.dumps(sorted_verdicts, separators=(",", ":"))
            + "|"
            + str(round(separation_ratio, 6))
            + "|"
            + str(ts_ns)
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _collect_snapshot(self) -> dict:
        """Collect current fleet verdict state and compute PoFC hash."""
        ts_ns = time.time_ns()

        # Collect recent verdicts from autonomous agent rulings
        verdicts: list[tuple[str, str]] = []
        try:
            rulings = self._store.get_agent_rulings(limit=50)
            for r in rulings:
                device_id = r.get("device_id", "") or ""
                verdict   = r.get("verdict", "UNKNOWN") or "UNKNOWN"
                if device_id:
                    verdicts.append((device_id, verdict))
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        sorted_verdicts = sorted(set(verdicts))

        # Collect separation ratio
        separation_ratio = 0.0
        try:
            def_status = self._store.get_separation_defensibility_status(
                session_type="touchpad_corners"
            )
            if def_status:
                separation_ratio = float(def_status.get("ratio", 0.0))
        except Exception:
            try:
                separation_ratio = float(
                    getattr(self._cfg, "separation_ratio_current", 0.0)
                )
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        # Compute PoFC hash
        pofc_hash = self.compute_pofc_hash(sorted_verdicts, separation_ratio, ts_ns)

        # Verdict summary breakdown
        verdict_summary: dict[str, int] = {}
        for _, v in sorted_verdicts:
            verdict_summary[v] = verdict_summary.get(v, 0) + 1

        return {
            "pofc_hash":         pofc_hash,
            "agent_count":       len(sorted_verdicts),
            "separation_ratio":  separation_ratio,
            "verdict_summary":   verdict_summary,
            "ts_ns":             ts_ns,
        }

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    async def run_poll_loop(self) -> None:
        """30-minute poll loop — computes and persists PoFC snapshots."""
        poll_s = int(getattr(self._cfg, "fleet_consensus_snapshot_interval_s", 1800))
        # Phase 235.x-STABILITY-9 stage 5 2026-05-17: startup-jitter.
        from .startup_grace import startup_grace
        await startup_grace(self._cfg, agent_name="FleetConsensusSnapshotAgent")
        while True:
            try:
                snap = self._collect_snapshot()
                self._store.insert_fleet_consensus_snapshot(
                    pofc_hash        = snap["pofc_hash"],
                    agent_count      = snap["agent_count"],
                    separation_ratio = snap["separation_ratio"],
                    verdict_summary  = snap["verdict_summary"],
                )

                if self._bus is not None:
                    try:
                        self._bus.publish_sync("fleet_consensus_snapshot_created", {
                            "pofc_hash":        snap["pofc_hash"],
                            "agent_count":      snap["agent_count"],
                            "separation_ratio": snap["separation_ratio"],
                            "ts":               time.time(),
                        })
                    except Exception:
                        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

                log.debug(
                    "[FleetConsensusSnapshotAgent] PoFC=%s... agents=%d ratio=%.3f",
                    snap["pofc_hash"][:12],
                    snap["agent_count"],
                    snap["separation_ratio"],
                )
            except Exception:
                log.debug("[FleetConsensusSnapshotAgent] poll error", exc_info=True)

            await asyncio.sleep(poll_s)
