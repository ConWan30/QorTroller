"""CalibrationMixin — D-DECON-2 calibration domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern.
STAY in _core: insert_l4_router_log, insert_controller_hardware_profile,
STRUCTURED_PROBE_TYPES (INV pins), _init_schema.
"""
from __future__ import annotations

from ._core import CorpusRegressionError
import hashlib
import json
import time


class CalibrationMixin:
    """L4/L6 calibration, separation defensibility, capture health; via MRO."""
    def insert_l6b_probe(
        self,
        device_id: str,
        probe_ts_ms: int,
        latency_ms: float,
        classification: str,
        accel_delta_peak: float,
        *,
        reflex_verdict: str | None = None,
        cco_profile_id: str | None = None,
        policy_ref: str | None = None,
        trigger_r2_at_probe: int | None = None,
    ) -> int:
        """Persist one L6b reflex probe result (Phase 63; CCO Phase B telemetry).

        latency_ms=-1.0 indicates NO_RESPONSE (stored as NULL in DB).
        Never raises — caller wraps in try/except.
        Returns the new ``l6b_probe_log`` row id.
        """
        _lat = None if latency_ms < 0 else latency_ms
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l6b_probe_log "
                "(device_id, probe_ts_ms, latency_ms, classification, accel_delta_peak, "
                "reflex_verdict, cco_profile_id, policy_ref, trigger_r2_at_probe) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    device_id,
                    probe_ts_ms,
                    _lat,
                    classification,
                    accel_delta_peak,
                    reflex_verdict,
                    cco_profile_id,
                    policy_ref,
                    trigger_r2_at_probe,
                ),
            )
            return int(cur.lastrowid)

    def insert_l6b_probe_diagnostic(
        self,
        device_id: str,
        probe_ts_mono: float,
        *,
        probe_log_id: int | None = None,
        legacy_latency_ms: float | None = None,
        true_latency_ms: float | None = None,
        precursor_gap_ms: float | None = None,
        reflex_gap_ms: float | None = None,
        diagnostic_json: str,
    ) -> None:
        """F-L6B-CAL-005 read-only latency diagnostic. Never raises."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO l6b_probe_diagnostic "
                "(probe_log_id, device_id, probe_ts_mono, legacy_latency_ms, "
                "true_latency_ms, precursor_gap_ms, reflex_gap_ms, diagnostic_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    probe_log_id,
                    device_id,
                    probe_ts_mono,
                    legacy_latency_ms,
                    true_latency_ms,
                    precursor_gap_ms,
                    reflex_gap_ms,
                    diagnostic_json,
                ),
            )

    def get_l6b_baseline(self, device_id: str) -> dict:
        """Return L6b reflex baseline statistics for a device (Phase 63).

        Returns dict with:
          device_id, probe_count, mean_latency_ms, std_latency_ms,
          classification_distribution (dict[str, int]),
          bot_events (int — count of BOT-classified probes)
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT latency_ms, classification FROM l6b_probe_log WHERE device_id=?",
                (device_id,),
            ).fetchall()
        if not rows:
            return {
                "device_id": device_id,
                "probe_count": 0,
                "mean_latency_ms": None,
                "std_latency_ms": None,
                "classification_distribution": {},
                "bot_events": 0,
            }
        latencies = [float(r["latency_ms"]) for r in rows if r["latency_ms"] is not None]
        dist: dict[str, int] = {}
        for r in rows:
            c = r["classification"]
            dist[c] = dist.get(c, 0) + 1
        mean_lat = sum(latencies) / len(latencies) if latencies else None
        if latencies and len(latencies) > 1:
            var = sum((x - mean_lat) ** 2 for x in latencies) / len(latencies)
            std_lat = var ** 0.5
        else:
            std_lat = None
        return {
            "device_id": device_id,
            "probe_count": len(rows),
            "mean_latency_ms": round(mean_lat, 2) if mean_lat is not None else None,
            "std_latency_ms": round(std_lat, 2) if std_lat is not None else None,
            "classification_distribution": dist,
            "bot_events": dist.get("BOT", 0),
        }

    def get_l6b_calibration_progress(self, device_id: str | None = None) -> dict:
        """CCO Phase B: corpus progress toward operator N>=50 gate.

        Counts all rows in l6b_probe_log (optionally filtered by device_id).
        """
        _where = "WHERE device_id=?" if device_id else ""
        _params: tuple = (device_id,) if device_id else ()
        with self._conn() as conn:
            total = int(
                conn.execute(
                    f"SELECT COUNT(*) AS n FROM l6b_probe_log {_where}",
                    _params,
                ).fetchone()["n"],
            )
            reflex_rows = conn.execute(
                f"SELECT reflex_verdict, COUNT(*) AS n FROM l6b_probe_log {_where} "
                "GROUP BY reflex_verdict",
                _params,
            ).fetchall()
            latest = conn.execute(
                f"SELECT device_id, probe_ts_ms, classification, reflex_verdict, "
                f"latency_ms, accel_delta_peak FROM l6b_probe_log {_where} "
                f"ORDER BY id DESC LIMIT 1",
                _params,
            ).fetchone()
        reflex_dist: dict[str, int] = {}
        for row in reflex_rows:
            key = row["reflex_verdict"] if row["reflex_verdict"] is not None else "(null)"
            reflex_dist[key] = int(row["n"])
        latest_dict = dict(latest) if latest else None
        return {
            "device_id": device_id,
            "probe_count": total,
            "reflex_verdict_distribution": reflex_dist,
            "latest_probe": latest_dict,
            "target_n": 50,
            "gate_reached": total >= 50,
        }

    def get_nominal_records_for_calibration(self, limit: int = 200) -> list[dict]:
        """Fetch warmed NOMINAL records for living calibration (Phase 38).

        Only includes records where inference=32 (NOMINAL) and the L4 classifier
        had warmed up (pitl_l4_warmed=1), ensuring threshold quality.
        Returns newest-first so exponential decay weights index 0 = most recent.
        """
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT device_id, pitl_l4_distance, pitl_l5_cv,
                       pitl_humanity_prob, timestamp_ms
                FROM records
                WHERE inference = 32
                  AND pitl_l4_distance IS NOT NULL
                  AND pitl_l4_warmed = 1
                ORDER BY timestamp_ms DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def upsert_player_calibration_profile(
        self,
        device_id: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        baseline_mean: float,
        baseline_std: float,
        session_count: int,
    ) -> None:
        """Insert or replace a per-player calibration profile (Phase 38)."""
        import datetime as _dt
        updated_at = _dt.datetime.now(_dt.timezone.utc).isoformat().replace("+00:00", "Z")
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO player_calibration_profiles
                    (device_id, anomaly_threshold, continuity_threshold,
                     baseline_mean, baseline_std, session_count, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (device_id, anomaly_threshold, continuity_threshold,
                 baseline_mean, baseline_std, session_count, updated_at),
            )

    def get_player_calibration_profile(self, device_id: str) -> dict | None:
        """Return the per-player calibration profile for a device, or None (Phase 38)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM player_calibration_profiles WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_player_calibration_profiles(self) -> list[dict]:
        """Return all per-player calibration profiles (Phase 38)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM player_calibration_profiles ORDER BY updated_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def store_l6_capture(
        self,
        session_id: str,
        profile_id: int,
        profile_name: str,
        challenge_sent_ts: float,
        onset_ms: float,
        settle_ms: float,
        peak_delta: float,
        grip_variance: float,
        r2_pre_mean: float,
        accel_variance: float,
        player_id: str = "",
        game_title: str = "",
        hw_session_ref: str = "",
        notes: str = "",
    ) -> None:
        """Insert one L6 challenge-response record into l6_capture_sessions (Phase 42)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR IGNORE INTO l6_capture_sessions
                    (session_id, profile_id, profile_name, challenge_sent_ts,
                     onset_ms, settle_ms, peak_delta, grip_variance,
                     r2_pre_mean, accel_variance,
                     player_id, game_title, hw_session_ref, notes, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id, profile_id, profile_name, challenge_sent_ts,
                    onset_ms, settle_ms, peak_delta, grip_variance,
                    r2_pre_mean, accel_variance,
                    player_id, game_title, hw_session_ref, notes, time.time(),
                ),
            )

    def query_l6_captures(
        self,
        player_id: str = "",
        profile_id: int | None = None,
        limit: int = 0,
    ) -> list[dict]:
        """Return l6_capture_sessions rows, optionally filtered (Phase 42).

        Args:
            player_id:  Filter to this player ('' = all players).
            profile_id: Filter to this profile_id (None = all profiles).
            limit:      Max rows to return (0 = no limit).
        """
        clauses, params = [], []
        if player_id:
            clauses.append("player_id = ?")
            params.append(player_id)
        if profile_id is not None:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit_clause = f"LIMIT {int(limit)}" if limit > 0 else ""
        sql = f"SELECT * FROM l6_capture_sessions {where} ORDER BY created_at ASC {limit_clause}"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]

    def count_l6_captures_by_profile(self, player_id: str = "") -> dict[int, int]:
        """Return {profile_id: count} for captured L6 sessions (Phase 42)."""
        params = []
        where = ""
        if player_id:
            where = "WHERE player_id = ?"
            params.append(player_id)
        sql = f"SELECT profile_id, COUNT(*) as n FROM l6_capture_sessions {where} GROUP BY profile_id"
        with self._conn() as conn:
            rows = conn.execute(sql, params).fetchall()
        return {r["profile_id"]: r["n"] for r in rows}

    def write_threshold_history(
        self,
        threshold_type: str,
        old_value: float,
        new_value: float,
        drift_pct: float,
        sessions_used: int,
        phase: str,
        device_id: str = None,
    ) -> None:
        """Record a threshold change in history (Phase 50)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO threshold_history "
                "(threshold_type, device_id, old_value, new_value, drift_pct, "
                "sessions_used, phase, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (threshold_type, device_id, old_value, new_value, drift_pct,
                 sessions_used, phase, time.time()),
            )

    def get_threshold_history(self, limit: int = 20) -> list:
        """Return recent threshold history entries desc by created_at (Phase 50)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM threshold_history ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_last_global_recalibration_time(self) -> float:
        """Return epoch of last global agent-triggered recalibration, or 0.0 (Phase 50)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(created_at) as ts FROM threshold_history "
                "WHERE threshold_type LIKE 'global%' "
                "AND phase IN ('manual', 'agent_triggered')",
            ).fetchone()
        ts = row["ts"] if (row is not None and row["ts"] is not None) else None
        return float(ts) if ts is not None else 0.0

    def count_records_since_last_calibration(self, device_id: str) -> int:
        """Count records for device_id since last threshold_history entry (Phase 50)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(created_at) as ts FROM threshold_history WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            last_ts = float(row["ts"]) if (row is not None and row["ts"] is not None) else 0.0
            result = conn.execute(
                "SELECT COUNT(*) as n FROM records WHERE device_id = ? AND created_at > ?",
                (device_id, last_ts),
            ).fetchone()
        return int(result["n"]) if result is not None else 0

    def store_calib_agent_session(self, session_id: str, history: list) -> None:
        """Persist CalibrationIntelligenceAgent conversation history (Phase 50)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO calibration_agent_sessions (session_id, history_json, updated_at) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT(session_id) DO UPDATE SET "
                "history_json = excluded.history_json, updated_at = excluded.updated_at",
                (session_id, json.dumps(history, default=str), now),
            )

    def load_calib_agent_session(self, session_id: str) -> list:
        """Load CalibrationIntelligenceAgent conversation history (Phase 50)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT history_json FROM calibration_agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return []
        try:
            return json.loads(row["history_json"])
        except Exception:
            return []

    def insert_epistemic_threshold_change(
        self, old_threshold: float, new_threshold: float,
        trigger: str = "manual", pmi_at_change: int = 0, notes: str = ""
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO epistemic_threshold_history "
                "(old_threshold, new_threshold, trigger, pmi_at_change, notes) VALUES (?,?,?,?,?)",
                (old_threshold, new_threshold, trigger, int(pmi_at_change), notes),
            )
            return cur.lastrowid

    def get_epistemic_threshold_history(self, limit: int = 20) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, old_threshold, new_threshold, trigger, pmi_at_change, notes, created_at "
                "FROM epistemic_threshold_history ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [{"id": r[0], "old_threshold": r[1], "new_threshold": r[2],
                  "trigger": r[3], "pmi_at_change": r[4], "notes": r[5], "created_at": r[6]}
                for r in rows]

    def insert_readiness_report(
        self, n_tested: int, false_positive_count: int, false_positive_rate: float,
        activation_committed: int, pmi: int, dry_run_active: int,
        ready_for_live: int, notes: str = ""
    ) -> int:
        """Persist live mode readiness validation result (Phase 107)."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO live_mode_readiness_reports "
                "(n_tested, false_positive_count, false_positive_rate, activation_committed, "
                "pmi, dry_run_active, ready_for_live, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (n_tested, false_positive_count, false_positive_rate,
                 activation_committed, pmi, dry_run_active, ready_for_live, notes, _t.time()),
            )
            return cur.lastrowid

    def get_latest_readiness_report(self) -> "dict | None":
        """Return the most recent live mode readiness report (Phase 107). None if none exist."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, n_tested, false_positive_count, false_positive_rate, "
                "activation_committed, pmi, dry_run_active, ready_for_live, notes, created_at "
                "FROM live_mode_readiness_reports ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0], "n_tested": row[1], "false_positive_count": row[2],
            "false_positive_rate": row[3], "activation_committed": bool(row[4]),
            "pmi": row[5], "dry_run_active": bool(row[6]), "ready_for_live": bool(row[7]),
            "notes": row[8], "created_at": row[9],
        }

    def insert_device_epoch_override(
        self,
        device_id: str,
        window_seconds: float,
        reason: str = "",
        max_uses: "int | None" = None,
        expires_at: "float | None" = None,
    ) -> int:
        """Upsert a per-device epoch window override (Phase 118/119).

        INSERT OR REPLACE so subsequent calls update the override for the same device_id.
        Phase 119: max_uses (auto-expire after N successful Gate-5 checks) and
        expires_at (absolute time-based expiry) are optional; None = infinite/never.
        Returns the rowid of the inserted/replaced row.
        """
        import time as _t118
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR REPLACE INTO per_device_epoch_overrides "
                "(device_id, override_window_seconds, reason, max_uses, use_count, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, 0, ?, ?)",
                (device_id, float(window_seconds), reason, max_uses, expires_at, _t118.time()),
            )
            return cur.lastrowid

    def get_device_epoch_override(self, device_id: str) -> "float | None":
        """Return per-device epoch override window in seconds, or None if not set (Phase 118).

        Phase 119: also returns None if the override has expired (expires_at exceeded).
        Expired overrides are deleted on read.
        """
        import time as _t119g
        with self._conn() as conn:
            row = conn.execute(
                "SELECT override_window_seconds, expires_at FROM per_device_epoch_overrides "
                "WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            if row is None:
                return None
            window, expires_at = row
            # Phase 119: check time-based expiry
            if expires_at is not None and _t119g.time() > expires_at:
                conn.execute(
                    "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                    (device_id,),
                )
                return None
        return float(window)

    def get_all_device_epoch_overrides(self) -> "list[dict]":
        """Return all per-device epoch window overrides (Phase 118)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id, override_window_seconds, reason, created_at "
                "FROM per_device_epoch_overrides ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "device_id": r[0],
                "override_window_seconds": r[1],
                "reason": r[2],
                "created_at": r[3],
            }
            for r in rows
        ]

    def delete_device_epoch_override(self, device_id: str) -> bool:
        """Revoke a per-device epoch window override (Phase 119).

        Returns True if a row was deleted, False if no override was set for device_id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                (device_id,),
            )
            return cur.rowcount > 0

    def increment_override_use_count(self, device_id: str) -> bool:
        """Increment use_count for a per-device override after a successful Gate-5 pass.

        Phase 119 W2: auto-graduation — when use_count reaches max_uses, the override
        self-deletes, restoring standard fleet policy for that device.
        Also checks time-based expiry (expires_at).

        Returns True if the override was consumed/expired and deleted, False otherwise.
        Non-blocking: returns False on any error (Gate-5 must not fail on this call).
        """
        import time as _t119i
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT use_count, max_uses, expires_at "
                    "FROM per_device_epoch_overrides WHERE device_id = ?",
                    (device_id,),
                ).fetchone()
                if row is None:
                    return False
                use_count, max_uses, expires_at = row
                # Time-based expiry check
                if expires_at is not None and _t119i.time() > expires_at:
                    conn.execute(
                        "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                        (device_id,),
                    )
                    return True
                # Increment use_count
                new_count = use_count + 1
                # max_uses check (None = infinite)
                if max_uses is not None and new_count >= max_uses:
                    conn.execute(
                        "DELETE FROM per_device_epoch_overrides WHERE device_id = ?",
                        (device_id,),
                    )
                    return True
                conn.execute(
                    "UPDATE per_device_epoch_overrides SET use_count = ? WHERE device_id = ?",
                    (new_count, device_id),
                )
                return False
        except Exception:
            return False

    def get_override_lifecycle_status(self) -> "list[dict]":
        """Return all overrides with full lifecycle fields (Phase 119).

        Includes max_uses, use_count, expires_at so operators can audit
        which overrides are ephemeral vs permanent.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id, override_window_seconds, reason, "
                "max_uses, use_count, expires_at, created_at "
                "FROM per_device_epoch_overrides ORDER BY created_at DESC"
            ).fetchall()
        return [
            {
                "device_id":              r[0],
                "override_window_seconds": r[1],
                "reason":                 r[2],
                "max_uses":               r[3],
                "use_count":              r[4],
                "expires_at":             r[5],
                "created_at":             r[6],
            }
            for r in rows
        ]

    def insert_bt_transport_log(
        self,
        device_address: str,
        sampling_rate_hz: int,
        frames_received: int,
        frames_dropped: int,
        avg_interval_ms: float,
        session_start_ts: float,
        session_end_ts: float,
    ) -> int:
        """Insert a BT transport session log entry (Phase 120). Returns row id."""
        import time as _t120
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO bt_transport_log "
                "(device_address, sampling_rate_hz, frames_received, frames_dropped, "
                "avg_interval_ms, session_start_ts, session_end_ts, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (device_address, sampling_rate_hz, frames_received, frames_dropped,
                 avg_interval_ms, session_start_ts, session_end_ts, _t120.time()),
            )
            return cur.lastrowid

    def get_bt_transport_status(self, limit: int = 10) -> "list[dict]":
        """Return most recent BT transport session logs, newest first (Phase 120)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, device_address, sampling_rate_hz, frames_received, "
                "frames_dropped, avg_interval_ms, session_start_ts, session_end_ts, created_at "
                "FROM bt_transport_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "device_address":   r[1],
                "sampling_rate_hz": r[2],
                "frames_received":  r[3],
                "frames_dropped":   r[4],
                "avg_interval_ms":  r[5],
                "session_start_ts": r[6],
                "session_end_ts":   r[7],
                "created_at":       r[8],
            }
            for r in rows
        ]

    def insert_l4_calibration_log(
        self,
        feature_dim: int,
        n_sessions: int,
        anomaly_threshold: float,
        continuity_threshold: float,
        calibration_timestamp: float,
        stale_flag: bool,
    ) -> int:
        """Record a threshold calibration run or staleness snapshot (Phase 123)."""
        import time as _t123
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l4_calibration_log "
                "(feature_dim, n_sessions, anomaly_threshold, continuity_threshold, "
                "calibration_timestamp, stale_flag, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (feature_dim, n_sessions, float(anomaly_threshold),
                 float(continuity_threshold), float(calibration_timestamp),
                 int(stale_flag), _t123.time()),
            )
            return cur.lastrowid

    def get_l4_calibration_log(self, limit: int = 10) -> "list[dict]":
        """Return recent L4 calibration log entries, newest first (Phase 123)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, feature_dim, n_sessions, anomaly_threshold, "
                "continuity_threshold, calibration_timestamp, stale_flag, created_at "
                "FROM l4_calibration_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                    r[0],
                "feature_dim":           r[1],
                "n_sessions":            r[2],
                "anomaly_threshold":     r[3],
                "continuity_threshold":  r[4],
                "calibration_timestamp": r[5],
                "stale_flag":            bool(r[6]),
                "created_at":            r[7],
            }
            for r in rows
        ]

    def insert_l4_threshold_track(
        self,
        battery_type: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int,
        calibrated_at: float,
        active: bool = True,
    ) -> int:
        """Insert a per-battery L4 threshold track (Phase 124).

        Bounds enforced: anomaly [5.0, 15.0]; continuity [3.0, 10.0].
        Raises ValueError on out-of-bounds to prevent threshold pollution (W1).
        """
        if not (5.0 <= anomaly_threshold <= 15.0):
            raise ValueError(
                f"anomaly_threshold {anomaly_threshold} out of range [5.0, 15.0]"
            )
        if not (3.0 <= continuity_threshold <= 10.0):
            raise ValueError(
                f"continuity_threshold {continuity_threshold} out of range [3.0, 10.0]"
            )
        import time as _t124
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l4_threshold_tracks "
                "(battery_type, anomaly_threshold, continuity_threshold, n_sessions, "
                "calibrated_at, active, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (battery_type, float(anomaly_threshold), float(continuity_threshold),
                 int(n_sessions), float(calibrated_at), int(active), _t124.time()),
            )
            return cur.lastrowid

    def get_l4_threshold_tracks(
        self, battery_type: "str | None" = None, active_only: bool = False
    ) -> "list[dict]":
        """Return L4 threshold tracks, newest first (Phase 124)."""
        conditions = []
        params: list = []
        if battery_type is not None:
            conditions.append("battery_type = ?")
            params.append(battery_type)
        if active_only:
            conditions.append("active = 1")
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        with self._conn() as conn:
            rows = conn.execute(
                f"SELECT id, battery_type, anomaly_threshold, continuity_threshold, "
                f"n_sessions, calibrated_at, active, created_at "
                f"FROM l4_threshold_tracks {where} ORDER BY id DESC",
                params,
            ).fetchall()
        return [
            {
                "id":                   r[0],
                "battery_type":         r[1],
                "anomaly_threshold":    r[2],
                "continuity_threshold": r[3],
                "n_sessions":           r[4],
                "calibrated_at":        r[5],
                "active":               bool(r[6]),
                "created_at":           r[7],
            }
            for r in rows
        ]

    def insert_separation_ratio_snapshot(
        self,
        pooled_ratio: float,
        bt_strat_ratio: float,
        n_sessions: int,
        n_players: int,
        active_features: int,
        tournament_ready: bool,
        ci_lower: float = 0.0,
        ci_upper: float = 0.0,
        n_bootstrap: int = 0,
    ) -> int:
        """Insert a separation ratio snapshot (Phase 121).
        Phase 168: ci_lower/ci_upper/n_bootstrap from bootstrap resampling (optional).
        """
        import time as _t121
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO separation_ratio_snapshots "
                "(pooled_ratio, bt_strat_ratio, n_sessions, n_players, active_features, "
                "tournament_ready, ci_lower, ci_upper, n_bootstrap, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (pooled_ratio, bt_strat_ratio, n_sessions, n_players, active_features,
                 int(tournament_ready), ci_lower, ci_upper, n_bootstrap, _t121.time()),
            )
            return cur.lastrowid

    def get_separation_ratio_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent separation ratio snapshots, newest first (Phase 121/168)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, pooled_ratio, bt_strat_ratio, n_sessions, n_players, "
                "active_features, tournament_ready, "
                "COALESCE(ci_lower, 0.0) as ci_lower, "
                "COALESCE(ci_upper, 0.0) as ci_upper, "
                "COALESCE(n_bootstrap, 0) as n_bootstrap, "
                "created_at "
                "FROM separation_ratio_snapshots ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "pooled_ratio":     r[1],
                "bt_strat_ratio":   r[2],
                "n_sessions":       r[3],
                "n_players":        r[4],
                "active_features":  r[5],
                "tournament_ready": bool(r[6]),
                "ci_lower":         float(r[7]),
                "ci_upper":         float(r[8]),
                "n_bootstrap":      int(r[9]),
                "created_at":       r[10],
            }
            for r in rows
        ]

    def insert_confidence_multiplier_log(
        self,
        device_id: str,
        original_score: int,
        multiplier: float,
        final_score: int,
        bt_strat_ratio: float,
    ) -> int:
        """Log a confidence_score multiplier application (Phase 122). Non-blocking callers."""
        import time as _t122
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO confidence_multiplier_log "
                "(device_id, original_score, multiplier, final_score, bt_strat_ratio, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, original_score, float(multiplier), final_score,
                 float(bt_strat_ratio), _t122.time()),
            )
            return cur.lastrowid

    def get_confidence_multiplier_log(
        self,
        device_id: "str | None" = None,
        limit: int = 10,
    ) -> "list[dict]":
        """Return recent confidence multiplier log entries, newest first (Phase 122)."""
        with self._conn() as conn:
            if device_id is not None:
                rows = conn.execute(
                    "SELECT id, device_id, original_score, multiplier, final_score, "
                    "bt_strat_ratio, created_at FROM confidence_multiplier_log "
                    "WHERE device_id=? ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, original_score, multiplier, final_score, "
                    "bt_strat_ratio, created_at FROM confidence_multiplier_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id":             r[0],
                "device_id":      r[1],
                "original_score": r[2],
                "multiplier":     r[3],
                "final_score":    r[4],
                "bt_strat_ratio": r[5],
                "created_at":     r[6],
            }
            for r in rows
        ]

    def insert_l4_battery_calibration_run(
        self,
        battery_type: str,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int,
        calibration_feature_dim: int = 13,
        notes: "str | None" = None,
    ) -> int:
        """Insert a per-battery L4 calibration run audit record (Phase 125).

        Records each apply operation for traceability.
        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO l4_battery_calibration_runs
                   (battery_type, anomaly_threshold, continuity_threshold,
                    n_sessions, calibration_feature_dim, notes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    battery_type,
                    float(anomaly_threshold),
                    float(continuity_threshold),
                    int(n_sessions),
                    int(calibration_feature_dim),
                    notes,
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_l4_battery_calibration_runs(self, limit: int = 10) -> "list[dict]":
        """Return recent per-battery L4 calibration run records, newest first (Phase 125)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, battery_type, anomaly_threshold, continuity_threshold,
                          n_sessions, calibration_feature_dim, notes, created_at
                   FROM l4_battery_calibration_runs
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                      r[0],
                "battery_type":            r[1],
                "anomaly_threshold":       r[2],
                "continuity_threshold":    r[3],
                "n_sessions":              r[4],
                "calibration_feature_dim": r[5],
                "notes":                   r[6],
                "created_at":              r[7],
            }
            for r in rows
        ]

    def get_l4_router_log(self, limit: int = 50) -> "list[dict]":
        """Return recent L4 threshold router lookup entries, newest first (Phase 126)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, battery_type, threshold_source, anomaly_used,
                          continuity_used, created_at
                   FROM l4_threshold_router_log
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "battery_type":     r[1],
                "threshold_source": r[2],
                "anomaly_used":     r[3],
                "continuity_used":  r[4],
                "created_at":       r[5],
            }
            for r in rows
        ]

    def insert_readiness_score(
        self,
        score: float,
        breakdown_json: str,
        conditions_met: int,
    ) -> int:
        """Insert a tournament readiness score into protocol_intelligence_reports (Phase 128).

        Stores: score in protocol_health_score, breakdown in components_json,
        conditions_met count in recommendation, ready_for_live_mode=score>=0.90.
        Returns row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_intelligence_reports "
                "(protocol_health_score, components_json, recommendation, "
                "ready_for_live_mode, created_at) "
                "VALUES (?,?,?,?,?)",
                (
                    float(score),
                    breakdown_json,
                    str(conditions_met),
                    int(score >= 0.90),
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_readiness_scores(self, limit: int = 10) -> "list[dict]":
        """Return recent tournament readiness score reports, newest first (Phase 128)."""
        import json as _json
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, protocol_health_score AS score, components_json, "
                "recommendation AS conditions_met_str, ready_for_live_mode, created_at "
                "FROM protocol_intelligence_reports "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        result = []
        for row in rows:
            d = dict(row)
            try:
                d["breakdown"] = _json.loads(d.get("components_json") or "{}")
            except (ValueError, TypeError):
                d["breakdown"] = {}
            try:
                d["conditions_met"] = int(d.get("conditions_met_str") or "0")
            except (ValueError, TypeError):
                d["conditions_met"] = 0
            result.append(d)
        return result

    def insert_separation_ratio_breakthrough(
        self,
        before_ratio: float,
        after_ratio: float,
        n_players: int,
        feature_count: int,
    ) -> int:
        """Insert a separation ratio breakthrough event (Phase 129)."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO separation_ratio_breakthrough_log "
                "(before_ratio, after_ratio, n_players, feature_count, breakthrough_at, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (float(before_ratio), float(after_ratio), int(n_players),
                 int(feature_count), now, now),
            )
            return cur.lastrowid

    def get_separation_ratio_breakthrough(self, limit: int = 5) -> "list[dict]":
        """Return recent breakthrough log entries, newest first (Phase 129)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, before_ratio, after_ratio, n_players, feature_count, "
                "breakthrough_at, created_at "
                "FROM separation_ratio_breakthrough_log "
                "ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_usb_reconnect_log(
        self,
        device_address: str = "",
        disconnect_reason: str = "",
        consecutive_fb_timeouts: int = 0,
        ps5_compat_mode_active: bool = False,
        session_id: str = "",
    ) -> int:
        """Phase 131B: Log a USB disconnect/instability event from the HID feedback path.

        Called when _consecutive_fb_timeouts exceeds the auto-log threshold, indicating
        the HID output write path (LED/haptic) is causing USB instability — the root cause
        of the PS5 reconnect notification. VAPI-exclusive: only VAPI writes HID output
        to a DualShock Edge while simultaneously maintaining a live biometric PoAC stream.
        """
        import time as _t
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO usb_reconnect_log "
                "(device_address, disconnect_reason, consecutive_fb_timeouts, "
                "ps5_compat_mode_active, session_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    device_address,
                    disconnect_reason,
                    consecutive_fb_timeouts,
                    int(ps5_compat_mode_active),
                    session_id,
                    _t.time(),
                ),
            )
            return cur.lastrowid or 0

    def get_usb_stability_status(self, limit: int = 50) -> dict:
        """Phase 131B: Return USB stability summary for /agent/usb-stability-status.

        Returns disconnect_count, last_disconnect_ts, and recent log entries. Used by
        the operator to diagnose PS5 coexistence issues and decide whether to enable
        ps5_compat_mode (suppresses all HID output writes, eliminating USB drops at
        the cost of no LED/haptic feedback during gameplay).
        """
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM usb_reconnect_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        entries = [dict(r) for r in rows]
        last_ts = entries[0]["created_at"] if entries else 0.0
        return {
            "disconnect_count": len(entries),
            "last_disconnect_ts": last_ts,
            "entries": entries,
        }

    def insert_l4_recalibration_job(self, started_at: float) -> int:
        """Insert a new recalibration job with status='running'. Returns row id."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO l4_recalibration_jobs (started_at, status, created_at)"
                " VALUES (?, 'running', ?)",
                (started_at, time.time()),
            )
            return cur.lastrowid

    def update_l4_recalibration_job(
        self,
        job_id: int,
        status: str,
        sessions_processed: int,
        anomaly_result: float,
        continuity_result: float,
        completed_at: float,
        error: str | None = None,
    ) -> None:
        """Update a recalibration job record (Phase 134)."""
        with self._conn() as con:
            con.execute(
                "UPDATE l4_recalibration_jobs"
                " SET status=?, sessions_processed=?, anomaly_result=?,"
                "     continuity_result=?, completed_at=?, error=?"
                " WHERE id=?",
                (status, sessions_processed, anomaly_result,
                 continuity_result, completed_at, error, job_id),
            )

    def get_l4_recalibration_jobs(self, limit: int = 10) -> list:
        """Return the most recent L4 recalibration jobs ordered by id DESC (Phase 134)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM l4_recalibration_jobs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_separation_defensibility_log(
        self,
        session_type: str,
        n_sessions_total: int,
        n_per_player: dict,
        min_n_per_player: int,
        defensible: bool,
        ratio: float,
        all_pairs_above_1: bool,
    ) -> int:
        """Insert a separation defensibility report (Phase 150/151).

        defensible=True requires ALL players >= min_n_per_player AND ratio > 1.0.
        Closes WIF-010 formally by tracking per-player N vs target.

        Phase 151 P0 — W1-011: session_type must be in STRUCTURED_PROBE_TYPES.
        Raises ValueError on invalid session_type to prevent free-form corpus
        contamination of the defensibility gate.
        """
        if session_type not in self.STRUCTURED_PROBE_TYPES:
            raise ValueError(
                f"Invalid session_type {session_type!r} for defensibility log. "
                f"Must be one of {sorted(self.STRUCTURED_PROBE_TYPES)}. "
                "Free-form gameplay sessions must not enter the defensibility gate "
                "(W1-011: session type mixing integrity)."
            )
        import json as _json150
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO separation_defensibility_log "
                "(session_type, n_sessions_total, n_per_player_json, min_n_per_player, "
                " defensible, ratio, all_pairs_above_1, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    session_type,
                    n_sessions_total,
                    _json150.dumps(n_per_player),
                    min_n_per_player,
                    1 if defensible else 0,
                    float(ratio),
                    1 if all_pairs_above_1 else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def insert_separation_defensibility_log_guarded(
        self,
        session_type: str,
        n_sessions_total: int,
        n_per_player: dict,
        min_n_per_player: int,
        defensible: bool,
        ratio: float,
        all_pairs_above_1: bool,
        guard_enabled: bool = False,
    ) -> int:
        """Guarded variant of insert_separation_defensibility_log (Phase 208 — WIF-039 W1).

        When guard_enabled=True (CORPUS_RATIO_REGRESSION_GUARD_ENABLED=true):
          - If all_pairs_above_1=True: insert a breakthrough milestone in
            corpus_ratio_regression_guard_log with a tamper-evident provenance chain.
          - If all_pairs_above_1=False AND a prior breakthrough exists for this probe type
            (any prior separation_defensibility_log row had all_pairs_above_1=True):
            raises CorpusRegressionError UNLESS an override exists in
            corpus_regression_override_log for this probe type.
          - This is the Mode-6 ratchet for separation ratio: once all_pairs_above_1
            is reached, it cannot silently regress without an explicit override record.

        When guard_enabled=False (default): behaves identically to
        insert_separation_defensibility_log — no regression check is performed.

        The Ratio Provenance Chain links consecutive guard log entries via:
          provenance_hash = SHA-256(prev_hash + str(ratio) + str(n) + probe_type + str(ts_ns))
        This gives operators an auditable lineage of every milestone.
        """
        import hashlib as _hl208
        # Always insert the main defensibility log entry (guard only adds a side effect)
        row_id = self.insert_separation_defensibility_log(
            session_type=session_type,
            n_sessions_total=n_sessions_total,
            n_per_player=n_per_player,
            min_n_per_player=min_n_per_player,
            defensible=defensible,
            ratio=ratio,
            all_pairs_above_1=all_pairs_above_1,
        )

        if not guard_enabled:
            return row_id

        with self._conn() as con:
            # Check whether a prior breakthrough exists for this probe type
            breakthrough_row = con.execute(
                "SELECT id FROM separation_defensibility_log "
                "WHERE session_type=? AND all_pairs_above_1=1 ORDER BY id ASC LIMIT 1",
                (session_type,),
            ).fetchone()
            prior_breakthrough = breakthrough_row is not None

            if not all_pairs_above_1 and prior_breakthrough:
                # Regression detected — check for an authorized override
                override_row = con.execute(
                    "SELECT id FROM corpus_regression_override_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
                if override_row is None:
                    raise CorpusRegressionError(
                        f"Corpus ratio regression blocked for probe_type={session_type!r}: "
                        f"all_pairs_above_1 was previously True but new entry has "
                        f"all_pairs_above_1=False (ratio={ratio:.3f}). "
                        "Call insert_corpus_regression_override() with a reason before inserting. "
                        "(Phase 208: WIF-039 W1 — CorpusRatioRegressionGuard)"
                    )

            # Record milestone in provenance chain when all_pairs_above_1=True
            if all_pairs_above_1:
                last_guard = con.execute(
                    "SELECT provenance_hash FROM corpus_ratio_regression_guard_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
                prev_hash = last_guard["provenance_hash"] if last_guard else ""
                ts_ns = int(time.time() * 1e9)
                prov_input = f"{prev_hash}{ratio}{n_sessions_total}{session_type}{ts_ns}"
                prov_hash = _hl208.sha256(prov_input.encode()).hexdigest()
                con.execute(
                    "INSERT INTO corpus_ratio_regression_guard_log "
                    "(probe_type, ratio, n_sessions_total, all_pairs_above_1, "
                    " provenance_hash, prev_hash, created_at) VALUES (?,?,?,?,?,?,?)",
                    (
                        session_type,
                        float(ratio),
                        n_sessions_total,
                        1,
                        prov_hash,
                        prev_hash,
                        time.time(),
                    ),
                )

        return row_id

    def insert_corpus_regression_override(
        self,
        probe_type: str,
        old_ratio: float,
        new_ratio: float,
        reason: str,
    ) -> int:
        """Record an authorized corpus ratio regression override (Phase 208 — WIF-039 W2).

        Allows insert_separation_defensibility_log_guarded to proceed with
        all_pairs_above_1=False after a prior breakthrough, provided this
        override record exists.

        override_hash = SHA-256(probe_type + str(old_ratio) + str(new_ratio) + reason + str(ts_ns))
        """
        import hashlib as _hl208o
        ts_ns = int(time.time() * 1e9)
        ov_input = f"{probe_type}{old_ratio}{new_ratio}{reason}{ts_ns}"
        ov_hash = _hl208o.sha256(ov_input.encode()).hexdigest()
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO corpus_regression_override_log "
                "(probe_type, old_ratio, new_ratio, reason, override_hash, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (probe_type, float(old_ratio), float(new_ratio), reason, ov_hash, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_corpus_regression_guard_status(
        self, probe_type: str | None = None
    ) -> dict:
        """Return corpus ratio regression guard summary (Phase 208).

        Returns 7 keys:
          guard_active / breakthrough_ratio / breakthrough_n /
          provenance_hash / override_count / probe_type / timestamp
        """
        import time as _t208
        with self._conn() as con:
            if probe_type:
                guard_row = con.execute(
                    "SELECT ratio, n_sessions_total, provenance_hash, created_at "
                    "FROM corpus_ratio_regression_guard_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                    (probe_type,),
                ).fetchone()
                override_count = con.execute(
                    "SELECT COUNT(*) AS cnt FROM corpus_regression_override_log "
                    "WHERE probe_type=?",
                    (probe_type,),
                ).fetchone()["cnt"]
            else:
                guard_row = con.execute(
                    "SELECT ratio, n_sessions_total, provenance_hash, created_at "
                    "FROM corpus_ratio_regression_guard_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
                override_count = con.execute(
                    "SELECT COUNT(*) AS cnt FROM corpus_regression_override_log"
                ).fetchone()["cnt"]

        guard_active = guard_row is not None
        return {
            "guard_active":      guard_active,
            "breakthrough_ratio": float(guard_row["ratio"]) if guard_row else None,
            "breakthrough_n":    int(guard_row["n_sessions_total"]) if guard_row else None,
            "provenance_hash":   guard_row["provenance_hash"] if guard_row else None,
            "override_count":    int(override_count),
            "probe_type":        probe_type,
            "timestamp":         _t208.time(),
        }

    def insert_l4_dim_sync(
        self,
        from_dim: int,
        to_dim: int,
        anomaly_threshold: float,
        continuity_threshold: float,
        n_sessions: int = 0,
        sync_reason: str = "",
    ) -> int:
        """Record an L4 dimension sync confirmation (Phase 215).

        Called when live_feature_dim != calibration_feature_dim but the added feature is
        structurally zero in gameplay sessions (touchpad_spatial_entropy, index 12),
        confirming thresholds remain valid without a full recalibration run.

        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO l4_dim_sync_log "
                "(from_dim, to_dim, anomaly_threshold, continuity_threshold, n_sessions, "
                "sync_reason, sync_completed, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (int(from_dim), int(to_dim), float(anomaly_threshold),
                 float(continuity_threshold), int(n_sessions), sync_reason, 1, time.time()),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_l4_dim_sync_status(self) -> dict:
        """Return the latest L4 dimension sync status (Phase 215).

        Returns 6 keys:
          sync_completed / from_dim / to_dim / anomaly_threshold / continuity_threshold / timestamp
        """
        import time as _t215
        with self._conn() as conn:
            row = conn.execute(
                "SELECT from_dim, to_dim, anomaly_threshold, continuity_threshold, "
                "sync_completed, created_at FROM l4_dim_sync_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "sync_completed":        False,
                "from_dim":              None,
                "to_dim":                None,
                "anomaly_threshold":     None,
                "continuity_threshold":  None,
                "timestamp":             _t215.time(),
            }
        return {
            "sync_completed":        bool(row["sync_completed"]),
            "from_dim":              int(row["from_dim"]),
            "to_dim":                int(row["to_dim"]),
            "anomaly_threshold":     float(row["anomaly_threshold"]),
            "continuity_threshold":  float(row["continuity_threshold"]),
            "timestamp":             _t215.time(),
        }

    def insert_per_pair_gap(
        self,
        session_type: str,
        pair_key: str,
        player_i: str,
        player_j: str,
        distance: float,
        above_1_0: bool,
        n_sessions_i: int = 0,
        n_sessions_j: int = 0,
        analysis_date: str = "",
    ) -> int:
        """Insert a per-pair Mahalanobis distance record (Phase 216)."""
        import time as _t216
        if not analysis_date:
            import datetime as _dt216
            analysis_date = _dt216.date.today().isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO per_pair_gap_log "
                "(session_type, pair_key, player_i, player_j, distance, above_1_0, "
                "n_sessions_i, n_sessions_j, analysis_date, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    session_type, pair_key, player_i, player_j,
                    float(distance), int(bool(above_1_0)),
                    int(n_sessions_i), int(n_sessions_j),
                    analysis_date, _t216.time(),
                ),
            )
            return cur.lastrowid  # type: ignore[return-value]

    def get_per_pair_gap_status(self, session_type: str | None = None) -> dict:
        """Return per-pair gap distances for the most recent analysis run (Phase 216).

        Returns dict with keys:
          all_pairs_above_1 / pairs / session_type / pair_count / timestamp
        """
        import time as _t216
        with self._conn() as conn:
            if session_type:
                rows = conn.execute(
                    "SELECT pair_key, player_i, player_j, distance, above_1_0, "
                    "n_sessions_i, n_sessions_j, analysis_date FROM per_pair_gap_log "
                    "WHERE session_type=? ORDER BY created_at DESC LIMIT 50",
                    (session_type,),
                ).fetchall()
            else:
                # Return rows from the most recent analysis_date across all session types
                latest = conn.execute(
                    "SELECT analysis_date FROM per_pair_gap_log ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                if latest is None:
                    return {
                        "all_pairs_above_1": False,
                        "pairs": [],
                        "session_type": None,
                        "pair_count": 0,
                        "timestamp": _t216.time(),
                    }
                rows = conn.execute(
                    "SELECT pair_key, player_i, player_j, distance, above_1_0, "
                    "n_sessions_i, n_sessions_j, analysis_date FROM per_pair_gap_log "
                    "WHERE analysis_date=? ORDER BY distance ASC",
                    (latest["analysis_date"],),
                ).fetchall()

        if not rows:
            return {
                "all_pairs_above_1": False,
                "pairs": [],
                "session_type": session_type,
                "pair_count": 0,
                "timestamp": _t216.time(),
            }

        pairs = [
            {
                "pair_key": r["pair_key"],
                "player_i": r["player_i"],
                "player_j": r["player_j"],
                "distance": float(r["distance"]),
                "above_1_0": bool(r["above_1_0"]),
                "n_sessions_i": int(r["n_sessions_i"]),
                "n_sessions_j": int(r["n_sessions_j"]),
            }
            for r in rows
        ]
        all_above = all(p["above_1_0"] for p in pairs)
        return {
            "all_pairs_above_1": all_above,
            "pairs": pairs,
            "session_type": rows[0]["analysis_date"],
            "pair_count": len(pairs),
            "timestamp": _t216.time(),
        }

    def get_per_pair_gap_trend(
        self,
        pair_key: str,
        session_type: str | None = None,
        n_runs: int = 5,
    ) -> dict:
        """Compute velocity (distance delta per day) for a specific pair over the last N analysis runs.

        Returns dict with keys (Phase 217):
          pair_key / session_type / distances / analysis_dates / velocity_per_day /
          trend / n_runs / timestamp
        """
        import time as _t217
        n_runs = max(2, min(20, int(n_runs)))
        with self._conn() as conn:
            if session_type:
                rows = conn.execute(
                    "SELECT distance, analysis_date, above_1_0, created_at "
                    "FROM per_pair_gap_log "
                    "WHERE pair_key=? AND session_type=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pair_key, session_type, n_runs),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT distance, analysis_date, above_1_0, created_at "
                    "FROM per_pair_gap_log "
                    "WHERE pair_key=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (pair_key, n_runs),
                ).fetchall()

        if not rows:
            return {
                "pair_key":         pair_key,
                "session_type":     session_type,
                "distances":        [],
                "analysis_dates":   [],
                "velocity_per_day": None,
                "trend":            "UNKNOWN",
                "n_runs":           0,
                "timestamp":        _t217.time(),
            }

        distances   = [float(r["distance"])      for r in rows]
        dates       = [r["analysis_date"]         for r in rows]
        created_ats = [float(r["created_at"])     for r in rows]

        # Velocity = (latest - oldest) / elapsed_days  (positive = improving = farther apart)
        if len(distances) >= 2:
            dt_days = (created_ats[0] - created_ats[-1]) / 86400.0
            if dt_days > 0:
                vel = (distances[0] - distances[-1]) / dt_days
            else:
                vel = 0.0
            if vel > 0.01:
                trend = "IMPROVING"
            elif vel < -0.01:
                trend = "WORSENING"
            else:
                trend = "STABLE"
        else:
            vel = None
            trend = "UNKNOWN"

        return {
            "pair_key":         pair_key,
            "session_type":     session_type,
            "distances":        distances,
            "analysis_dates":   dates,
            "velocity_per_day": vel,
            "trend":            trend,
            "n_runs":           len(distances),
            "timestamp":        _t217.time(),
        }

    def get_separation_defensibility_status(
        self, session_type: str | None = None
    ) -> "dict | None":
        """Return the latest defensibility report, optionally filtered by session_type (Phase 150)."""
        import json as _json150
        with self._conn() as con:
            if session_type:
                row = con.execute(
                    "SELECT * FROM separation_defensibility_log "
                    "WHERE session_type=? ORDER BY id DESC LIMIT 1",
                    (session_type,),
                ).fetchone()
            else:
                row = con.execute(
                    "SELECT * FROM separation_defensibility_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["n_per_player"] = _json150.loads(d.pop("n_per_player_json", "{}"))
        except Exception:
            d["n_per_player"] = {}
        return d

    def get_enrollment_capture_guidance(
        self, min_n: int = 10
    ) -> dict:
        """Return per-player capture guidance for each structured probe type (Phase 151 P1).

        For each probe type in STRUCTURED_PROBE_TYPES, reads the latest defensibility
        log entry and computes how many more sessions each player needs to reach min_n.

        Returns a guidance dict with:
          - min_n_per_player: the target
          - probe_types: list of structured probe types
          - guidance: per-probe-type breakdown with n_per_player, gap, all_players_ready
          - sessions_needed_total: total capture sessions across all probes/players
          - overall_ready: True when all probe types have all players >= min_n AND ratio >= min_separation_ratio
        """
        import json as _j151
        guidance = {}
        sessions_needed_total = 0
        overall_ready = True
        # Phase 166: configurable gate — retrieve from store attribute if set, else default 0.70
        _min_sep = float(getattr(self, "_min_separation_ratio", 0.70))

        for probe in sorted(self.STRUCTURED_PROBE_TYPES):
            row = self.get_separation_defensibility_status(session_type=probe)
            if row is None:
                guidance[probe] = {
                    "found":             False,
                    "current_ratio":     0.0,
                    "n_per_player":      {},
                    "gap":               {},
                    "all_players_ready": False,
                }
                overall_ready = False
                continue

            n_per_player = row.get("n_per_player", {})
            gap = {
                player: max(0, min_n - count)
                for player, count in n_per_player.items()
            }
            all_players_ready = all(count >= min_n for count in n_per_player.values()) \
                and bool(n_per_player)
            probe_ratio_ok = float(row.get("ratio", 0.0)) >= _min_sep
            probe_entry_ready = all_players_ready and probe_ratio_ok

            sessions_needed_total += sum(gap.values())
            if not probe_entry_ready:
                overall_ready = False

            guidance[probe] = {
                "found":             True,
                "current_ratio":     float(row.get("ratio", 0.0)),
                "n_per_player":      n_per_player,
                "gap":               gap,
                "all_players_ready": probe_entry_ready,
            }

        return {
            "min_n_per_player":       min_n,
            "min_separation_ratio":   _min_sep,
            "probe_types":            sorted(self.STRUCTURED_PROBE_TYPES),
            "guidance":               guidance,
            "sessions_needed_total":  sessions_needed_total,
            "overall_ready":          overall_ready,
        }

    def insert_centroid_velocity_log(
        self,
        probe_type: str,
        velocity: float,
        ratio_prev: float,
        ratio_curr: float,
        dt_seconds: float,
        n_snapshots_used: int,
        stagnant: bool,
    ) -> int:
        """Insert a centroid velocity record (Phase 152)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO centroid_velocity_log "
                "(probe_type, velocity, ratio_prev, ratio_curr, dt_seconds, "
                " n_snapshots_used, stagnant, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (probe_type, float(velocity), float(ratio_prev), float(ratio_curr),
                 float(dt_seconds), int(n_snapshots_used),
                 1 if stagnant else 0, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_centroid_velocity_status(
        self, probe_type: str = "touchpad_corners"
    ) -> "dict | None":
        """Return the latest centroid velocity record for a probe type (Phase 152)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM centroid_velocity_log WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                (probe_type,),
            ).fetchone()
        return dict(row) if row else None

    def compute_centroid_velocity(
        self, probe_type: str = "touchpad_corners"
    ) -> dict:
        """Compute centroid velocity from last 2 defensibility snapshots (Phase 152).

        velocity = |ratio_curr - ratio_prev| / dt_seconds (ratio units per second).
        stagnant = True when velocity_per_day < _PLATEAU_THRESHOLD_PER_DAY (0.001/day).
        Returns velocity dict; never raises.
        """
        with self._conn() as con:
            rows = con.execute(
                "SELECT ratio, created_at FROM separation_defensibility_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT 2",
                (probe_type,),
            ).fetchall()
        if len(rows) < 2:
            return {
                "velocity": 0.0, "ratio_prev": 0.0, "ratio_curr": 0.0,
                "dt_seconds": 0.0, "n_snapshots_used": len(rows), "stagnant": True,
            }
        ratio_curr = float(rows[0]["ratio"])
        ratio_prev = float(rows[1]["ratio"])
        dt = max(1.0, float(rows[0]["created_at"]) - float(rows[1]["created_at"]))
        velocity = abs(ratio_curr - ratio_prev) / dt
        stagnant = (velocity * 86400) < self._PLATEAU_THRESHOLD_PER_DAY
        return {
            "velocity": velocity,
            "ratio_prev": ratio_prev,
            "ratio_curr": ratio_curr,
            "dt_seconds": dt,
            "n_snapshots_used": 2,
            "stagnant": stagnant,
        }

    def insert_separation_ratio_registry_log(
        self,
        commit_hash: str,
        ratio_millis: int,
        n_sessions: int,
        n_players: int,
        on_chain_tx: "str | None" = None,
        committed: bool = False,
        n_consented: int = 0,
    ) -> int:
        """Insert a separation ratio registry commitment record (Phase 153).
        Phase 163: n_consented binds active consent count into hash preimage (WIF-022).
        """
        with self._conn() as con:
            cur = con.execute(
                "INSERT OR IGNORE INTO separation_ratio_registry_log "
                "(commit_hash, ratio_millis, n_sessions, n_players, "
                " on_chain_tx, committed, n_consented, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (commit_hash, int(ratio_millis), int(n_sessions), int(n_players),
                 on_chain_tx, 1 if committed else 0, int(n_consented), time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_separation_ratio_registry_status(self) -> "dict | None":
        """Return the latest separation ratio registry entry (Phase 153/163)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM separation_ratio_registry_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return dict(row) if row else None

    def update_separation_ratio_registry_committed(
        self, commit_hash: str, on_chain_tx: str
    ) -> None:
        """Mark a separation ratio registry entry as committed on-chain (Phase 163)."""
        with self._conn() as con:
            con.execute(
                "UPDATE separation_ratio_registry_log"
                " SET committed=1, on_chain_tx=? WHERE commit_hash=?",
                (on_chain_tx, commit_hash),
            )

    def compute_separation_ratio_commit_hash(
        self,
        ratio: float,
        n_sessions: int,
        players_sorted: str,
        ts_ns: int,
    ) -> "tuple[str, int]":
        """Compute (commit_hash, n_consented) for Phase 163 WIF-022.

        Hash formula: SHA-256('{ratio:.6f}:{n_sessions}:{n_consented}:{players_sorted}:{ts_ns}')
        Reads n_consented atomically from consent_corpus_coverage at call time.
        Returns (commit_hash_hex, n_consented).
        """
        import hashlib as _hl163
        cov = self.get_consent_corpus_coverage()
        n_consented = cov["active_consent_count"]
        preimage = (
            f"{ratio:.6f}:{n_sessions}:{n_consented}:{players_sorted}:{ts_ns}"
        ).encode()
        commit_hash = _hl163.sha256(preimage).hexdigest()
        return commit_hash, n_consented

    def insert_capture_stagnation_log(
        self,
        probe_type: str,
        sessions_in_window: int,
        window_days: float,
        sessions_per_day: float,
        stagnant: bool,
        stagnation_threshold: float = 0.5,
        notes: "str | None" = None,
    ) -> int:
        """Insert a capture stagnation check result (Phase 154)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO capture_stagnation_log "
                "(probe_type, sessions_in_window, window_days, sessions_per_day, "
                " stagnant, stagnation_threshold, notes, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (probe_type, int(sessions_in_window), float(window_days),
                 float(sessions_per_day), 1 if stagnant else 0,
                 float(stagnation_threshold), notes, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_capture_stagnation_status(
        self, probe_type: str = "touchpad_corners"
    ) -> "dict | None":
        """Return the latest capture stagnation check for a probe type (Phase 154)."""
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM capture_stagnation_log WHERE probe_type=? ORDER BY id DESC LIMIT 1",
                (probe_type,),
            ).fetchone()
        return dict(row) if row else None

    def compute_capture_stagnation(
        self, probe_type: str = "touchpad_corners",
        window_days: float = 7.0, threshold: float = 0.5
    ) -> dict:
        """Compute capture stagnation for a probe type over window_days (Phase 154).

        Counts separation_defensibility_log entries in the last window_days.
        stagnant=True when sessions_per_day < threshold (default 0.5/day = 1 every 2 days).
        """
        cutoff = time.time() - window_days * 86400
        with self._conn() as con:
            count_row = con.execute(
                "SELECT COUNT(*) AS cnt FROM separation_defensibility_log "
                "WHERE session_type=? AND created_at >= ?",
                (probe_type, cutoff),
            ).fetchone()
        count = int(count_row["cnt"]) if count_row else 0
        spd = count / window_days if window_days > 0 else 0.0
        return {
            "probe_type": probe_type,
            "sessions_in_window": count,
            "window_days": window_days,
            "sessions_per_day": spd,
            "stagnant": spd < threshold,
            "stagnation_threshold": threshold,
        }

    def get_capture_velocity_oracle_status(
        self,
        probe_type: str = "touchpad_corners",
        window_days: float = 7.0,
        stagnation_threshold: float = 0.5,
    ) -> dict:
        """Synthesize capture stagnation + centroid velocity into a unified oracle (Phase 218).

        Returns dict with keys:
          probe_type / sessions_per_day / sessions_stagnant / ratio_velocity /
          velocity_stagnant / overall_capture_healthy / recommended_action / timestamp
        """
        import time as _t218
        # --- capture stagnation (Phase 154) ---
        stag_row = self.get_capture_stagnation_status(probe_type)
        if stag_row:
            spd = float(stag_row.get("sessions_per_day", 0.0))
            sessions_stagnant = bool(stag_row.get("stagnant", True))
        else:
            # compute live if no log entry
            live = self.compute_capture_stagnation(
                probe_type=probe_type,
                window_days=window_days,
                threshold=stagnation_threshold,
            )
            spd = float(live["sessions_per_day"])
            sessions_stagnant = bool(live["stagnant"])

        # --- centroid velocity (Phase 152) ---
        vel_row = self.get_centroid_velocity_status(probe_type)
        if vel_row:
            ratio_vel = float(vel_row.get("velocity", 0.0))
            velocity_stagnant = bool(vel_row.get("stagnant", True))
        else:
            ratio_vel = 0.0
            velocity_stagnant = True

        overall_healthy = not sessions_stagnant and not velocity_stagnant

        # --- recommended action ---
        if overall_healthy:
            action = "CONTINUE_CURRENT_PROTOCOL"
        elif sessions_stagnant and velocity_stagnant:
            action = "URGENT_CAPTURE_SESSIONS_AND_REANALYZE"
        elif sessions_stagnant:
            action = "CAPTURE_MORE_SESSIONS"
        else:
            action = "RERUN_SEPARATION_ANALYSIS"

        return {
            "probe_type":            probe_type,
            "sessions_per_day":      spd,
            "sessions_stagnant":     sessions_stagnant,
            "ratio_velocity":        ratio_vel,
            "velocity_stagnant":     velocity_stagnant,
            "overall_capture_healthy": overall_healthy,
            "recommended_action":    action,
            "timestamp":             _t218.time(),
        }

    def get_per_pair_gap_projection(
        self,
        session_type: str | None = None,
        n_runs: int = 5,
    ) -> dict:
        """Project how many days until each blocker pair reaches distance=1.0 (Phase 220).

        Uses get_per_pair_gap_trend() to compute velocity for each known pair,
        then estimates days_to_1_0 = (1.0 - current_distance) / velocity_per_day.
        Returns None for WORSENING/STABLE pairs (infeasible without hardware change).

        Returns dict with keys:
          projections / any_feasible / max_days_to_1_0 / projected_tge_date /
          session_type / timestamp
        """
        import time as _t220
        import datetime as _dt220

        # Get current gap status; deduplicate by pair_key keeping most recent entry
        gap_status = self.get_per_pair_gap_status(session_type=session_type)
        _all_pairs = gap_status.get("pairs", [])
        # get_per_pair_gap_status may return multiple entries per pair_key when
        # filtered by session_type; keep only the first (most recent, sorted DESC).
        _seen: set = set()
        pairs = []
        for _p in _all_pairs:
            _pk = _p.get("pair_key", "")
            if _pk not in _seen:
                _seen.add(_pk)
                pairs.append(_p)

        projections = []
        max_days: float | None = None

        for p in pairs:
            pk = p.get("pair_key", "")
            current_dist = float(p.get("distance", 0.0))
            above = bool(p.get("above_1_0", False))

            if above:
                # Already resolved
                projections.append({
                    "pair_key":              pk,
                    "current_distance":      current_dist,
                    "velocity_per_day":      None,
                    "estimated_days_to_1_0": 0,
                    "projected_date":        _dt220.date.today().isoformat(),
                    "projection_feasible":   True,
                    "status":                "RESOLVED",
                })
                continue

            # Get trend velocity
            trend = self.get_per_pair_gap_trend(
                pair_key=pk,
                session_type=session_type,
                n_runs=n_runs,
            )
            vel = trend.get("velocity_per_day")

            if vel is not None and vel > 0.001:
                # IMPROVING — project forward
                days_needed = (1.0 - current_dist) / vel
                proj_date = (_dt220.date.today() +
                             _dt220.timedelta(days=days_needed)).isoformat()
                feasible = True
                if max_days is None or days_needed > max_days:
                    max_days = days_needed
            else:
                days_needed = None
                proj_date = None
                feasible = False

            projections.append({
                "pair_key":              pk,
                "current_distance":      current_dist,
                "velocity_per_day":      vel,
                "estimated_days_to_1_0": days_needed,
                "projected_date":        proj_date,
                "projection_feasible":   feasible,
                "status":                trend.get("trend", "UNKNOWN"),
            })

        # projected TGE date = today + max_days across all blocker pairs
        if max_days is not None:
            tge_date = (_dt220.date.today() +
                        _dt220.timedelta(days=max_days)).isoformat()
        else:
            tge_date = None

        any_feasible = any(p.get("projection_feasible") for p in projections
                          if p.get("status") != "RESOLVED")

        return {
            "projections":       projections,
            "any_feasible":      any_feasible,
            "max_days_to_1_0":   max_days,
            "projected_tge_date": tge_date,
            "session_type":      session_type,
            "timestamp":         _t220.time(),
        }

    def get_controller_hardware_profiles(self, active_only: bool = True) -> list:
        """Return controller hardware profiles (Phase 155)."""
        with self._conn() as con:
            if active_only:
                rows = con.execute(
                    "SELECT * FROM controller_hardware_profiles WHERE active=1 ORDER BY id DESC"
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM controller_hardware_profiles ORDER BY id DESC"
                ).fetchall()
        return [dict(r) for r in rows]

    def insert_enrollment_guidance_log(
        self,
        sessions_needed_total: int,
        overall_ready: bool,
        recommended_action: str,
        urgency_level: str = "low",
        stagnant_probes: "list | None" = None,
        estimated_days: float = -1.0,
        activation_chain_event: "str | None" = None,
        cov_regime_status: str = "unknown",
    ) -> int:
        """Insert an autonomous enrollment guidance report (Phase 156/157)."""
        import json as _j156
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO enrollment_guidance_log "
                "(sessions_needed_total, overall_ready, recommended_action, "
                " urgency_level, stagnant_probes, estimated_days, "
                " activation_chain_event, cov_regime_status, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    int(sessions_needed_total),
                    1 if overall_ready else 0,
                    recommended_action,
                    urgency_level,
                    _j156.dumps(stagnant_probes or []),
                    float(estimated_days),
                    activation_chain_event,
                    cov_regime_status,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_enrollment_guidance_status(self) -> "dict | None":
        """Return the latest enrollment guidance report (Phase 156/157)."""
        import json as _j156
        with self._conn() as con:
            row = con.execute(
                "SELECT * FROM enrollment_guidance_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        d = dict(row)
        try:
            d["stagnant_probes"] = _j156.loads(d.get("stagnant_probes", "[]"))
        except Exception:
            d["stagnant_probes"] = []
        if "cov_regime_status" not in d:
            d["cov_regime_status"] = "unknown"
        return d

    def insert_separation_ratio_recovery_log(
        self,
        current_ratio: float,
        trend_velocity: float,
        n_snapshots_used: int,
        recovery_needed: bool,
        recovery_action: str,
        recommendation: str,
    ) -> int:
        """Insert a separation ratio recovery assessment (Phase 173).

        trend_velocity: dRatio/dSession — negative means converging downward.
        recovery_action: one of STABLE | AGE_WEIGHTING | P1_RE_ENROLLMENT | MORE_SESSIONS.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO separation_ratio_recovery_log "
                "(current_ratio, trend_velocity, n_snapshots_used, recovery_needed, "
                "recovery_action, recommendation, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    float(current_ratio),
                    float(trend_velocity),
                    int(n_snapshots_used),
                    1 if recovery_needed else 0,
                    str(recovery_action),
                    str(recommendation),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_separation_ratio_recovery_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent recovery assessments, newest first (Phase 173)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, current_ratio, trend_velocity, n_snapshots_used, "
                "recovery_needed, recovery_action, recommendation, created_at "
                "FROM separation_ratio_recovery_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":               r[0],
                "current_ratio":    float(r[1]),
                "trend_velocity":   float(r[2]),
                "n_snapshots_used": int(r[3]),
                "recovery_needed":  bool(r[4]),
                "recovery_action":  r[5],
                "recommendation":   r[6],
                "created_at":       r[7],
            }
            for r in rows
        ]

    def register_calibration_session(self, session_file: str, player_id: str,
                                     phase: int) -> str:
        """Create a CALIBRATION_SESSION root node in the provenance DAG (Phase 192).
        node_id = SHA-256(session_file + player_id + str(phase))."""
        import hashlib
        node_id = "sha256:" + hashlib.sha256(
            (session_file + player_id + str(phase)).encode()
        ).hexdigest()
        self.insert_provenance_node({
            "node_id":        node_id,
            "node_type":      "CALIBRATION_SESSION",
            "source_table":   "calibration_sessions",
            "source_row_id":  None,
            "source_hash":    None,
            "parent_node_id": None,
            "edge_type":      None,
            "phase_produced": phase,
            "player_id":      player_id,
            "on_chain_ref":   None,
        })
        return node_id

    def insert_tremor_convergence_log(
        self,
        session_type: str,
        ratio: float,
        velocity: float,
        n_sessions: int,
        convergence_stable: bool,
        consecutive_positive: int,
        sessions_to_target_est: int = 0,
    ) -> int:
        """Insert a tremor convergence velocity snapshot (Phase 202).

        Called after each tremor_resting defensibility update.
        velocity = (ratio_curr - ratio_prev) / N_delta.
        convergence_stable=True when velocity >= 0 for 2 consecutive sessions.
        sessions_to_target_est: linear extrapolation of sessions needed to reach ratio=1.0.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tremor_convergence_log "
                "(session_type, ratio, velocity, n_sessions, convergence_stable, "
                " consecutive_positive, sessions_to_target_est, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    session_type,
                    float(ratio),
                    float(velocity),
                    int(n_sessions),
                    1 if convergence_stable else 0,
                    int(consecutive_positive),
                    int(sessions_to_target_est),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_tremor_convergence_status(
        self, session_type: str = "tremor_resting"
    ) -> "dict | None":
        """Return the latest tremor convergence status for a session type (Phase 202).

        Phase 206 addition: also computes non_convergence_detected and
        consecutive_negative from the last _N_NONCONV_THRESHOLD rows.
        non_convergence_detected=True when _N_NONCONV_THRESHOLD consecutive readings
        all have velocity < 0 — P3 genuine non-stationarity diagnosis gate.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tremor_convergence_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT 1",
                (session_type,),
            ).fetchone()
            # Compute consecutive_negative from recent history (Phase 206)
            recent_rows = conn.execute(
                "SELECT velocity FROM tremor_convergence_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT ?",
                (session_type, self._N_NONCONV_THRESHOLD),
            ).fetchall()
        if row is None:
            return None
        result = dict(row)
        # Count how many leading (most-recent) rows have velocity < 0
        _consec_neg = 0
        for _rrow in recent_rows:
            if float(_rrow[0]) < 0.0:
                _consec_neg += 1
            else:
                break
        result["consecutive_negative"] = _consec_neg
        result["non_convergence_detected"] = (
            len(recent_rows) >= self._N_NONCONV_THRESHOLD
            and _consec_neg >= self._N_NONCONV_THRESHOLD
        )
        return result

    def get_tremor_convergence_history(
        self, session_type: str = "tremor_resting", limit: int = 10
    ) -> "list[dict]":
        """Return recent tremor convergence snapshots, newest first (Phase 202)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tremor_convergence_log "
                "WHERE session_type=? ORDER BY id DESC LIMIT ?",
                (session_type, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_ait_session(
        self,
        n_sessions:          int,
        n_per_player:        dict,
        separation_ratio:    float,
        all_pairs_above_1:   bool,
        inter_player_mean:   float,
        intra_player_mean:   float,
        loo_accuracy:        float,
        cov_mode:            str  = "",
        pair_distances:      dict = None,
        analysis_date:       str  = "",
        per_player_features: dict = None,
        centroids:           dict = None,
        cov_inv:             list = None,
    ) -> int:
        """Insert AIT separation analysis result (Phase 229).

        Phase 230: also mirrors into separation_defensibility_log with session_type='ait'
        so tournament_preflight all_pairs_p0_ok reads AIT data instead of being locked to
        touchpad_corners history.  guard_enabled=False (regression guard off by default).

        Phase 237-ZK-SEPPROOF: optional `centroids` (player_id -> [feat0, feat1, ...]) +
        `cov_inv` (FxF inverse covariance matrix) persist the geometric inputs needed
        for ZK witness reconstruction.  Both default to empty for backward compat with
        callers that don't yet supply them.

        Called by analyze_interperson_separation.py --session-type ait --write-snapshot
        and by POST /agent/run-ait-analysis bridge endpoint.
        """
        import json  as _j229
        import time  as _t229
        _pair_dist_229  = pair_distances or {}
        _ppf_229        = per_player_features or {}
        _centroids_229  = centroids or {}
        _cov_inv_229    = cov_inv or []
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ait_session_log "
                "(probe_type, n_sessions, n_per_player_json, separation_ratio, "
                " all_pairs_above_1, inter_player_mean, intra_player_mean, "
                " loo_accuracy, cov_mode, pair_distances_json, analysis_date, "
                " per_player_features_json, centroids_json, cov_inv_json, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "ait",
                    int(n_sessions),
                    _j229.dumps(n_per_player),
                    float(separation_ratio),
                    int(bool(all_pairs_above_1)),
                    float(inter_player_mean),
                    float(intra_player_mean),
                    float(loo_accuracy),
                    str(cov_mode),
                    _j229.dumps(_pair_dist_229),
                    str(analysis_date),
                    _j229.dumps(_ppf_229),
                    _j229.dumps(_centroids_229),
                    _j229.dumps(_cov_inv_229),
                    _t229.time(),
                ),
            )
            row_id = int(cur.lastrowid)

        # Phase 230: mirror into separation_defensibility_log so all_pairs_p0_ok
        # tournament_preflight gate reads AIT results instead of touchpad_corners.
        _min_n230 = 10
        _n_vals230 = list(n_per_player.values()) if n_per_player else []
        _defensible230 = (
            all_pairs_above_1
            and bool(_n_vals230)
            and all(v >= _min_n230 for v in _n_vals230)
        )
        self.insert_separation_defensibility_log_guarded(
            session_type      = "ait",
            n_sessions_total  = n_sessions,
            n_per_player      = n_per_player,
            min_n_per_player  = _min_n230,
            defensible        = _defensible230,
            ratio             = separation_ratio,
            all_pairs_above_1 = all_pairs_above_1,
            guard_enabled     = False,
        )
        return row_id

    def get_ait_separation_status(self) -> dict:
        """Return AIT separation analysis summary (Phase 229).

        Returns dict with keys:
            ait_separation_enabled: bool (always True when table has rows)
            n_sessions: int
            separation_ratio: float
            all_pairs_above_1: bool
            inter_player_mean: float
            intra_player_mean: float
            loo_accuracy: float
            pair_distances: dict
            analysis_date: str
            last_run_ts: float | None
            timestamp: float
        """
        import json as _j229s
        import time as _t229s
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ait_session_log ORDER BY id DESC LIMIT 1"
            ).fetchone()

        _now = _t229s.time()
        if row is None:
            return {
                "ait_separation_enabled": False,
                "n_sessions":             0,
                "separation_ratio":       0.0,
                "all_pairs_above_1":      False,
                "inter_player_mean":      0.0,
                "intra_player_mean":      0.0,
                "loo_accuracy":           0.0,
                "pair_distances":         {},
                "analysis_date":          "",
                "last_run_ts":            None,
                "timestamp":              _now,
            }

        import math as _math229s
        d = dict(row)
        try:
            pd = _j229s.loads(d.get("pair_distances_json") or "{}")
        except Exception:
            pd = {}
        try:
            npp = _j229s.loads(d.get("n_per_player_json") or "{}")
        except Exception:
            npp = {}
        try:
            ppf = _j229s.loads(d.get("per_player_features_json") or "{}")
        except Exception:
            ppf = {}

        # Derive per-player biometric means for live radar visualisation.
        # Existing rows without per_player_features_json return empty dicts.
        _tremor_hz:  dict = {}
        _roll_deg:   dict = {}
        _pitch_deg:  dict = {}
        for _p, _feats in ppf.items():
            if not isinstance(_feats, dict):
                continue
            _hz = _feats.get("accel_tremor_peak_hz")
            if _hz is not None:
                _tremor_hz[_p] = float(_hz)
            _rs = _feats.get("roll_sin")
            _rc = _feats.get("roll_cos")
            if _rs is not None and _rc is not None:
                _roll_deg[_p] = round(_math229s.degrees(_math229s.atan2(float(_rs), float(_rc))), 2)
            _pc = _feats.get("pitch_cos")
            if _pc is not None:
                _pitch_deg[_p] = round(_math229s.degrees(_math229s.acos(max(-1.0, min(1.0, float(_pc))))), 2)

        return {
            "ait_separation_enabled":   True,
            "n_sessions":               int(d.get("n_sessions", 0)),
            "n_per_player":             npp,
            "separation_ratio":         float(d.get("separation_ratio", 0.0)),
            "all_pairs_above_1":        bool(d.get("all_pairs_above_1", 0)),
            "inter_player_mean":        float(d.get("inter_player_mean", 0.0)),
            "intra_player_mean":        float(d.get("intra_player_mean", 0.0)),
            "loo_accuracy":             float(d.get("loo_accuracy", 0.0)),
            "pair_distances":           pd,
            "analysis_date":            str(d.get("analysis_date") or ""),
            "last_run_ts":              float(d.get("created_at", 0.0)),
            "per_player_tremor_hz":     _tremor_hz,
            "per_player_roll_angle_deg": _roll_deg,
            "per_player_pitch_angle_deg": _pitch_deg,
            "timestamp":                _now,
        }

    def insert_capture_health_event(
        self,
        capture_state: str,
        host_state: str,
        poll_rate_hz: float,
        transition_reason: str = "",
        grind_mode: bool = False,
        session_id: str = "",
        prev_session_id: str = "",
        gap_duration_ms: float = 0.0,
    ) -> int:
        """Log a PCC state transition or periodic health snapshot."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO capture_health_log "
                "(capture_state, host_state, poll_rate_hz, transition_reason, "
                " grind_mode, session_id, prev_session_id, gap_duration_ms, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (capture_state, host_state, float(poll_rate_hz), transition_reason,
                 int(grind_mode), session_id, prev_session_id,
                 float(gap_duration_ms), time.time()),
            )
            return cur.lastrowid or 0

    def get_capture_health_status(self, limit: int = 10) -> dict:
        """Return latest capture health event + recent history."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM capture_health_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            n_total = conn.execute(
                "SELECT COUNT(*) FROM capture_health_log"
            ).fetchone()[0]
            history = conn.execute(
                "SELECT capture_state, host_state, poll_rate_hz, transition_reason, created_at "
                "FROM capture_health_log ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        if row is None:
            return {
                "capture_state":    "DISCONNECTED",
                "host_state":       "UNKNOWN",
                "poll_rate_hz":     0.0,
                "grind_mode":       False,
                "n_events":         0,
                "history":          [],
                "timestamp":        time.time(),
            }
        d = dict(row)
        return {
            "capture_state":    d.get("capture_state", "DISCONNECTED"),
            "host_state":       d.get("host_state", "UNKNOWN"),
            "poll_rate_hz":     float(d.get("poll_rate_hz", 0.0)),
            "grind_mode":       bool(d.get("grind_mode", 0)),
            "last_event_ts":    float(d.get("created_at", 0.0)),
            "n_events":         int(n_total),
            "history":          [dict(r) for r in history],
            "timestamp":        time.time(),
        }

    def insert_gamer_readiness_log(
        self,
        *,
        device_id: str,
        readiness_score: float,
        rsi_risk_score: float,
        fatigue_index: float,
        avg_tremor_hz: float,
        touchpad_entropy: float,
        reaction_latency_ms: float,
        recommendation: str,
    ) -> int:
        """Insert a gamer readiness log entry (Phase 239)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO gamer_readiness_log "
                "(device_id, readiness_score, rsi_risk_score, fatigue_index, "
                " avg_tremor_hz, touchpad_entropy, reaction_latency_ms, "
                " recommendation, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    str(device_id),
                    float(readiness_score),
                    float(rsi_risk_score),
                    float(fatigue_index),
                    float(avg_tremor_hz),
                    float(touchpad_entropy),
                    float(reaction_latency_ms),
                    str(recommendation),
                    time.time(),
                ),
            )
            row_id = cur.lastrowid
        return row_id  # type: ignore[return-value]

    def get_gamer_readiness_status(self, device_id: str) -> dict | None:
        """Return the latest gamer readiness entry for a device (Phase 239)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM gamer_readiness_log "
                "WHERE device_id = ? ORDER BY id DESC LIMIT 1",
                (str(device_id),),
            ).fetchone()
        if row:
            d = dict(row)
            return {
                "id":                  d["id"],
                "device_id":           d["device_id"],
                "readiness_score":     d["readiness_score"],
                "rsi_risk_score":      d["rsi_risk_score"],
                "fatigue_index":       d["fatigue_index"],
                "avg_tremor_hz":       d["avg_tremor_hz"],
                "touchpad_entropy":    d["touchpad_entropy"],
                "reaction_latency_ms": d["reaction_latency_ms"],
                "recommendation":      d["recommendation"],
                "created_at":          d["created_at"],
            }
        return None
