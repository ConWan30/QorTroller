"""Phase O5-MLGA Stage 6 (HONESTY-BOARD autonomy) — weekly self-report.

Third autonomous VPM artifact class after MLGA-SESSION-v1 + GIC-LEDGER-BETA-v1.
Wires `HONESTY-BOARD-v1` to fire on a weekly cadence, snapshotting protocol-
state honesty fields (fleet phase alignment, ZKBA class coverage, kill-switch
state, Cedar v2 anchor status, PV-CI invariant count, wallet balance,
last on-chain anchor).

Design discipline (mirrors mlga_session_tracker + gic_ledger_beta_tracker):
  • POLLING-based at 1h cadence; emission gated by 7-day interval.
  • NO FROZEN-region edits.
  • Opt-in via cfg.honesty_board_tracker_enabled (default True;
    wallet-free, local-only, idempotent on restart).
  • Single-task background coroutine; fail-open.
  • Idempotent: seeds last_emit_ts_ns from existing vpm_artifact_log
    rows on startup; emission gated by (now - last_emit) >= interval.

Snapshot semantics:
  • fleet_phase_aligned    — defaults False; pulled from cfg if wired
  • fleet_phase_target     — defaults "UNKNOWN"
  • zkba_class_coverage    — distinct zkba_class count in zkba_artifact_log
  • chain_submission_paused — cfg.chain_submission_paused flag
  • cedar_v2_bundles_anchored — count of operator_agent_activation_log rows
  • pv_ci_invariants_count — INVARIANTS_ALLOWLIST.json entry count
  • wallet_balance_iotx    — empty string if unreachable (chain optional)
  • last_anchor_tx_hash / last_anchor_block — latest activation log row

WALLET-FREE; READ-ONLY against chain (no submissions).
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


# Default polling cadence — check every hour; emit at 7-day boundary.
_DEFAULT_POLL_INTERVAL_S: int = 3600
_DEFAULT_EMISSION_INTERVAL_S: int = 7 * 24 * 3600   # 7 days


@dataclass(slots=True)
class HonestyBoardState:
    """In-memory tracker state."""
    last_emit_ts_ns:        int = 0
    emissions_this_session: int = 0


def _snapshot_inputs(*, store, cfg) -> Dict[str, Any]:
    """Pull HONESTY-BOARD inputs from existing sources with fail-open
    defaults. Never raises."""
    # ZKBA class coverage
    zkba_coverage = 0
    try:
        db_path = getattr(store, "_db_path", None) or getattr(
            store, "db_path", None
        )
        if db_path:
            con = sqlite3.connect(db_path, timeout=2.0)
            try:
                row = con.execute(
                    "SELECT COUNT(DISTINCT zkba_class) FROM zkba_artifact_log"
                ).fetchone()
                if row:
                    zkba_coverage = int(row[0] or 0)
            finally:
                con.close()
    except Exception:  # noqa: BLE001
        pass

    # Cedar v2 anchor count
    cedar_count = 0
    last_anchor_tx = ""
    last_anchor_block = 0
    try:
        db_path = getattr(store, "_db_path", None) or getattr(
            store, "db_path", None
        )
        if db_path:
            con = sqlite3.connect(db_path, timeout=2.0)
            try:
                con.row_factory = sqlite3.Row
                row = con.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_activation_log"
                ).fetchone()
                cedar_count = int(row["n"] or 0) if row else 0
                latest = con.execute(
                    "SELECT operational_tx_hash, operational_block_number "
                    "FROM operator_agent_activation_log "
                    "ORDER BY activated_at DESC LIMIT 1"
                ).fetchone()
                if latest:
                    last_anchor_tx = latest["operational_tx_hash"] or ""
                    last_anchor_block = int(
                        latest["operational_block_number"] or 0
                    )
            finally:
                con.close()
    except Exception:  # noqa: BLE001
        pass

    # PV-CI invariants — read allowlist JSON
    pv_ci_count = 0
    try:
        allowlist = (
            Path(__file__).resolve().parents[2]
            / ".github" / "INVARIANTS_ALLOWLIST.json"
        )
        if allowlist.exists():
            data = json.loads(allowlist.read_text())
            # Per allowlist format: top-level dict, count entries
            if isinstance(data, dict):
                pv_ci_count = len(data)
            elif isinstance(data, list):
                pv_ci_count = len(data)
    except Exception:  # noqa: BLE001
        pass

    return {
        "fleet_phase_aligned":         False,  # to be wired when FRR available
        "fleet_phase_target":          "UNKNOWN",
        "zkba_class_coverage_count":   zkba_coverage,
        "chain_submission_paused":     bool(getattr(cfg, "chain_submission_paused", False)),
        "cedar_v2_bundles_anchored":   cedar_count > 0,
        "pv_ci_invariants_count":      pv_ci_count,
        "wallet_balance_iotx":         "",       # async chain call deferred
        "last_anchor_tx_hash":         last_anchor_tx,
        "last_anchor_block":           last_anchor_block,
    }


def _build_integrity_label(*, snapshot: Dict[str, Any]) -> Dict[str, Any]:
    """Construct the FROZEN 9-field integrity label for HONESTY-BOARD-v1."""
    return {
        "proof_type":             "VPM-HONESTY-BOARD",
        "capture_mode":           "live",
        "raw_biometrics_exposed": False,
        "consent_active":         "n/a",
        "zk_verified":            False,
        "on_chain_anchor":        bool(snapshot.get("last_anchor_tx_hash")),
        "proof_weight":           "CHAIN_ONLY",
        "revocation_status":      "active",
        "limitations":            [
            "Autonomous weekly Sentry self-report; PV-CI count + "
            "Cedar v2 anchor status + ZKBA class coverage snapshot.",
        ],
    }


class HonestyBoardTracker:
    """Autonomous HONESTY-BOARD-v1 VPM emission tracker.

    Polls every poll_interval_s; emits one artifact each time
    (now - last_emit_ts_ns) >= emission_interval_s.
    """

    def __init__(
        self,
        *,
        store,
        cfg,
        poll_interval_s: Optional[int] = None,
        emission_interval_s: Optional[int] = None,
    ) -> None:
        self._store = store
        self._cfg = cfg
        self._poll_interval_s = (
            poll_interval_s
            if poll_interval_s is not None
            else getattr(cfg, "honesty_board_poll_interval_s", _DEFAULT_POLL_INTERVAL_S)
        )
        self._emission_interval_s = (
            emission_interval_s
            if emission_interval_s is not None
            else getattr(cfg, "honesty_board_emission_interval_s", _DEFAULT_EMISSION_INTERVAL_S)
        )
        self._state = HonestyBoardState()
        self._state.last_emit_ts_ns = self._seed_last_emit_ts_ns()

    def _seed_last_emit_ts_ns(self) -> int:
        try:
            db_path = getattr(self._store, "_db_path", None) or getattr(
                self._store, "db_path", None
            )
            if not db_path:
                return 0
            con = sqlite3.connect(db_path, timeout=2.0)
            try:
                row = con.execute(
                    "SELECT MAX(ts_ns) FROM vpm_artifact_log "
                    "WHERE vpm_id='HONESTY-BOARD-v1'"
                ).fetchone()
            finally:
                con.close()
            best = int(row[0] or 0) if row else 0
            if best > 0:
                log.info(
                    "HONESTY-BOARD tracker: seeded last_emit_ts_ns=%d "
                    "(%.1fh ago)",
                    best, (time.time_ns() - best) / 1e9 / 3600,
                )
            return best
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "HONESTY-BOARD tracker: seed failed (%s); starting at 0", exc
            )
            return 0

    def poll_once(self) -> Dict[str, Any]:
        try:
            now_ns = time.time_ns()
            elapsed_s = (now_ns - self._state.last_emit_ts_ns) / 1e9
            if (
                self._state.last_emit_ts_ns > 0
                and elapsed_s < self._emission_interval_s
            ):
                return {
                    "action": "noop_within_interval",
                    "elapsed_s": int(elapsed_s),
                    "interval_s": self._emission_interval_s,
                }
            return self._emit(now_ns=now_ns)
        except Exception as exc:  # noqa: BLE001
            log.warning("HONESTY-BOARD tracker: poll error: %s", exc)
            return {"action": "error", "error": str(exc)}

    def _emit(self, *, now_ns: int) -> Dict[str, Any]:
        try:
            snapshot = _snapshot_inputs(store=self._store, cfg=self._cfg)
            integrity_label = _build_integrity_label(snapshot=snapshot)
            # zkba_manifest_hash: synthesize a snapshot hash over the inputs
            # (gives the artifact a stable cryptographic ID for this state).
            import hashlib
            digest = hashlib.sha256(
                json.dumps(snapshot, sort_keys=True, separators=(",", ":"))
                .encode("utf-8")
            ).hexdigest()

            output_dir = (
                Path(__file__).resolve().parents[2]
                / "frontend" / "src" / "artifacts" / "honesty_board"
            )

            # Lazy import — dual-path mirroring prior trackers.
            import sys as _sys
            _scripts_path = str(
                Path(__file__).resolve().parents[2] / "scripts"
            )
            if _scripts_path not in _sys.path:
                _sys.path.insert(0, _scripts_path)
            from vpm_compile_honesty_board import (
                build_honesty_board_artifact,
            )

            manifest = build_honesty_board_artifact(
                fleet_phase_aligned=snapshot["fleet_phase_aligned"],
                fleet_phase_target=snapshot["fleet_phase_target"],
                zkba_class_coverage_count=snapshot["zkba_class_coverage_count"],
                chain_submission_paused=snapshot["chain_submission_paused"],
                cedar_v2_bundles_anchored=snapshot["cedar_v2_bundles_anchored"],
                pv_ci_invariants_count=snapshot["pv_ci_invariants_count"],
                wallet_balance_iotx=snapshot["wallet_balance_iotx"],
                last_anchor_tx_hash=snapshot["last_anchor_tx_hash"],
                last_anchor_block=snapshot["last_anchor_block"],
                integrity_label=integrity_label,
                zkba_manifest_hash_hex=digest,
                visual_state="live",
                capture_mode="live",
                output_dir=output_dir,
                ts_ns=now_ns,
            )

            preimage_json = json.dumps({
                "vpm_id":   "HONESTY-BOARD-v1",
                "snapshot": snapshot,
                "ts_ns":    now_ns,
            }, sort_keys=True, separators=(",", ":"))

            row_id = self._store.insert_vpm_artifact(
                commitment_hex=manifest.output_hash_hex,
                vpm_id="HONESTY-BOARD-v1",
                zkba_class=2,            # GIC
                proof_weight=3,          # CHAIN_ONLY
                visual_state="live",
                capture_mode="live",
                integrity_label_hash_hex=manifest.integrity_label_hash_hex,
                wrapper_schema="vapi-vpm-artifact-v1",
                zkba_manifest_hash_hex=digest,
                manifest_uri=manifest.output_path,
                compiler_output_hash_hex=manifest.output_hash_hex,
                preimage_json=preimage_json,
                ts_ns=now_ns,
            )

            self._state.last_emit_ts_ns = now_ns
            self._state.emissions_this_session += 1
            log.info(
                "HONESTY-BOARD emitted: row=%d zkba_coverage=%d pv_ci=%d "
                "cedar_anchored=%s",
                row_id,
                snapshot["zkba_class_coverage_count"],
                snapshot["pv_ci_invariants_count"],
                snapshot["cedar_v2_bundles_anchored"],
            )
            return {"action": "emitted", "row": row_id,
                    "commitment_hex": manifest.output_hash_hex}
        except Exception as exc:  # noqa: BLE001
            import traceback as _tb
            log.warning(
                "HONESTY-BOARD emit failed: %s\n%s", exc, _tb.format_exc(),
            )
            return {"action": "error", "error": str(exc)}


async def run_honesty_board_tracker_loop(
    *, tracker: HonestyBoardTracker, interval_s: Optional[int] = None,
) -> None:
    if interval_s is None:
        interval_s = tracker._poll_interval_s
    log.info(
        "Phase O5-MLGA Stage 6: HONESTY-BOARD tracker started "
        "(poll=%ds, emit_interval=%ds, seeded_at_ns=%d)",
        interval_s, tracker._emission_interval_s,
        tracker._state.last_emit_ts_ns,
    )
    try:
        while True:
            # Phase 235.x-STABILITY-8 2026-05-17: wrap sync poll_once in
            # asyncio.to_thread per the 4-tracker fix.
            await asyncio.to_thread(tracker.poll_once)
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        log.info("HONESTY-BOARD tracker cancelled")
        raise
