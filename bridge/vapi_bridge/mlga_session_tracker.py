"""Phase O5-MLGA Stage 3 — runtime session tracker (polling-based).

Operationalizes the MLGA capability shipped in commit `cee77070`. Without
this module the MLGA pipeline is paper: the audit variant runs, the capture
module is callable, the unblock-export script reports, but nothing actually
tracks gameplay sessions or persists dataproofs during real-use.

Design discipline (per the operator's defensive-design directive):
  • POLLING-based. The tracker periodically queries existing tables that
    other bridge components already write to (records / ruling_validation_log
    / active_play_occupancy_log / capture_health_log). NO FROZEN-region edits.
    No PoAC wire format changes. No GIC chain changes. No dualshock_
    integration.py modifications.
  • Mirrors the cedar_drift_sweeper + mythos_cadence_engine pattern verbatim.
  • Opt-in. Default mlga_session_tracker_enabled=False in cfg.
  • Single-task background coroutine. Registers with main.py task slot
    alongside cedar_drift_sweeper.
  • Fail-open. Any DB error → log + continue; never raises.

Session lifecycle:
  1. Tracker starts (cfg.mlga_session_tracker_enabled=True).
  2. On each poll cycle (default 30s):
     a. Reads capture_health_log latest row.
     b. If capture_state=NOMINAL + no open session → opens new session.
     c. If session open + capture_state=DISCONNECTED → closes session.
     d. If session open + session_duration > max_duration → closes session
        (default 1 hour cap; configurable).
     e. If session open: updates running totals from records +
        ruling_validation_log + active_play_occupancy_log.
  3. On close: computes MLGA dataproof per mlga_capture.py + persists to
     mlga_session_log + opens fresh tracker state.

This module is the operational unblock for the 3 currently-blocked phases:
Phase 243-SS2 Stage-A + Phase 242-BT Stage 2 + Phase 229 AIT corpus growth.
After this lands + the cfg flag flips, every gameplay session organically
produces a dataproof persisted to mlga_session_log; the unblock-export
script reports progress against the 3 phase targets.

WALLET-FREE; READ-ONLY against chain; SQLite writes only to mlga_session_log.
"""
from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

log = logging.getLogger(__name__)


# Default polling interval (seconds). Fast enough to catch session
# transitions within reasonable latency; slow enough to be background.
_DEFAULT_POLL_INTERVAL_S: int = 30

# Default session max duration cap (1 hour). Long sessions get auto-closed
# + a fresh session opens. Prevents runaway accumulator state if a player
# leaves the controller plugged in indefinitely.
_DEFAULT_MAX_SESSION_DURATION_S: int = 3600


@dataclass(slots=True)
class _SessionState:
    """In-memory running state of one open MLGA session."""
    session_id: str
    open_ts_ns: int                           # session start
    last_poll_ts_ns: int                      # most recent update
    open_reason: str                          # "controller_connected" / "poll_detected_nominal"
    cursor_records_id: int = 0                # last seen records.id (for delta accumulation)
    cursor_validation_id: int = 0             # last seen ruling_validation_log.id
    cursor_apop_id: int = 0                   # last seen active_play_occupancy_log.id
    n_poac_records: int = 0
    n_trigger_pulls_r2: int = 0
    n_trigger_pulls_l2: int = 0
    apop_state_counts: Dict[str, int] = field(default_factory=dict)
    gic_advances_in_session: int = 0
    bt_observability: int = 0                 # 0x00/0x01/0x02 per MLGA capability


@dataclass(slots=True)
class MLGASessionLiveStatus:
    """Public snapshot of the tracker's current state — operator dashboard surface."""
    enabled: bool
    has_open_session: bool
    session_id: str = ""
    session_open_ts_ns: int = 0
    session_duration_s: float = 0.0
    n_poac_records: int = 0
    n_trigger_pulls_r2: int = 0
    n_trigger_pulls_l2: int = 0
    gic_advances_in_session: int = 0
    apop_state_counts: Dict[str, int] = field(default_factory=dict)
    bt_observability: int = 0
    sessions_persisted_total: int = 0
    last_close_ts_ns: int = 0
    last_close_reason: str = ""


class MLGASessionTracker:
    """Polling-based MLGA session lifecycle manager.

    Single instance per bridge process. Constructed at bridge boot when
    cfg.mlga_session_tracker_enabled=True; otherwise dormant. The coroutine
    `run_loop` registers as a background task alongside cedar_drift_sweeper.
    """

    def __init__(self, *, store, cfg, poll_interval_s: int | None = None,
                 max_session_duration_s: int | None = None):
        self._store = store
        self._cfg = cfg
        self._poll_interval_s = int(
            poll_interval_s
            if poll_interval_s is not None
            else getattr(cfg, "mlga_session_tracker_interval_s",
                         _DEFAULT_POLL_INTERVAL_S)
        )
        self._max_duration_s = int(
            max_session_duration_s
            if max_session_duration_s is not None
            else getattr(cfg, "mlga_session_max_duration_s",
                         _DEFAULT_MAX_SESSION_DURATION_S)
        )
        self._open: Optional[_SessionState] = None
        self._sessions_persisted = 0
        self._last_close_ts_ns = 0
        self._last_close_reason = ""

    # ------------------------------------------------------------------
    # Lifecycle methods (testable independent of asyncio loop)
    # ------------------------------------------------------------------

    def open_session(self, reason: str, *, ts_ns: int | None = None) -> str:
        """Open a new MLGA session. Returns the session_id. Idempotent: if
        a session is already open, returns its session_id (no-op)."""
        if self._open is not None:
            return self._open.session_id
        now_ns = ts_ns if ts_ns is not None else time.time_ns()
        sid = f"mlga_{now_ns}"
        self._open = _SessionState(
            session_id=sid,
            open_ts_ns=now_ns,
            last_poll_ts_ns=now_ns,
            open_reason=reason,
        )
        log.info("MLGA session opened: %s (reason=%s)", sid, reason)
        return sid

    def close_session(self, reason: str, *, ts_ns: int | None = None,
                       db_path: str | None = None) -> bool:
        """Close the open session. Computes dataproof + persists to
        mlga_session_log. Returns True if a session was closed; False if
        no open session (idempotent).

        db_path is honored ONLY for tests; production callers pass None
        and the tracker uses its store reference.
        """
        if self._open is None:
            return False
        now_ns = ts_ns if ts_ns is not None else time.time_ns()
        end_ts_ns = max(now_ns, self._open.open_ts_ns + 1)  # ensure end >= start+1
        sess = self._open

        try:
            from vapi_bridge.mlga_capture import (
                compute_mlga_session_dataproof,
                MLGA_BT_NOT_OBSERVED, MLGA_BT_OBSERVED,
                MLGA_BT_HELD_PLACED_IDENTIFIED,
            )
            # Normalize bt_observability to valid FROZEN values
            bt_obs = sess.bt_observability
            if bt_obs not in (
                MLGA_BT_NOT_OBSERVED, MLGA_BT_OBSERVED,
                MLGA_BT_HELD_PLACED_IDENTIFIED,
            ):
                bt_obs = MLGA_BT_NOT_OBSERVED

            dataproof = compute_mlga_session_dataproof(
                session_start_ts_ns=sess.open_ts_ns,
                session_end_ts_ns=end_ts_ns,
                n_poac_records=sess.n_poac_records,
                n_trigger_pulls_r2=sess.n_trigger_pulls_r2,
                n_trigger_pulls_l2=sess.n_trigger_pulls_l2,
                apop_state_counts=sess.apop_state_counts,
                bt_observability=bt_obs,
                gic_advances_in_session=sess.gic_advances_in_session,
            )
            row_id = self._store.insert_mlga_session(
                session_id=sess.session_id,
                session_start_ts_ns=sess.open_ts_ns,
                session_end_ts_ns=end_ts_ns,
                n_poac_records=sess.n_poac_records,
                n_trigger_pulls_r2=sess.n_trigger_pulls_r2,
                n_trigger_pulls_l2=sess.n_trigger_pulls_l2,
                apop_state_counts_json=json.dumps(
                    sess.apop_state_counts, sort_keys=True,
                    separators=(",", ":"),
                ),
                bt_observability=bt_obs,
                gic_advances_in_session=sess.gic_advances_in_session,
                dataproof_hex=dataproof.hex(),
            )
            if row_id > 0:
                self._sessions_persisted += 1
            log.info(
                "MLGA session closed: %s (reason=%s, n_poac=%d, "
                "r2=%d, l2=%d, gic_advances=%d, row=%d)",
                sess.session_id, reason, sess.n_poac_records,
                sess.n_trigger_pulls_r2, sess.n_trigger_pulls_l2,
                sess.gic_advances_in_session, row_id,
            )

            # ---- Phase O5-MLGA Stage 4: VPM artifact compile + persist ----
            # Composes MLGA dataproof with Phase O4 VPM compiler discipline
            # to produce a deterministic HTML artifact + persist row to
            # vpm_artifact_log. The artifact becomes accessible to operators
            # via the existing /operator/vpm-list endpoint + VpmRegistryView
            # frontend tab (vpm_id filter = "MLGA-SESSION-v1") + the new
            # MlgaLiveDrawer tile in DeveloperView. Fail-open: compiler
            # failure must NOT prevent dataproof persist (which already
            # succeeded above). Pinned by INV-MLGA-CLOSE-HOOK-001.
            try:
                import sys as _sys
                _scripts_path = str(
                    Path(__file__).resolve().parents[2] / "scripts"
                )
                if _scripts_path not in _sys.path:
                    _sys.path.insert(0, _scripts_path)
                from mlga_compile_session_artifact import (  # noqa: E402
                    build_mlga_session_artifact,
                )
                _output_dir = (
                    Path(__file__).resolve().parents[2]
                    / "frontend" / "src" / "artifacts" / "mlga"
                )
                _vpm_manifest = build_mlga_session_artifact(
                    session_id=sess.session_id,
                    session_start_ts_ns=sess.open_ts_ns,
                    session_end_ts_ns=end_ts_ns,
                    n_poac_records=sess.n_poac_records,
                    n_trigger_pulls_r2=sess.n_trigger_pulls_r2,
                    n_trigger_pulls_l2=sess.n_trigger_pulls_l2,
                    apop_state_counts=sess.apop_state_counts,
                    bt_observability=bt_obs,
                    gic_advances_in_session=sess.gic_advances_in_session,
                    dataproof_hex=dataproof.hex(),
                    output_dir=_output_dir,
                )
                _vpm_row = self._store.insert_vpm_artifact(
                    commitment_hex=_vpm_manifest["commitment_hex"],
                    vpm_id="MLGA-SESSION-v1",
                    zkba_class=2,            # ZKBAClass.GIC
                    proof_weight=1,          # ProofWeightClass.CHAIN_ONLY (=1 enum order)
                    visual_state=_vpm_manifest["visual_state"],
                    capture_mode="live",
                    integrity_label_hash_hex=_vpm_manifest["integrity_label_hash_hex"],
                    wrapper_schema="vapi-mlga-session-artifact-v1",
                    zkba_manifest_hash_hex=dataproof.hex(),
                    manifest_uri=_vpm_manifest.get("manifest_uri"),
                    compiler_output_hash_hex=_vpm_manifest.get("output_hash_hex"),
                    preimage_json=_vpm_manifest.get("preimage_json", "{}"),
                    ts_ns=end_ts_ns,
                )
                log.info(
                    "MLGA VPM artifact compiled: vpm_row=%d commitment=%s...",
                    _vpm_row, _vpm_manifest["commitment_hex"][:16],
                )
            except Exception as vpm_exc:  # noqa: BLE001 — fail-open
                log.warning(
                    "MLGA VPM compile/persist failed (non-fatal): %s",
                    vpm_exc,
                )

        except Exception as exc:  # noqa: BLE001 — fail-open
            log.warning("MLGA session close persist failed: %s", exc)

        self._last_close_ts_ns = now_ns
        self._last_close_reason = reason
        self._open = None
        return True

    def poll_once(self, *, ts_ns: int | None = None,
                  db_path: str | None = None) -> Dict[str, Any]:
        """One poll cycle. Reads capture_health_log + records + APOP +
        ruling_validation_log; updates session state. Returns brief status
        dict (for tests + operator visibility). Never raises."""
        now_ns = ts_ns if ts_ns is not None else time.time_ns()
        status: Dict[str, Any] = {
            "ts_ns": now_ns,
            "action": "noop",
        }
        try:
            # Determine effective DB path for this poll
            db_for_query = db_path or getattr(self._store, "_db_path", None)
            if db_for_query is None:
                status["error"] = "no_db_path"
                return status

            # ----- Read latest capture state -----
            capture_state, host_state = self._latest_capture_state(db_for_query)
            status["capture_state"] = capture_state
            status["host_state"] = host_state

            # ----- Lifecycle decisions -----
            if self._open is None:
                # No open session: open one if controller is NOMINAL
                if capture_state == "NOMINAL":
                    self.open_session("poll_detected_nominal", ts_ns=now_ns)
                    status["action"] = "opened"
                    status["session_id"] = self._open.session_id  # type: ignore[union-attr]
                else:
                    status["action"] = "noop_no_controller"
                return status

            # Session is open. Check close conditions:
            session_duration_s = (now_ns - self._open.open_ts_ns) / 1e9
            if capture_state == "DISCONNECTED":
                self.close_session("controller_disconnected", ts_ns=now_ns)
                status["action"] = "closed_disconnect"
                return status
            if session_duration_s >= self._max_duration_s:
                self.close_session("max_duration_reached", ts_ns=now_ns)
                status["action"] = "closed_max_duration"
                return status

            # Session continues — accumulate from existing tables.
            self._accumulate_from_records(db_for_query)
            self._accumulate_from_apop(db_for_query)
            self._accumulate_from_gic(db_for_query)
            self._open.last_poll_ts_ns = now_ns
            status["action"] = "accumulated"
            status["session_id"] = self._open.session_id
            return status
        except Exception as exc:  # noqa: BLE001 — fail-open
            status["error"] = f"{type(exc).__name__}: {exc}"
            log.warning("MLGA poll_once raised: %s", exc)
            return status

    # ------------------------------------------------------------------
    # Read helpers (each fail-open; never raise)
    # ------------------------------------------------------------------

    def _latest_capture_state(self, db_path: str) -> tuple[str, str]:
        try:
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            row = con.execute(
                "SELECT capture_state, host_state FROM capture_health_log "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            con.close()
            if row is None:
                return ("", "")
            d = dict(row)
            return (
                (d.get("capture_state") or "").upper(),
                (d.get("host_state") or "").upper(),
            )
        except Exception:  # noqa: BLE001
            return ("", "")

    def _accumulate_from_records(self, db_path: str) -> None:
        """Read records rows new since last poll. Increments n_poac_records
        + n_trigger_pulls_r2 + n_trigger_pulls_l2 (using trigger_active
        column from Phase 235-GAD).

        NOTE: the records table uses record_hash as PRIMARY KEY, NOT
        a numeric `id`. We use SQLite's implicit `rowid` for monotonic
        delta cursoring within this tracker session — adequate because
        rowid is assigned in INSERT order and never reused once
        AUTOINCREMENT is implicit on TEXT PRIMARY KEY tables.
        """
        if self._open is None:
            return
        try:
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT rowid AS rowid_, trigger_active FROM records "
                "WHERE rowid > ? ORDER BY rowid ASC LIMIT 5000",
                (self._open.cursor_records_id,),
            ).fetchall()
            con.close()
            new_count = 0
            new_trigger_active = 0
            max_id = self._open.cursor_records_id
            for r in rows:
                d = dict(r)
                new_count += 1
                if int(d.get("trigger_active", 0) or 0) > 0:
                    # trigger_active is a 1-bit summary (Phase 235-GAD);
                    # we count each active frame as one pull-event boundary.
                    new_trigger_active += 1
                rid = int(d["rowid_"])
                if rid > max_id:
                    max_id = rid
            self._open.n_poac_records += new_count
            # Split active frames roughly between R2 + L2 (NCAA CFB 26
            # sprint mechanic is R2-dominant; without per-trigger split
            # available cheaply here, attribute all to R2 conservatively
            # — Stream 2 of the feature schema will refine this).
            self._open.n_trigger_pulls_r2 += new_trigger_active
            if max_id > self._open.cursor_records_id:
                self._open.cursor_records_id = max_id
        except Exception:  # noqa: BLE001
            pass

    def _accumulate_from_apop(self, db_path: str) -> None:
        if self._open is None:
            return
        try:
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT id, classified_state FROM active_play_occupancy_log "
                "WHERE id > ? ORDER BY id ASC LIMIT 5000",
                (self._open.cursor_apop_id,),
            ).fetchall()
            con.close()
            max_id = self._open.cursor_apop_id
            for r in rows:
                d = dict(r)
                state = (d.get("classified_state") or "").strip() or "UNKNOWN"
                self._open.apop_state_counts[state] = (
                    self._open.apop_state_counts.get(state, 0) + 1
                )
                rid = int(d["id"])
                if rid > max_id:
                    max_id = rid
            if max_id > self._open.cursor_apop_id:
                self._open.cursor_apop_id = max_id
        except Exception:  # noqa: BLE001
            pass

    def _accumulate_from_gic(self, db_path: str) -> None:
        if self._open is None:
            return
        try:
            con = sqlite3.connect(db_path)
            con.row_factory = sqlite3.Row
            rows = con.execute(
                "SELECT id, grind_chain_hash FROM ruling_validation_log "
                "WHERE id > ? AND grind_chain_hash IS NOT NULL "
                "AND grind_chain_hash != '' "
                "ORDER BY id ASC LIMIT 5000",
                (self._open.cursor_validation_id,),
            ).fetchall()
            con.close()
            new_advances = 0
            max_id = self._open.cursor_validation_id
            for r in rows:
                d = dict(r)
                new_advances += 1
                rid = int(d["id"])
                if rid > max_id:
                    max_id = rid
            self._open.gic_advances_in_session += new_advances
            if max_id > self._open.cursor_validation_id:
                self._open.cursor_validation_id = max_id
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------
    # Public status surface
    # ------------------------------------------------------------------

    def live_status(self) -> MLGASessionLiveStatus:
        """Snapshot of tracker state. Operator dashboard / SDK / preflight
        consume this. Never raises."""
        if self._open is None:
            return MLGASessionLiveStatus(
                enabled=bool(
                    getattr(self._cfg, "mlga_session_tracker_enabled", False)
                ),
                has_open_session=False,
                sessions_persisted_total=self._sessions_persisted,
                last_close_ts_ns=self._last_close_ts_ns,
                last_close_reason=self._last_close_reason,
            )
        now_ns = time.time_ns()
        return MLGASessionLiveStatus(
            enabled=True,
            has_open_session=True,
            session_id=self._open.session_id,
            session_open_ts_ns=self._open.open_ts_ns,
            session_duration_s=(now_ns - self._open.open_ts_ns) / 1e9,
            n_poac_records=self._open.n_poac_records,
            n_trigger_pulls_r2=self._open.n_trigger_pulls_r2,
            n_trigger_pulls_l2=self._open.n_trigger_pulls_l2,
            gic_advances_in_session=self._open.gic_advances_in_session,
            apop_state_counts=dict(self._open.apop_state_counts),
            bt_observability=self._open.bt_observability,
            sessions_persisted_total=self._sessions_persisted,
            last_close_ts_ns=self._last_close_ts_ns,
            last_close_reason=self._last_close_reason,
        )


# ----------------------------------------------------------------------
# Async loop entry point (registers with main.py task slot)
# ----------------------------------------------------------------------

async def run_mlga_session_tracker_loop(
    *, tracker: MLGASessionTracker, interval_s: int | None = None,
) -> None:
    """Background coroutine — runs tracker.poll_once on a cadence.

    Mirrors run_cedar_drift_sweep_loop pattern. Opt-in: bridge main.py only
    constructs this when cfg.mlga_session_tracker_enabled=True. Fail-open:
    poll_once already catches its own exceptions.

    Final close on cancellation: if a session is open when the loop is
    cancelled (bridge shutdown), close it with reason='bridge_shutdown'
    so the in-progress dataproof persists.
    """
    if interval_s is None:
        interval_s = tracker._poll_interval_s
    log.info(
        "Phase O5-MLGA Stage 3: session tracker started "
        "(interval=%ds, max_duration=%ds)",
        interval_s, tracker._max_duration_s,
    )
    try:
        while True:
            tracker.poll_once()
            await asyncio.sleep(interval_s)
    except asyncio.CancelledError:
        if tracker._open is not None:
            log.info("MLGA tracker cancelled — closing open session")
            tracker.close_session("bridge_shutdown")
        raise
