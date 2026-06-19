"""TournamentMixin — D-DECON-2 tournament_activation domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern
(removal diff is the canonical source). CREATE TABLE statements stay
centralized in _core.py._init_schema per D-DECON-2(4).
"""
from __future__ import annotations

import time


class TournamentMixin:
    """Tournament + graduation domain methods extracted from Store; resolved via MRO."""
    def store_tournament_passport(
        self,
        device_id: str,
        passport_hash: str,
        ioid_token_id: int,
        min_humanity_int: int,
        tx_hash: str = "",
        on_chain: bool = False,
    ) -> None:
        """Persist a tournament passport record (Phase 56)."""
        with self._conn() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO tournament_passports
                    (device_id, passport_hash, ioid_token_id, min_humanity_int,
                     tx_hash, on_chain, issued_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    device_id, passport_hash, ioid_token_id, min_humanity_int,
                    tx_hash, 1 if on_chain else 0, time.time(),
                ),
            )

    def get_tournament_passport(self, device_id: str) -> dict | None:
        """Return tournament passport for device_id, or None (Phase 56)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM tournament_passports WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def insert_tournament_readiness_snapshot(
        self, n_tested: int, false_positive_count: int,
        activation_committed: int, pmi: int, dry_run_active: int,
        software_conditions_met: int, separation_ratio: float,
        separation_ratio_ok: int, touchpad_recapture_complete: int,
        hardware_conditions_met: int, fully_ready: int,
        blocking_conditions_json: str = "[]", notes: str = ""
    ) -> int:
        """Persist tournament readiness snapshot (Phase 108)."""
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO tournament_readiness_snapshots "
                "(n_tested, false_positive_count, activation_committed, pmi, dry_run_active, "
                "software_conditions_met, separation_ratio, separation_ratio_ok, "
                "touchpad_recapture_complete, hardware_conditions_met, fully_ready, "
                "blocking_conditions_json, notes, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (n_tested, false_positive_count, activation_committed, pmi, dry_run_active,
                 software_conditions_met, separation_ratio, separation_ratio_ok,
                 touchpad_recapture_complete, hardware_conditions_met, fully_ready,
                 blocking_conditions_json, notes, _t.time()),
            )
            return cur.lastrowid

    def get_latest_tournament_readiness_snapshot(self) -> "dict | None":
        """Return most recent tournament readiness snapshot (Phase 108). None if none exist."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, n_tested, false_positive_count, activation_committed, pmi, "
                "dry_run_active, software_conditions_met, separation_ratio, "
                "separation_ratio_ok, touchpad_recapture_complete, hardware_conditions_met, "
                "fully_ready, blocking_conditions_json, notes, created_at "
                "FROM tournament_readiness_snapshots ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        import json as _j
        return {
            "id": row[0], "n_tested": row[1], "false_positive_count": row[2],
            "activation_committed": bool(row[3]), "pmi": row[4],
            "dry_run_active": bool(row[5]), "software_conditions_met": row[6],
            "separation_ratio": row[7], "separation_ratio_ok": bool(row[8]),
            "touchpad_recapture_complete": bool(row[9]),
            "hardware_conditions_met": row[10], "fully_ready": bool(row[11]),
            "blocking_conditions": _j.loads(row[12]), "notes": row[13],
            "created_at": row[14],
        }

    def insert_tournament_preflight_log(
        self,
        separation_ok: bool,
        l4_ok: bool,
        gate_ok: bool,
        cert_ok: bool,
        audit_ok: bool,
        dual_gate_warned: bool = False,
        epoch_window_warned: bool = False,
        ioswarm_warned: bool = False,
        overall_pass: bool = False,
        conditions_json: str = "{}",
        biometric_ttl_ok: bool = True,
        all_pairs_p0_ok: bool = False,
        ait_defensibility_ok: bool = False,
    ) -> int:
        """Insert a tournament preflight run record (Phase 127; Phase 196 biometric_ttl_ok; Phase 197 all_pairs_p0_ok; Phase 231 ait_defensibility_ok).

        Returns the new row id.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO tournament_preflight_log
                   (separation_ok, l4_ok, gate_ok, cert_ok, audit_ok,
                    dual_gate_warned, epoch_window_warned, ioswarm_warned,
                    overall_pass, conditions_json, biometric_ttl_ok, all_pairs_p0_ok,
                    ait_defensibility_ok, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    int(separation_ok), int(l4_ok), int(gate_ok),
                    int(cert_ok), int(audit_ok),
                    int(dual_gate_warned), int(epoch_window_warned), int(ioswarm_warned),
                    int(overall_pass), conditions_json,
                    int(biometric_ttl_ok), int(all_pairs_p0_ok),
                    int(ait_defensibility_ok),
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_tournament_preflight_status(self, limit: int = 5) -> "list[dict]":
        """Return recent tournament preflight run records, newest first (Phase 127; Phase 196; Phase 197; Phase 231)."""
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT id, separation_ok, l4_ok, gate_ok, cert_ok, audit_ok,
                          dual_gate_warned, epoch_window_warned, ioswarm_warned,
                          overall_pass, conditions_json, biometric_ttl_ok, all_pairs_p0_ok,
                          ait_defensibility_ok, created_at
                   FROM tournament_preflight_log
                   ORDER BY id DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                    r[0],
                "separation_ok":         bool(r[1]),
                "l4_ok":                 bool(r[2]),
                "gate_ok":               bool(r[3]),
                "cert_ok":               bool(r[4]),
                "audit_ok":              bool(r[5]),
                "dual_gate_warned":      bool(r[6]),
                "epoch_window_warned":   bool(r[7]),
                "ioswarm_warned":        bool(r[8]),
                "overall_pass":          bool(r[9]),
                "conditions_json":       r[10],
                "biometric_ttl_ok":       bool(r[11]) if r[11] is not None else True,
                "all_pairs_p0_ok":        bool(r[12]) if r[12] is not None else False,
                "ait_defensibility_ok":   bool(r[13]) if r[13] is not None else False,
                "created_at":             r[14],
            }
            for r in rows
        ]

    def insert_tournament_activation_chain(
        self,
        event_type: str,
        separation_ratio: float,
        n_players: int,
        gate_open_notified: bool = False,
        notes: str | None = None,
    ) -> int:
        """Insert a tournament activation chain event (Phase 135)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO tournament_activation_chain_log "
                "(event_type, separation_ratio, n_players, gate_open_notified, "
                " auto_activate_blocked, operator_action_required, notes, created_at)"
                " VALUES (?,?,?,?,1,1,?,?)",
                (event_type, separation_ratio, n_players,
                 1 if gate_open_notified else 0,
                 notes, time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_tournament_activation_chain(self, limit: int = 10) -> list:
        """Return tournament activation chain log entries ordered by id DESC (Phase 135)."""
        with self._conn() as con:
            rows = con.execute(
                "SELECT * FROM tournament_activation_chain_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_tournament_blocker_summary(self) -> dict:
        """Aggregate all active TGE blockers across preflight, per-pair gaps, and capture velocity (Phase 219).

        Returns dict with keys:
          total_blockers / blockers / overall_blocked /
          preflight_pass / capture_healthy / all_pairs_above_1 / timestamp
        """
        import time as _t219
        blockers = []

        # --- Tournament preflight P0 failures ---
        try:
            preflight_rows = self.get_tournament_preflight_status(limit=1)
            if preflight_rows:
                pf = preflight_rows[0]
                preflight_pass = bool(pf.get("overall_pass", False))
                if not pf.get("separation_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "separation_ok",
                        "detail": "Separation ratio below threshold (ratio < min_separation_ratio)",
                        "severity": "P0",
                    })
                if not pf.get("l4_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "l4_ok",
                        "detail": "L4 threshold staleness or calibration gap",
                        "severity": "P0",
                    })
                if not pf.get("all_pairs_p0_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "all_pairs_p0_ok",
                        "detail": "Not all per-pair Mahalanobis distances above 1.0",
                        "severity": "P0",
                    })
                if not pf.get("biometric_ttl_ok", True):
                    blockers.append({
                        "source": "tournament_preflight",
                        "key":    "biometric_ttl_ok",
                        "detail": "Biometric credential TTL expired or no renewal chain",
                        "severity": "P0",
                    })
            else:
                preflight_pass = False
                blockers.append({
                    "source": "tournament_preflight",
                    "key":    "no_preflight_run",
                    "detail": "Tournament preflight has never been executed",
                    "severity": "P0",
                })
        except Exception:
            preflight_pass = False

        # --- Per-pair gap blockers ---
        try:
            gap_status = self.get_per_pair_gap_status()
            all_pairs_above_1 = bool(gap_status.get("all_pairs_above_1", False))
            if not all_pairs_above_1:
                for bp in gap_status.get("pairs", []):
                    if not bp.get("above_1_0", True):
                        blockers.append({
                            "source":  "per_pair_gap",
                            "key":     bp.get("pair_key", "UNKNOWN"),
                            "detail":  f"Distance={bp.get('distance', 0.0):.4f} < 1.0 (tournament gate requires all pairs ≥ 1.0)",
                            "severity": "P0",
                        })
        except Exception:
            all_pairs_above_1 = False

        # --- Capture velocity oracle ---
        try:
            cvo = self.get_capture_velocity_oracle_status()
            capture_healthy = bool(cvo.get("overall_capture_healthy", False))
            if not capture_healthy:
                blockers.append({
                    "source":  "capture_velocity",
                    "key":     "overall_capture_healthy",
                    "detail":  f"Recommended: {cvo.get('recommended_action', 'UNKNOWN')}; "
                               f"sessions/day={cvo.get('sessions_per_day', 0.0):.2f}",
                    "severity": "P1",
                })
        except Exception:
            capture_healthy = False

        return {
            "total_blockers":   len(blockers),
            "blockers":         blockers,
            "overall_blocked":  len(blockers) > 0,
            "preflight_pass":   preflight_pass,
            "capture_healthy":  capture_healthy,
            "all_pairs_above_1": all_pairs_above_1,
            "timestamp":        _t219.time(),
        }

    def insert_graduation_stage(
        self,
        agent_id: str,
        stage_number: int,
        notes: str = "",
    ) -> int:
        """Insert a new graduation stage record for an agent (Phase 207).

        Called when an operator activates dry_run=False for a specific agent.
        stage_number indicates sequential graduation order (1 = first agent).
        Returns the row id of the inserted record.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO dry_run_graduation_log "
                "(agent_id, stage_number, activated_at, dry_run_disabled_at, "
                " n_clean_sessions, n_false_positives, notes, created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    agent_id,
                    int(stage_number),
                    time.time(),
                    time.time(),
                    0,
                    0,
                    notes,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def record_graduation_clean_session(self, agent_id: str) -> bool:
        """Increment n_clean_sessions for the active graduation stage (Phase 207).

        Called when an adjudication completes without triggering a false positive.
        Returns True if a live graduation stage was found and updated, False otherwise.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM dry_run_graduation_log "
                "WHERE agent_id=? AND rollback_triggered=0 ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE dry_run_graduation_log SET n_clean_sessions=n_clean_sessions+1 "
                "WHERE id=?",
                (row["id"],),
            )
        return True

    def record_graduation_false_positive(
        self, agent_id: str, fp_threshold: int = 2
    ) -> bool:
        """Increment n_false_positives and auto-trigger rollback if threshold exceeded (Phase 207).

        Returns True when rollback was auto-triggered (n_false_positives >= fp_threshold),
        False when false positive was recorded but threshold not yet reached.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, n_false_positives FROM dry_run_graduation_log "
                "WHERE agent_id=? AND rollback_triggered=0 ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row is None:
                return False
            new_fp = int(row["n_false_positives"]) + 1
            if new_fp >= fp_threshold:
                conn.execute(
                    "UPDATE dry_run_graduation_log "
                    "SET n_false_positives=?, rollback_triggered=1, "
                    "    rollback_triggered_at=?, rollback_reason=? "
                    "WHERE id=?",
                    (new_fp, time.time(), f"auto: {new_fp}>={fp_threshold} false positives", row["id"]),
                )
                return True
            conn.execute(
                "UPDATE dry_run_graduation_log SET n_false_positives=? WHERE id=?",
                (new_fp, row["id"]),
            )
        return False

    def trigger_graduation_rollback(self, agent_id: str, reason: str) -> bool:
        """Manually trigger rollback for an agent's active graduation stage (Phase 207).

        Returns True if an active stage was found and rolled back, False otherwise.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM dry_run_graduation_log "
                "WHERE agent_id=? AND rollback_triggered=0 ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row is None:
                return False
            conn.execute(
                "UPDATE dry_run_graduation_log "
                "SET rollback_triggered=1, rollback_triggered_at=?, rollback_reason=? "
                "WHERE id=?",
                (time.time(), reason, row["id"]),
            )
        return True

    def get_graduation_stage_status(self, agent_id: str) -> "dict | None":
        """Return the latest graduation stage for an agent (Phase 207)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM dry_run_graduation_log "
                "WHERE agent_id=? ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_all_graduation_stages(self) -> "list[dict]":
        """Return all graduation stages, ordered by stage_number then creation (Phase 207)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM dry_run_graduation_log "
                "ORDER BY stage_number ASC, id ASC"
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_graduation_autowatch_log(
        self,
        probe_type: str,
        ratio: float,
        all_pairs_above_1: bool,
        trigger_fired: bool,
        preconditions_evaluated: bool = False,
        preconditions_met: "bool | None" = None,
        blockers_json: str = "[]",
    ) -> int:
        """Insert a graduation autowatch event (Phase 214 — WIF-041 mitigation).

        Called by SeparationRatioMonitorAgent when all_pairs_p0_ok transitions False→True
        (trigger_fired=True) and by StagedDryRunGraduationAgent after evaluating
        preconditions (preconditions_evaluated=True).
        """
        import time as _t214
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO graduation_autowatch_log "
                "(probe_type, ratio, all_pairs_above_1, trigger_fired, "
                " preconditions_evaluated, preconditions_met, blockers_json, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    probe_type,
                    float(ratio),
                    int(bool(all_pairs_above_1)),
                    int(bool(trigger_fired)),
                    int(bool(preconditions_evaluated)),
                    int(bool(preconditions_met)) if preconditions_met is not None else None,
                    blockers_json,
                    _t214.time(),
                ),
            )
            return int(cur.lastrowid)

    def get_graduation_autowatch_status(
        self, probe_type: str | None = None, limit: int = 10
    ) -> "dict":
        """Return graduation autowatch summary: latest trigger + precondition results (Phase 214)."""
        import json as _json214
        import time as _t214

        with self._conn() as conn:
            if probe_type:
                rows = conn.execute(
                    "SELECT * FROM graduation_autowatch_log "
                    "WHERE probe_type=? ORDER BY id DESC LIMIT ?",
                    (probe_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM graduation_autowatch_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()

        entries = [dict(r) for r in rows]
        trigger_count   = sum(1 for e in entries if e.get("trigger_fired"))
        evaluated_count = sum(1 for e in entries if e.get("preconditions_evaluated"))
        last_trigger    = next((e for e in entries if e.get("trigger_fired")), None)
        last_evaluated  = next((e for e in entries if e.get("preconditions_evaluated")), None)

        return {
            "total_entries":            len(entries),
            "trigger_count":            trigger_count,
            "evaluated_count":          evaluated_count,
            "last_trigger_ratio":       last_trigger["ratio"] if last_trigger else None,
            "last_trigger_probe_type":  last_trigger["probe_type"] if last_trigger else None,
            "last_preconditions_met":   bool(last_evaluated["preconditions_met"]) if last_evaluated and last_evaluated.get("preconditions_met") is not None else None,
            "last_blockers":            _json214.loads(last_evaluated["blockers_json"]) if last_evaluated else [],
            "entries":                  entries,
            "timestamp":                _t214.time(),
        }
