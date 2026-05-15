"""Phase O5-MLGA Stage 8 (CDRR-DAG autonomy) — fires on coherence re-rejection.

Fifth autonomous VPM artifact class. Wires `CDRR-DAG-v1` to fire when
FleetSignalCoherenceAgent records a HIGH or CRITICAL severity
contradiction — the "coherence rule re-rejection" trigger per
VBDIP-0002A §10.4.

Design discipline (mirrors prior trackers):
  • POLLING-based at 60s cadence (matches FSCA poll cycle).
  • Reads fleet_coherence_log; tracks max-seen id.
  • Emits one artifact per cycle if any new HIGH/CRITICAL rows
    landed since last poll (rate-limited; not one-per-row).
  • Opt-in via cfg.cdrr_dag_tracker_enabled (default True).
  • Fail-open; idempotent on restart via vpm_artifact_log scan.

The CDRR DAG renders the FROZEN composition lattice between the
seven ZKBA artifact classes + their cross-class references. The DAG
topology is FROZEN-v1 — no caller inputs control nodes/edges, so
every emission has the same input commitment. The artifact's value
is the EMISSION TRIGGER ITSELF: a CDRR-DAG row landing in
vpm_artifact_log is a cryptographically-timestamped acknowledgement
that the protocol observed a coherence re-rejection event in the
window before the emission timestamp.

WALLET-FREE; READ-ONLY against chain.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


_DEFAULT_POLL_INTERVAL_S: int = 60
_SEVERITIES_TRIGGERING = ("HIGH", "CRITICAL")


@dataclass(slots=True)
class CdrrDagState:
    """In-memory tracker state."""
    last_seen_coherence_id: int = 0
    emissions_this_session: int = 0
    last_emit_ts_ns:        int = 0


def _build_integrity_label(
    *, severity: str, rule_name: str, coherence_id: str,
) -> Dict[str, Any]:
    return {
        "proof_type":             "VPM-CDRR-DAG",
        "capture_mode":           "live",
        "raw_biometrics_exposed": False,
        "consent_active":         "n/a",
        "zk_verified":            False,
        "on_chain_anchor":        False,
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            f"Autonomous emission triggered by {severity} contradiction "
            f"rule={rule_name} coherence_id={coherence_id[:16]}; DAG "
            "topology is FROZEN-v1, content does not change between "
            "emissions — the emission timestamp IS the cryptographic "
            "acknowledgement of the re-rejection event.",
        ],
    }


class CdrrDagTracker:
    """Autonomous CDRR-DAG-v1 VPM emission tracker."""

    def __init__(
        self,
        *,
        store,
        cfg,
        poll_interval_s: Optional[int] = None,
    ) -> None:
        self._store = store
        self._cfg = cfg
        self._poll_interval_s = (
            poll_interval_s
            if poll_interval_s is not None
            else getattr(cfg, "cdrr_dag_poll_interval_s", _DEFAULT_POLL_INTERVAL_S)
        )
        self._state = CdrrDagState()
        self._state.last_seen_coherence_id = self._seed_last_seen()

    def _seed_last_seen(self) -> int:
        """Seed last_seen from existing vpm_artifact_log + fleet_coherence_log.

        Prefers the highest coherence_id we've already emitted (encoded
        in preimage_json). Falls back to current max coherence_id so a
        bridge restart doesn't replay every historical contradiction.
        """
        try:
            db_path = getattr(self._store, "_db_path", None) or getattr(
                self._store, "db_path", None
            )
            if not db_path:
                return 0
            con = sqlite3.connect(db_path, timeout=2.0)
            try:
                # Highest coherence_id we've emitted
                rows = con.execute(
                    "SELECT preimage_json FROM vpm_artifact_log "
                    "WHERE vpm_id='CDRR-DAG-v1'"
                ).fetchall()
                best = 0
                for r in rows:
                    if not r[0]:
                        continue
                    try:
                        d = json.loads(r[0])
                        cid = int(d.get("trigger_row_id", 0))
                        if cid > best:
                            best = cid
                    except Exception:
                        pass
                if best > 0:
                    return best
                # Fallback: don't replay history — start at current max
                row = con.execute(
                    "SELECT COALESCE(MAX(id), 0) FROM fleet_coherence_log"
                ).fetchone()
                cur_max = int(row[0] or 0) if row else 0
                if cur_max > 0:
                    log.info(
                        "CDRR-DAG tracker: seeded last_seen=%d (current "
                        "fleet_coherence_log max) — historical findings "
                        "skipped",
                        cur_max,
                    )
                return cur_max
            finally:
                con.close()
        except Exception as exc:  # noqa: BLE001
            log.warning("CDRR-DAG tracker: seed failed (%s); starting at 0", exc)
            return 0

    def poll_once(self) -> Dict[str, Any]:
        try:
            db_path = getattr(self._store, "_db_path", None) or getattr(
                self._store, "db_path", None
            )
            if not db_path:
                return {"action": "noop_no_db"}
            con = sqlite3.connect(db_path, timeout=2.0)
            try:
                con.row_factory = sqlite3.Row
                # Most recent HIGH/CRITICAL row newer than last_seen
                placeholders = ",".join(["?"] * len(_SEVERITIES_TRIGGERING))
                params = list(_SEVERITIES_TRIGGERING) + [
                    self._state.last_seen_coherence_id,
                ]
                row = con.execute(
                    f"SELECT id, rule_name, severity, coherence_id "
                    f"FROM fleet_coherence_log "
                    f"WHERE severity IN ({placeholders}) AND id > ? "
                    f"ORDER BY id DESC LIMIT 1",
                    params,
                ).fetchone()
            finally:
                con.close()
            if row is None:
                return {"action": "noop_no_new_findings"}
            return self._emit(trigger_row=dict(row))
        except Exception as exc:  # noqa: BLE001
            log.warning("CDRR-DAG tracker: poll error: %s", exc)
            return {"action": "error", "error": str(exc)}

    def _emit(self, *, trigger_row: Dict[str, Any]) -> Dict[str, Any]:
        try:
            rule_name = str(trigger_row.get("rule_name") or "UNKNOWN")
            severity = str(trigger_row.get("severity") or "HIGH")
            coherence_id = str(trigger_row.get("coherence_id") or "")
            trigger_row_id = int(trigger_row.get("id") or 0)

            integrity_label = _build_integrity_label(
                severity=severity,
                rule_name=rule_name,
                coherence_id=coherence_id,
            )

            ts_ns = time.time_ns()
            snapshot = {
                "vpm_id":          "CDRR-DAG-v1",
                "trigger_row_id":  trigger_row_id,
                "rule_name":       rule_name,
                "severity":        severity,
                "coherence_id":    coherence_id,
                "ts_ns":           ts_ns,
            }
            digest = hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
                .encode("utf-8")
            ).hexdigest()

            output_dir = (
                Path(__file__).resolve().parents[2]
                / "frontend" / "src" / "artifacts" / "cdrr_dag"
            )
            import sys as _sys
            _scripts_path = str(
                Path(__file__).resolve().parents[2] / "scripts"
            )
            if _scripts_path not in _sys.path:
                _sys.path.insert(0, _scripts_path)
            from vpm_compile_cdrr_dag import build_cdrr_dag_artifact

            manifest = build_cdrr_dag_artifact(
                integrity_label=integrity_label,
                zkba_manifest_hash_hex=digest,
                visual_state="live",
                capture_mode="live",
                output_dir=output_dir,
                ts_ns=ts_ns,
            )

            # CDRR-DAG's input commitment is FROZEN (DAG topology
            # doesn't change between emissions), so the OUTPUT
            # commitment is the same every time. Use the
            # trigger_row_id as a uniqueness suffix in the
            # zkba_manifest_hash_hex slot to give each row a distinct
            # commitment_hex (otherwise UNIQUE constraint blocks
            # repeat emissions).
            commitment_hex = hashlib.sha256(
                (manifest.output_hash_hex + ":" + str(trigger_row_id))
                .encode("utf-8")
            ).hexdigest()

            preimage_json = json.dumps(snapshot, sort_keys=True,
                                        separators=(",", ":"))
            row_id = self._store.insert_vpm_artifact(
                commitment_hex=commitment_hex,
                vpm_id="CDRR-DAG-v1",
                zkba_class=4,             # ZKBAClass.HARDWARE
                proof_weight=3,           # CHAIN_ONLY
                visual_state="live",
                capture_mode="live",
                integrity_label_hash_hex=manifest.integrity_label_hash_hex,
                wrapper_schema="vapi-vpm-artifact-v1",
                zkba_manifest_hash_hex=digest,
                manifest_uri=manifest.output_path,
                compiler_output_hash_hex=manifest.output_hash_hex,
                preimage_json=preimage_json,
                ts_ns=ts_ns,
            )

            self._state.last_seen_coherence_id = trigger_row_id
            self._state.emissions_this_session += 1
            self._state.last_emit_ts_ns = ts_ns
            log.info(
                "CDRR-DAG emitted: trigger=%s/%s row=%d coherence_id=%s...",
                severity, rule_name, row_id, coherence_id[:16],
            )
            return {
                "action": "emitted",
                "row": row_id,
                "trigger_row_id": trigger_row_id,
                "rule_name": rule_name,
            }
        except Exception as exc:  # noqa: BLE001
            import traceback as _tb
            log.warning(
                "CDRR-DAG emit failed: %s\n%s", exc, _tb.format_exc(),
            )
            # Advance past this trigger so we don't tight-loop.
            self._state.last_seen_coherence_id = int(
                trigger_row.get("id") or self._state.last_seen_coherence_id
            )
            return {"action": "error", "error": str(exc)}


async def run_cdrr_dag_tracker_loop(
    *, tracker: CdrrDagTracker, interval_s: Optional[int] = None,
) -> None:
    if interval_s is None:
        interval_s = tracker._poll_interval_s
    log.info(
        "Phase O5-MLGA Stage 8: CDRR-DAG tracker started (poll=%ds, "
        "seeded_at=%d)",
        interval_s, tracker._state.last_seen_coherence_id,
    )
    try:
        while True:
            tracker.poll_once()
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        log.info("CDRR-DAG tracker cancelled")
        raise
