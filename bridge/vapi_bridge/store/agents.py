"""AgentsRulingsMixin — D-DECON-2 agents_rulings domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern.
STAY in _core: insert_mythos_finding, get_curator_session_aggregate,
get_prev_grind_chain_hash (FROZEN-span / INV pins).
"""
from __future__ import annotations

import json
import math
import time


class AgentsRulingsMixin:
    """Agent sessions, rulings, validation, mythos cadence, commits; via MRO."""
    def store_agent_session(self, session_id: str, history: list[dict]) -> None:
        """Persist BridgeAgent conversation history (Phase 31)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO agent_sessions (session_id, history_json, created_at, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    history_json = excluded.history_json,
                    updated_at   = excluded.updated_at
            """, (session_id, json.dumps(history, default=str), now, now))

    def get_agent_session(self, session_id: str) -> list[dict]:
        """Load BridgeAgent conversation history (Phase 31). Returns [] if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT history_json FROM agent_sessions WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return []
        try:
            return json.loads(row["history_json"])
        except Exception:
            return []

    def delete_agent_session(self, session_id: str) -> None:
        """Remove an agent session from persistent store (Phase 31)."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM agent_sessions WHERE session_id = ?", (session_id,)
            )

    def store_protocol_insight(self, insight_type: str, content: str,
                                device_id: str = "", severity: str = "low") -> None:
        """Persist a proactive alert or anomaly reaction (Phase 32)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO protocol_insights"
                " (insight_type, device_id, content, severity, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (insight_type, device_id, content, severity, time.time()),
            )

    def get_recent_insights(self, limit: int = 20) -> list:
        """Return most recent protocol insights DESC by created_at (Phase 32)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, insight_type, device_id, content, severity, created_at"
                " FROM protocol_insights ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def prune_old_agent_sessions(self, age_days: float = 30.0) -> int:
        """Delete agent sessions older than age_days. Returns rows deleted (Phase 32)."""
        cutoff = time.time() - age_days * 86400
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM agent_sessions WHERE updated_at < ?", (cutoff,)
            )
        return cur.rowcount

    def prune_old_insights(self, age_days: float = 30.0) -> int:
        """Delete protocol_insights older than age_days. Returns rows deleted (Phase 32)."""
        cutoff = time.time() - age_days * 86400
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM protocol_insights WHERE created_at < ?", (cutoff,)
            )
        return cur.rowcount

    def get_insights_since(self, since: float) -> list:
        """Return all protocol_insights rows created after `since` epoch (Phase 35)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM protocol_insights WHERE created_at >= ? ORDER BY created_at ASC",
                (since,),
            ).fetchall()
        return [dict(r) for r in rows]

    def store_insight_digest(self, window_label: str, bot_farm_count: int,
                              high_risk_count: int, federated_count: int,
                              anomaly_count: int, eligible_count: int,
                              dominant_severity: str, top_devices: list,
                              narrative: str) -> None:
        """Persist a longitudinal insight digest for a time window (Phase 35)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO insight_digests"
                " (window_label, synthesized_at, bot_farm_count, high_risk_count,"
                "  federated_count, anomaly_count, eligible_count, dominant_severity,"
                "  top_devices, narrative)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (window_label, time.time(), bot_farm_count, high_risk_count,
                 federated_count, anomaly_count, eligible_count, dominant_severity,
                 json.dumps(top_devices[:5]), narrative),
            )

    def get_latest_digest(self, window_label: str) -> dict | None:
        """Return most recent insight digest for the given window_label (Phase 35)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM insight_digests WHERE window_label=?"
                " ORDER BY synthesized_at DESC LIMIT 1",
                (window_label,),
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["top_devices"] = json.loads(d.get("top_devices", "[]"))
        return d

    def get_all_latest_digests(self) -> list:
        """Return most recent digest for each window_label (Phase 35)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM insight_digests GROUP BY window_label"
                " HAVING synthesized_at = MAX(synthesized_at)"
                " ORDER BY synthesized_at DESC",
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["top_devices"] = json.loads(d.get("top_devices", "[]"))
            result.append(d)
        return result

    def prune_old_digests(self, age_days: float = 90.0) -> int:
        """Delete insight_digests older than age_days. Returns rows deleted (Phase 35)."""
        cutoff = time.time() - age_days * 86400
        with self._conn() as conn:
            cur = conn.execute(
                "DELETE FROM insight_digests WHERE synthesized_at < ?", (cutoff,)
            )
        return cur.rowcount

    def write_agent_event(
        self,
        event_type: str,
        payload: str,
        source: str,
        device_id: str = None,
        target: str = None,
    ) -> int:
        """Insert an agent coordination event (Phase 50). Returns the new event id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO agent_events "
                "(event_type, device_id, payload_json, source_agent, target_agent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (event_type, device_id, payload, source, target, now),
            )
            return cur.lastrowid

    def read_unconsumed_events(self, target_agent: str, limit: int = 50) -> list:
        """Return unconsumed agent events for target_agent (Phase 50)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM agent_events "
                "WHERE target_agent = ? AND consumed_at IS NULL "
                "ORDER BY created_at ASC LIMIT ?",
                (target_agent, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_event_consumed(self, event_id: int, consumed_by: str) -> None:
        """Mark an agent event as consumed (Phase 50)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE agent_events SET consumed_at = ?, consumed_by = ? WHERE id = ?",
                (time.time(), consumed_by, event_id),
            )

    def get_last_sbd_fire_ts(self) -> float | None:
        """Return wall-clock created_at of the most recent SBD ruling_request, or None.

        Phase 235-OBSERVABILITY: used by SessionBoundaryDetectorAgent on startup to
        recover last_fire_at so the 300s throttle survives bridge restart.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT created_at FROM agent_events "
                "WHERE event_type='ruling_request' "
                "AND source_agent='session_boundary_detector_agent' "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        return float(row["created_at"]) if row else None

    def insert_agent_ruling(
        self,
        device_id: str,
        verdict: str,
        confidence: float,
        reasoning: str,
        evidence_json: str,
        commitment_hash: str,
        attestation_hash: str = "",
        dry_run: bool = True,
        source_agent: str = "session_adjudicator",
        expires_at: float | None = None,
        ceremony_integrity: str | None = None,
    ) -> int:
        """Insert autonomous agent ruling. Returns ruling id.

        Phase 73: optional ceremony_integrity — JSON string from
        VAPIZKProof.verify_ceremony_integrity() stored alongside the ruling for
        cryptographic provenance tracing.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO agent_rulings "
                "(device_id, verdict, confidence, reasoning, evidence_json, "
                "attestation_hash, commitment_hash, dry_run, source_agent, "
                "created_at, expires_at, ceremony_integrity) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (device_id, verdict, confidence, reasoning, evidence_json,
                 attestation_hash, commitment_hash, int(dry_run), source_agent,
                 now, expires_at, ceremony_integrity),
            )
            return cur.lastrowid

    def get_agent_rulings(
        self,
        device_id: str,
        limit: int = 20,
        verdict_filter: str | None = None,
    ) -> list[dict]:
        """Return rulings for device, most recent first. Optional verdict filter."""
        with self._conn() as conn:
            if verdict_filter:
                rows = conn.execute(
                    "SELECT * FROM agent_rulings WHERE device_id=? AND verdict=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, verdict_filter, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM agent_rulings WHERE device_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_agent_ruling_by_id(self, ruling_id: int) -> dict | None:
        """Return single ruling by id, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_rulings WHERE id=?", (ruling_id,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_ruling_streak(self, device_id: str, verdict: str, ruling_id: int) -> dict:
        """Update streak counter. Resets on verdict change. Returns current streak dict."""
        now = time.time()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT * FROM ruling_streaks WHERE device_id=?", (device_id,)
            ).fetchone()
            if existing and existing["streak_verdict"] == verdict:
                new_count = existing["current_streak"] + 1
                conn.execute(
                    "UPDATE ruling_streaks SET current_streak=?, last_verdict=?, "
                    "last_ruling_id=?, updated_at=? WHERE device_id=?",
                    (new_count, verdict, ruling_id, now, device_id),
                )
            else:
                conn.execute(
                    "INSERT INTO ruling_streaks (device_id, current_streak, streak_verdict, "
                    "streak_start, last_verdict, last_ruling_id, updated_at) VALUES (?,?,?,?,?,?,?) "
                    "ON CONFLICT(device_id) DO UPDATE SET current_streak=excluded.current_streak, "
                    "streak_verdict=excluded.streak_verdict, streak_start=excluded.streak_start, "
                    "last_verdict=excluded.last_verdict, last_ruling_id=excluded.last_ruling_id, "
                    "updated_at=excluded.updated_at",
                    (device_id, 1, verdict, now, verdict, ruling_id, now),
                )
        return self.get_ruling_streak(device_id)

    def get_ruling_streak(self, device_id: str) -> dict | None:
        """Return current streak for device, or None if no streak recorded."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ruling_streaks WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def set_streak_escalation(self, device_id: str, escalated_to: str) -> None:
        """Mark that a streak was auto-escalated to a higher verdict."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE ruling_streaks SET escalated_to=?, updated_at=? WHERE device_id=?",
                (escalated_to, time.time(), device_id),
            )

    def insert_on_chain_ruling(
        self,
        ruling_id: int,
        device_id: str,
        commitment_hash: str,
        tx_hash: str,
        block_number: int | None = None,
        chain_id: int = 4690,
    ) -> int:
        """Insert on-chain commitment record. Returns row id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO on_chain_rulings "
                "(ruling_id, device_id, commitment_hash, tx_hash, block_number, chain_id, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (ruling_id, device_id, commitment_hash, tx_hash, block_number, chain_id, now),
            )
            return cur.lastrowid

    def get_on_chain_rulings(self, device_id: str, limit: int = 10) -> list[dict]:
        """Return on-chain ruling records for device, most recent first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM on_chain_rulings WHERE device_id=? "
                "ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_on_chain_ruling_by_commitment(self, commitment_hash: str) -> dict | None:
        """Return on-chain ruling by commitment_hash, or None if not found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM on_chain_rulings WHERE commitment_hash=?",
                (commitment_hash,),
            ).fetchone()
        return dict(row) if row else None

    def get_unvalidated_rulings(self, limit: int = 50) -> list[dict]:
        """Phase 235-BRIDGE-WEDGE-FIX: agent_rulings rows with no matching
        ruling_validation_log row.  Extracted from session_adjudicator_validator
        so the entire connection-open / fetch / close lifecycle runs inside a
        single asyncio.to_thread() worker thread instead of straddling the
        event loop."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT ar.* FROM agent_rulings ar "
                "LEFT JOIN ruling_validation_log rvl ON ar.id = rvl.ruling_id "
                "WHERE rvl.id IS NULL "
                "ORDER BY ar.created_at ASC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def insert_validation_record(
        self,
        ruling_id: int,
        device_id: str,
        llm_verdict: str,
        fallback_verdict: str,
        llm_confidence: float,
        fallback_confidence: float,
        divergence: int,
        divergence_reason: str | None = None,
        pcc_state: str | None = None,
        pcc_host_state: str | None = None,
        gameplay_context: str | None = None,
    ) -> int:
        """Insert a validation comparison record. Returns row id.

        divergence_reason (Phase 88): JSON string of non-nominal evidence fields that
        may explain why LLM and _rule_fallback disagreed. None for non-diverging records.

        pcc_state / pcc_host_state (Phase 235-B): capture health at adjudication time.
        NULL = fail-closed (session does not count toward consecutive_clean in grind mode).

        gameplay_context (Phase 235-GAD): 'ACTIVE_GAMEPLAY' | 'MENU_DETECTED' | None.
        NULL = unknown (pass-through). 'MENU_DETECTED' = confirmed non-gameplay (blocked).
        """
        if self._consent_ledger_enabled:
            self._check_consent_gate(device_id, "insert_validation_record")
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                "llm_confidence, fallback_confidence, divergence, divergence_reason, "
                "pcc_state, pcc_host_state, gameplay_context, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (ruling_id, device_id, llm_verdict, fallback_verdict,
                 llm_confidence, fallback_confidence, divergence, divergence_reason,
                 pcc_state, pcc_host_state, gameplay_context, now),
            )
            return cur.lastrowid


    def override_gameplay_context(
        self, row_id: int, reason: str, device_id: str = ""
    ) -> None:
        """Phase 235-GAD — Operator override: set gameplay_context='ACTIVE_GAMEPLAY'.

        Logs to gameplay_classification_disagreements for post-hoc analysis.
        Use when automatic MENU_DETECTED classification was incorrect (e.g., analog
        stick fault caused false classification during competitive match).
        """
        with self._conn() as conn:
            conn.execute(
                "SELECT gameplay_context FROM ruling_validation_log WHERE id = ?",
                (row_id,),
            )
            old_ctx_row = conn.execute(
                "SELECT gameplay_context FROM ruling_validation_log WHERE id = ?",
                (row_id,),
            ).fetchone()
            old_ctx = old_ctx_row["gameplay_context"] if old_ctx_row else None
        with self._conn() as conn:
            conn.execute(
                "UPDATE ruling_validation_log SET gameplay_context = 'ACTIVE_GAMEPLAY' WHERE id = ?",
                (row_id,),
            )
            conn.execute(
                "INSERT INTO gameplay_classification_disagreements "
                "(ruling_validation_log_id, device_id, automatic_context, override_reason, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (row_id, device_id, old_ctx or "", reason, time.time()),
            )

    def insert_active_play_occupancy_log(
        self,
        ruling_validation_log_id: int,
        ruling_id: int,
        device_id: str,
        state: str,
        score: float,
        confidence: float,
        evidence_json: str,
        gate_mode: str,
    ) -> int:
        """Persist Phase 241-APOP classifier output for a validation row."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO active_play_occupancy_log "
                "(ruling_validation_log_id, ruling_id, device_id, state, score, "
                "confidence, evidence_json, gate_mode, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(ruling_validation_log_id),
                    int(ruling_id),
                    device_id or "",
                    state,
                    float(score),
                    float(confidence),
                    evidence_json or "{}",
                    gate_mode or "shadow",
                    time.time(),
                ),
            )
            return cur.lastrowid or 0

    def get_active_play_logs_for_validation_ids(
        self, validation_ids: list[int]
    ) -> dict[int, dict]:
        """Return latest APOP log per ruling_validation_log id."""
        ids = [int(v) for v in validation_ids if v is not None]
        if not ids:
            return {}
        placeholders = ",".join("?" for _ in ids)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM active_play_occupancy_log "
                f"WHERE ruling_validation_log_id IN ({placeholders}) "
                "ORDER BY created_at DESC",
                tuple(ids),
            ).fetchall()
        result: dict[int, dict] = {}
        for row in rows:
            d = dict(row)
            key = int(d["ruling_validation_log_id"])
            if key not in result:
                result[key] = d
        return result

    def get_latest_active_play_occupancy_status(
        self,
        enabled: bool = True,
        gate_mode: str = "shadow",
        latest_gameplay_context: str | None = None,
    ) -> dict:
        """Return latest Phase 241-APOP status for the operator API."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM active_play_occupancy_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
            total = conn.execute(
                "SELECT COUNT(*) FROM active_play_occupancy_log"
            ).fetchone()[0]
        if row is None:
            return {
                "active_play_occupancy_enabled": bool(enabled),
                "gate_mode": gate_mode,
                "total_logs": int(total),
                "latest_state": None,
                "latest_score": 0.0,
                "latest_confidence": 0.0,
                "latest_evidence": {},
                "latest_gameplay_context": latest_gameplay_context,
                "timestamp": time.time(),
            }
        d = dict(row)
        try:
            evidence = json.loads(d.get("evidence_json") or "{}")
        except Exception:
            evidence = {}
        return {
            "active_play_occupancy_enabled": bool(enabled),
            "gate_mode": gate_mode,
            "total_logs": int(total),
            "latest_state": d.get("state"),
            "latest_score": float(d.get("score", 0.0) or 0.0),
            "latest_confidence": float(d.get("confidence", 0.0) or 0.0),
            "latest_evidence": evidence if isinstance(evidence, dict) else {},
            "latest_gameplay_context": latest_gameplay_context,
            "latest_ruling_validation_log_id": d.get("ruling_validation_log_id"),
            "latest_ruling_id": d.get("ruling_id"),
            "latest_device_id": d.get("device_id", ""),
            "last_run_ts": d.get("created_at"),
            "timestamp": time.time(),
        }

    def get_validation_gate_status(
        self, gate_n: int = 100, max_divergence_rate: float = 1.0
    ) -> dict:
        """Return validation gate status with recommended operator action (Phase 78)."""
        summary = self.get_validation_summary(gate_n, max_divergence_rate)
        if summary["gate_passed"]:
            action = "Gate passed — safe to set AGENT_DRY_RUN=false via POST /agent/config"
        elif not summary["divergence_rate_ok"]:
            action = (
                f"Divergence rate {summary['divergence_rate']:.1%} exceeds max "
                f"{max_divergence_rate:.1%} — review recent divergences before enabling enforcement"
            )
        elif summary["divergence_count"] > 0:
            action = (
                f"Divergences detected ({summary['divergence_count']}) — "
                "review validation_divergence events before enabling enforcement"
            )
        else:
            remaining = gate_n - summary["consecutive_clean"]
            action = (
                f"{remaining} more clean ruling(s) needed before enforcement is safe"
            )
        summary["recommended_action"] = action
        return summary

    def get_campaign_status(
        self, gate_n: int = 100, max_divergence_rate: float = 1.0
    ) -> dict:
        """Return adjudication campaign progress toward dry_run=False activation (Phase 88).

        Reads from ruling_validation_log to compute:
          - consecutive_clean / gate_n progress (atomically from get_validation_summary)
          - verdict_breakdown (CERTIFY/FLAG/HOLD/BLOCK counts from LLM verdicts)
          - divergence_breakdown (divergence_reason → count for diverged rows)
          - recent_sessions (last 10 validation log rows, newest-first)
          - estimated_sessions_to_gate (probabilistic: remaining / (1 - divergence_rate))
          - campaign_note (human-readable operator narrative)

        W1 invariant: consecutive_clean and gate_passed computed atomically via
        get_validation_summary() — never cached or stale.
        """
        import math as _math

        summary = self.get_validation_summary(gate_n, max_divergence_rate)
        consecutive_clean = summary["consecutive_clean"]
        session_count = summary["total"]
        divergence_count = summary["divergence_count"]
        divergence_rate = summary["divergence_rate"]
        gate_passed = summary["gate_passed"]

        progress_pct = round(
            min(100.0, consecutive_clean / gate_n * 100.0), 1
        ) if gate_n > 0 else 0.0

        remaining = max(0, gate_n - consecutive_clean)
        if remaining == 0:
            estimated_sessions_to_gate = 0
        elif (1.0 - divergence_rate) > 0.01:
            estimated_sessions_to_gate = int(
                _math.ceil(remaining / (1.0 - divergence_rate))
            )
        else:
            estimated_sessions_to_gate = 9999  # divergence_rate near 1.0 — gating indefinitely

        with self._conn() as conn:
            vb_rows = conn.execute(
                "SELECT llm_verdict, COUNT(*) as cnt FROM ruling_validation_log "
                "GROUP BY llm_verdict"
            ).fetchall()
            verdict_breakdown = {r["llm_verdict"]: r["cnt"] for r in vb_rows}

            div_rows = conn.execute(
                "SELECT divergence_reason, COUNT(*) as cnt FROM ruling_validation_log "
                "WHERE divergence=1 AND divergence_reason IS NOT NULL "
                "GROUP BY divergence_reason"
            ).fetchall()
            divergence_breakdown = {r["divergence_reason"]: r["cnt"] for r in div_rows}

            recent_rows = conn.execute(
                "SELECT ruling_id, device_id, llm_verdict, fallback_verdict, "
                "divergence, divergence_reason, created_at "
                "FROM ruling_validation_log ORDER BY created_at DESC LIMIT 10"
            ).fetchall()
            recent_sessions = [dict(r) for r in recent_rows]

            last_row = conn.execute(
                "SELECT MAX(created_at) as last_at FROM ruling_validation_log"
            ).fetchone()
            last_session_at = (
                float(last_row["last_at"])
                if last_row and last_row["last_at"] else None
            )

        if gate_passed:
            note = (
                f"Gate PASSED — {consecutive_clean}/{gate_n} consecutive clean rulings. "
                "Safe to set AGENT_DRY_RUN=false via POST /agent/config."
            )
        elif session_count == 0:
            note = (
                "No real sessions validated yet — start the bridge with controller "
                "connected and play NCAA CFB 26 to begin accumulating clean rulings."
            )
        else:
            note = (
                f"Campaign in progress: {consecutive_clean}/{gate_n} consecutive clean "
                f"(~{estimated_sessions_to_gate} more sessions at current divergence "
                f"rate {divergence_rate:.1%})."
            )

        return {
            "consecutive_clean": consecutive_clean,
            "gate_n": gate_n,
            "progress_pct": progress_pct,
            "session_count": session_count,
            "divergence_count": divergence_count,
            "divergence_rate": divergence_rate,
            "gate_passed": gate_passed,
            "estimated_sessions_to_gate": estimated_sessions_to_gate,
            "verdict_breakdown": verdict_breakdown,
            "divergence_breakdown": divergence_breakdown,
            "recent_sessions": recent_sessions,
            "last_session_at": last_session_at,
            "campaign_note": note,
        }

    def insert_provenance_anchor(
        self,
        ruling_id: int,
        device_id: str,
        provenance_hash: str,
        ceremony_hash: str,
        evidence_hash: str,
    ) -> int:
        """Insert a provenance anchor record. Returns row id.

        Uses INSERT OR IGNORE so duplicate anchors for the same ruling_id are silently
        ignored (the unique index on ruling_id enforces idempotency).
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO ruling_provenance_anchors "
                "(ruling_id, device_id, provenance_hash, ceremony_hash, evidence_hash, anchored_at) "
                "VALUES (?,?,?,?,?,?)",
                (ruling_id, device_id, provenance_hash, ceremony_hash, evidence_hash, now),
            )
            return cur.lastrowid or 0

    def get_provenance_anchor(self, ruling_id: int) -> dict | None:
        """Return the provenance anchor record for ruling_id, or None if not yet anchored."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM ruling_provenance_anchors WHERE ruling_id=?",
                (ruling_id,),
            ).fetchone()
        return dict(row) if row else None

    def count_operator_overrides(self, within_n: int = 100) -> int:
        """Count manual operator overrides in the most recent within_n rulings window (Phase 79).

        An override is a 'ruling_override' event in agent_events.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_events "
                "WHERE event_type='ruling_override' "
                "AND created_at > COALESCE(("
                "  SELECT MIN(created_at) FROM ("
                "    SELECT created_at FROM agent_rulings ORDER BY created_at DESC LIMIT ?"
                "  )"
                "), 0)",
                (within_n,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def count_ceremony_key_rotations(self, within_hours: float = 24.0) -> int:
        """Count ceremony_key_rotated events within the last within_hours hours (Phase 79)."""
        cutoff = time.time() - within_hours * 3600
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM agent_events "
                "WHERE event_type='ceremony_key_rotated' AND created_at > ?",
                (cutoff,),
            ).fetchone()
            return int(row["cnt"]) if row else 0

    def insert_class_j_assessment(
        self,
        device_id: str,
        entropy_variance: float,
        risk_level: str,
        window_count: int,
    ) -> int:
        """Insert a Class J ML-bot risk assessment (Phase 81). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO class_j_assessments "
                "(device_id, entropy_variance, risk_level, window_count, assessed_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (device_id, entropy_variance, risk_level, window_count, time.time()),
            )
            return cur.lastrowid

    def get_class_j_assessment(self, device_id: str) -> dict | None:
        """Return most recent Class J assessment for device_id (Phase 81)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM class_j_assessments WHERE device_id=? "
                "ORDER BY assessed_at DESC LIMIT 1",
                (device_id,),
            ).fetchone()
            return dict(row) if row else None

    def get_agent_activity(
        self,
        table: str,
        ts_col: str,
        filter_sql: str | None = None,
        device_col: str | None = None,
    ) -> dict:
        """Return last-activity metrics for an agent's table (Phase 83).

        Returns last_active_at, activity_count, and distinct_devices.
        W1 mitigation: distinct_devices distinguishes genuine agent activity from
        a zombie writing to a single device in a tight loop.
        """
        where = f"WHERE {filter_sql}" if filter_sql else ""
        with self._conn() as conn:
            row = conn.execute(
                f"SELECT MAX({ts_col}), COUNT(*) FROM {table} {where}"
            ).fetchone()
            last_active_at = row[0] if row else None
            activity_count = int(row[1]) if row else 0

            distinct = None
            if device_col:
                d_row = conn.execute(
                    f"SELECT COUNT(DISTINCT {device_col}) FROM {table} {where}"
                ).fetchone()
                distinct = int(d_row[0]) if d_row else 0

        return {
            "last_active_at": last_active_at,
            "activity_count": activity_count,
            "distinct_devices": distinct,
        }

    def insert_supervisor_health_log(
        self,
        agent_name: str,
        health: str,
        last_active_at: float | None,
        activity_count: int = 0,
    ) -> int:
        """Persist an agent health check result (Phase 83). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO supervisor_health_log "
                "(agent_name, health, last_active_at, activity_count, checked_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (agent_name, health, last_active_at, activity_count, time.time()),
            )
            return cur.lastrowid

    def get_latest_supervisor_health(self) -> list[dict]:
        """Return the most recent health check row per agent (Phase 83)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT s.*
                FROM supervisor_health_log s
                INNER JOIN (
                    SELECT agent_name, MAX(checked_at) AS max_checked
                    FROM supervisor_health_log
                    GROUP BY agent_name
                ) latest ON s.agent_name = latest.agent_name
                          AND s.checked_at = latest.max_checked
                ORDER BY s.agent_name
                """
            ).fetchall()
            return [dict(r) for r in rows]

    def insert_reactive_adjudication_log(
        self,
        device_id: str,
        triggered_by: str,
        entropy_variance: float | None,
        verdict: str | None,
        was_deferred: bool = False,
    ) -> int:
        """Log a reactive adjudication interrupt attempt (Phase 82). Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO reactive_adjudication_log "
                "(device_id, triggered_by, entropy_variance, verdict, was_deferred, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (device_id, triggered_by, entropy_variance, verdict,
                 1 if was_deferred else 0, time.time()),
            )
            return cur.lastrowid

    def get_reactive_adjudication_log(
        self, device_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Return recent reactive adjudication log entries (Phase 82).

        If device_id is provided, filters to that device only.
        Returns newest-first, at most limit rows.
        """
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM reactive_adjudication_log "
                    "WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM reactive_adjudication_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]

    def insert_synthetic_session(
        self,
        session_id: str,
        device_id: str,
        inference_code: int,
        humanity_score: float,
        fallback_verdict: str,
        fallback_confidence: float,
        passed_fallback: int,
        corpus_run_id: str | None = None,
    ) -> int:
        """Insert synthetic session result. INSERT OR IGNORE (idempotent by session_id)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO synthetic_sessions "
                "(session_id, device_id, inference_code, humanity_score, "
                " fallback_verdict, fallback_confidence, passed_fallback, corpus_run_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, device_id, inference_code, humanity_score,
                 fallback_verdict, fallback_confidence, passed_fallback, corpus_run_id),
            )
            conn.commit()
            return cur.lastrowid or 0

    def get_corpus_status(self) -> dict:
        """Return synthetic corpus aggregate statistics (Phase 86)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(passed_fallback) as passed, "
                "COUNT(DISTINCT corpus_run_id) as run_count, "
                "MAX(created_at) as last_run_at "
                "FROM synthetic_sessions"
            ).fetchone()
        if not row or not row["total"]:
            return {
                "total": 0, "passed": 0, "failed": 0,
                "run_count": 0, "last_run_at": None,
                "isolation_note": (
                    "Synthetic sessions do NOT count toward production gate "
                    "consecutive_clean (Phase 86 W1 isolation invariant)."
                ),
            }
        total = int(row["total"] or 0)
        passed = int(row["passed"] or 0)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "run_count": int(row["run_count"] or 0),
            "last_run_at": row["last_run_at"],
            "isolation_note": (
                "Synthetic sessions do NOT count toward production gate "
                "consecutive_clean (Phase 86 W1 isolation invariant)."
            ),
        }

    def insert_protocol_intelligence_report(self, report: dict) -> int:
        """Insert a protocol intelligence report. Returns row id."""
        components = report.get("components", {})
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_intelligence_reports "
                "(protocol_health_score, gate_progress_score, fleet_health_score, "
                "divergence_clarity_score, corpus_pass_score, class_j_confidence_score, "
                "shadow_pass_score, triage_confidence_score, ready_for_live_mode, "
                "bottleneck, estimated_days_to_gate, components_json, recommendation, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    float(report.get("protocol_health_score", 0.0)),
                    float(components.get("gate_progress", 0.0)) / 35.0
                    if components.get("gate_progress") is not None else 0.0,
                    float(components.get("fleet_health", 0.0)) / 25.0
                    if components.get("fleet_health") is not None else 0.0,
                    float(components.get("divergence_clarity", 0.0)) / 20.0
                    if components.get("divergence_clarity") is not None else 0.0,
                    float(components.get("corpus_pass", 0.0)) / 10.0
                    if components.get("corpus_pass") is not None else 0.0,
                    float(components.get("class_j_confidence", 0.0)) / 10.0
                    if components.get("class_j_confidence") is not None else 0.0,
                    float(components["shadow_pass"]) / 5.0 if "shadow_pass" in components else None,
                    float(components["triage_confidence"]) / 5.0
                    if "triage_confidence" in components else None,
                    int(bool(report.get("ready_for_live_mode", False))),
                    report.get("bottleneck"),
                    report.get("estimated_days_to_gate"),
                    report.get("components_json", "{}"),
                    report.get("recommendation", ""),
                    float(report.get("created_at", time.time())),
                ),
            )
            return cur.lastrowid

    def get_latest_protocol_intelligence_report(self) -> dict | None:
        """Return the most recent protocol intelligence report, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM protocol_intelligence_reports "
                "ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        try:
            result["components"] = json.loads(result.get("components_json") or "{}")
        except (json.JSONDecodeError, TypeError):
            result["components"] = {}
        return result

    def insert_shadow_enforcement_log(
        self,
        device_id: str,
        ruling_id,
        commitment_hash,
        would_have_suspended: int,
        duration_s=None,
        warmup_attack_score=None,
    ) -> int:
        """Log a shadow enforcement event (BLOCK in shadow mode)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO shadow_enforcement_log "
                "(device_id, ruling_id, verdict, commitment_hash, "
                "would_have_suspended, duration_s, warmup_attack_score) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    device_id, ruling_id, "BLOCK", commitment_hash,
                    int(would_have_suspended), duration_s, warmup_attack_score,
                ),
            )
            return cur.lastrowid

    def get_shadow_enforcement_log(self, device_id=None, limit: int = 50) -> list:
        """Return recent shadow enforcement log entries."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM shadow_enforcement_log WHERE device_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM shadow_enforcement_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def get_shadow_enforcement_stats(self) -> dict:
        """Return aggregate shadow enforcement statistics."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as total, "
                "SUM(CASE WHEN would_have_suspended=0 THEN 1 ELSE 0 END) as passed, "
                "SUM(would_have_suspended) as would_have_suspended "
                "FROM shadow_enforcement_log"
            ).fetchone()
        total = int(row["total"] or 0)
        passed = int(row["passed"] or 0)
        suspended = int(row["would_have_suspended"] or 0)
        return {
            "total": total,
            "passed": passed,
            "would_have_suspended": suspended,
            "pass_rate": round(passed / total, 4) if total > 0 else None,
        }

    def insert_divergence_triage_report(
        self,
        device_id: str,
        divergence_count: int,
        escalated: int,
        patterns,
        ml_bot_high_count: int,
        cheat_count: int,
        enrollment_anomaly_count: int,
    ) -> int:
        """Insert triage report for device."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO divergence_triage_reports "
                "(device_id, divergence_count, escalated, patterns, "
                "ml_bot_high_count, cheat_count, enrollment_anomaly_count) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    device_id, int(divergence_count), int(escalated), patterns,
                    int(ml_bot_high_count), int(cheat_count), int(enrollment_anomaly_count),
                ),
            )
            return cur.lastrowid

    def get_divergence_triage_report(self, limit: int = 50) -> list:
        """Return most recent triage entry per device, escalated first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT t.* FROM divergence_triage_reports t "
                "INNER JOIN (SELECT device_id, MAX(assessed_at) as latest "
                "FROM divergence_triage_reports GROUP BY device_id) latest "
                "ON t.device_id=latest.device_id AND t.assessed_at=latest.latest "
                "ORDER BY t.escalated DESC, t.assessed_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_escalation_ruling_log(
        self,
        device_id: str,
        patterns,
        verdict,
        ruling_id,
        was_deferred: bool,
    ) -> int:
        """Insert an escalation ruling log entry."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO escalation_ruling_log "
                "(device_id, patterns, verdict, ruling_id, was_deferred) "
                "VALUES (?,?,?,?,?)",
                (device_id, patterns, verdict, ruling_id, int(was_deferred)),
            )
            return cur.lastrowid

    def get_escalation_ruling_log(self, device_id=None, limit: int = 50) -> list:
        """Return escalation ruling log entries."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT * FROM escalation_ruling_log WHERE device_id=? "
                    "ORDER BY created_at DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM escalation_ruling_log "
                    "ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def insert_agent_calibration_health(
        self,
        agent_id: int,
        agent_name: str,
        test_name: str,
        result: str,
        details: str = "",
    ) -> int:
        """Insert an agent self-test result (Phase 148)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO agent_calibration_health "
                "(agent_id, agent_name, test_name, result, details, calibration_ts, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (agent_id, agent_name, test_name, result, details,
                 time.time(), time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_agent_calibration_health(self, limit: int = 32, agent_id: int | None = None) -> list:
        """Return agent calibration health rows ordered by id DESC (Phase 148)."""
        with self._conn() as con:
            if agent_id is not None:
                rows = con.execute(
                    "SELECT * FROM agent_calibration_health WHERE agent_id=? ORDER BY id DESC LIMIT ?",
                    (agent_id, limit),
                ).fetchall()
            else:
                rows = con.execute(
                    "SELECT * FROM agent_calibration_health ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def upsert_agent_context_hash(
        self,
        agent_id: str,
        prompt_sha256: str,
        phase_number: int,
    ) -> int:
        """Insert or ignore an agent context hash record (Phase 203).

        UNIQUE(agent_id, prompt_sha256) — same hash for same agent is a no-op.
        Returns the row id of the inserted or existing record.
        """
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO agent_context_log "
                "(agent_id, prompt_sha256, phase_number, created_at)"
                " VALUES (?,?,?,?)",
                (agent_id, prompt_sha256, int(phase_number), time.time()),
            )
            row = conn.execute(
                "SELECT id FROM agent_context_log "
                "WHERE agent_id=? AND prompt_sha256=? LIMIT 1",
                (agent_id, prompt_sha256),
            ).fetchone()
        return int(row["id"]) if row else 0

    def get_agent_context_status(
        self, agent_id: str
    ) -> "dict | None":
        """Return the latest agent context hash record for an agent (Phase 203)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM agent_context_log "
                "WHERE agent_id=? ORDER BY id DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
        if row is None:
            return None
        return dict(row)

    def get_all_agent_context_status(self) -> "list[dict]":
        """Return the latest context hash record for all agents (Phase 203)."""
        with self._conn() as conn:
            rows = conn.execute(
                """
                SELECT a.* FROM agent_context_log a
                INNER JOIN (
                    SELECT agent_id, MAX(id) as max_id
                    FROM agent_context_log GROUP BY agent_id
                ) b ON a.agent_id = b.agent_id AND a.id = b.max_id
                ORDER BY a.agent_id
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def insert_mythos_cadence_run(
        self,
        *,
        variant: str,
        cadence: str,
        findings_count: int,
        duration_ms: int,
        triggered_by: str = "schedule",
        error: str | None = None,
    ) -> int:
        """Persist one cadence-engine wakeup record for a variant. Returns
        new row id; 0 on error. Fail-open."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO mythos_cadence_log "
                    "(variant, cadence, findings_count, duration_ms, "
                    " triggered_by, error, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(variant),
                        str(cadence),
                        int(findings_count),
                        int(duration_ms),
                        str(triggered_by),
                        error,
                        time.time(),
                    ),
                )
                return int(cur.lastrowid or 0)
        except Exception:
            return 0

    def get_mythos_findings(
        self,
        *,
        variant: str | None = None,
        severity: str | None = None,
        unresolved_only: bool = False,
        limit: int = 50,
    ) -> list[dict]:
        """Read Mythos findings with optional filters. Fail-open: returns
        [] on any DB error."""
        try:
            sql = "SELECT * FROM mythos_finding_log WHERE 1=1"
            args: list = []
            if variant:
                sql += " AND variant = ?"
                args.append(str(variant))
            if severity:
                sql += " AND severity = ?"
                args.append(str(severity).upper())
            if unresolved_only:
                sql += " AND resolved = 0"
            sql += " ORDER BY created_at DESC LIMIT ?"
            args.append(max(1, min(int(limit), 500)))
            with self._conn() as conn:
                rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_mythos_cadence_status(self) -> dict:
        """Summary of cadence-engine activity. Fail-open: returns
        {variants: {}, total_runs: 0, ...} on DB error."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT variant, COUNT(*) AS n_runs, "
                    "       SUM(findings_count) AS total_findings, "
                    "       MAX(created_at) AS last_run_ts "
                    "FROM mythos_cadence_log "
                    "GROUP BY variant"
                ).fetchall()
            variants: dict = {}
            total_runs = 0
            total_findings = 0
            for r in rows:
                d = dict(r)
                vname = d["variant"]
                variants[vname] = {
                    "n_runs": int(d["n_runs"] or 0),
                    "total_findings": int(d["total_findings"] or 0),
                    "last_run_ts": float(d["last_run_ts"] or 0.0),
                }
                total_runs += int(d["n_runs"] or 0)
                total_findings += int(d["total_findings"] or 0)
            return {
                "variants": variants,
                "total_runs": total_runs,
                "total_findings": total_findings,
                "timestamp": time.time(),
            }
        except Exception:
            return {"variants": {}, "total_runs": 0, "total_findings": 0, "timestamp": time.time()}

    def update_grind_chain_hash(
        self, row_id: int, gic_hex: str, ts_ns: int, grind_session_id: str = ""
    ) -> None:
        """Stamp a completed GIC hash, timestamp, and session ID on a validation row.

        INV-GIC-001 fix: grind_session_id is now persisted so get_prev_grind_chain_hash
        can scope lookups to the correct session.
        """
        with self._conn() as conn:
            conn.execute(
                "UPDATE ruling_validation_log "
                "SET grind_chain_hash = ?, gic_ts_ns = ?, grind_session_id = ? "
                "WHERE id = ?",
                (gic_hex, ts_ns, grind_session_id or None, row_id),
            )

    def get_ruling_rows_for_chain(self, grind_session_id: str = "") -> list[dict]:
        """Return GIC-stamped validation rows ordered by gic_ts_ns ASC.

        INV-GIC-001 fix: when grind_session_id is provided, only rows belonging to
        that session are returned, preventing cross-session chain reconstruction.
        """
        with self._conn() as conn:
            if grind_session_id:
                rows = conn.execute(
                    "SELECT rvl.id, rvl.grind_chain_hash, rvl.pcc_host_state, "
                    "       rvl.fallback_verdict, rvl.gic_ts_ns, "
                    "       ar.commitment_hash "
                    "FROM ruling_validation_log AS rvl "
                    "JOIN agent_rulings AS ar ON ar.id = rvl.ruling_id "
                    "WHERE rvl.grind_chain_hash IS NOT NULL "
                    "AND rvl.grind_session_id = ? "
                    "ORDER BY rvl.gic_ts_ns ASC",
                    (grind_session_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT rvl.id, rvl.grind_chain_hash, rvl.pcc_host_state, "
                    "       rvl.fallback_verdict, rvl.gic_ts_ns, "
                    "       ar.commitment_hash "
                    "FROM ruling_validation_log AS rvl "
                    "JOIN agent_rulings AS ar ON ar.id = rvl.ruling_id "
                    "WHERE rvl.grind_chain_hash IS NOT NULL "
                    "ORDER BY rvl.gic_ts_ns ASC",
                ).fetchall()
        return [dict(r) for r in rows]

    def get_grind_chain_status(self, grind_session_id: str, cfg=None) -> dict:
        """Recompute and verify the full GIC chain.

        Returns:
            grind_session_id, chain_length, latest_gic_hash (hex), chain_intact (bool),
            genesis_ts (float), latest_ts (float).
        """
        from ..grind_chain import compute_gic, genesis_gic

        rows = self.get_ruling_rows_for_chain(grind_session_id)
        if not rows:
            return {
                "grind_session_id":  grind_session_id,
                "chain_length":      0,
                "latest_gic_hash":   "",
                "chain_intact":      True,  # empty chain is vacuously intact
                "genesis_ts":        0.0,
                "latest_ts":         0.0,
            }

        chain_intact = True

        for i, row in enumerate(rows):
            ts_ns = int(row.get("gic_ts_ns") or 0)
            commitment_hex = row.get("commitment_hash") or ""
            pcc_host = row.get("pcc_host_state") or "DISCONNECTED"
            verdict = row.get("fallback_verdict") or "FLAG"
            stored_hex = row.get("grind_chain_hash") or ""

            if i == 0:
                # Session 1: genesis_gic anchors with same ts_ns; compute_gic folds in session data.
                genesis = genesis_gic(grind_session_id, ts_ns)
                expected = compute_gic(genesis, commitment_hex, pcc_host, verdict, ts_ns)
            else:
                expected = compute_gic(
                    bytes.fromhex(rows[i - 1]["grind_chain_hash"]),
                    commitment_hex, pcc_host, verdict, ts_ns,
                )

            if expected.hex() != stored_hex:
                chain_intact = False
                break

        genesis_ts = float(rows[0].get("gic_ts_ns", 0)) / 1e9 if rows[0].get("gic_ts_ns") else 0.0
        latest_ts = float(rows[-1].get("gic_ts_ns", 0)) / 1e9 if rows[-1].get("gic_ts_ns") else 0.0

        return {
            "grind_session_id":  grind_session_id,
            "chain_length":      len(rows),
            "latest_gic_hash":   rows[-1]["grind_chain_hash"],
            "chain_intact":      chain_intact,
            "genesis_ts":        genesis_ts,
            "latest_ts":         latest_ts,
        }

    def get_prev_gic_ts_ns(self) -> int:
        """Return the maximum gic_ts_ns across all GIC-stamped rows (0 if none).

        Used to enforce monotonicity in GIC timestamp sequence.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(gic_ts_ns) FROM ruling_validation_log WHERE gic_ts_ns IS NOT NULL"
            ).fetchone()
        if row and row[0] is not None:
            return int(row[0])
        return 0

    def insert_agent_commit(
        self,
        commit_hash: str,
        agent_id: str,
        commit_sha: str,
        prev_commit_hash: str,
        repo_uri_sha: str,
        ts_ns: int,
        tx_hash: str = "",
        on_chain_confirmed: bool = False,
        anchor_id: int = -1,
    ) -> int:
        """Insert one AGENT_COMMIT v1 row into agent_commit_log. Returns row id.

        UNIQUE(commit_hash) enforced — duplicate inserts (same agent_commit
        hash from re-running the same git commit attestation) are idempotent:
        the duplicate raises sqlite3.IntegrityError which we translate to
        "already recorded" by returning the existing row id. Mirrors the
        pattern from insert_corpus_snapshot.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO agent_commit_log "
                    "(commit_hash, agent_id, commit_sha, prev_commit_hash, "
                    " repo_uri_sha, ts_ns, tx_hash, on_chain_confirmed, "
                    " anchor_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(commit_hash), str(agent_id), str(commit_sha),
                        str(prev_commit_hash), str(repo_uri_sha), int(ts_ns),
                        str(tx_hash), 1 if on_chain_confirmed else 0,
                        int(anchor_id), time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM agent_commit_log WHERE commit_hash = ?",
                    (str(commit_hash),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_agent_commit_status(self) -> dict:
        """Return latest AGENT_COMMIT v1 record summary.

        Returns 8 keys: total_commits, latest_hash, latest_agent_id,
        latest_commit_sha, latest_ts_ns, on_chain_confirmed, anchor_id,
        timestamp.
        """
        import time as _tac
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM agent_commit_log"
            ).fetchone()["n"]
            row = conn.execute(
                "SELECT commit_hash, agent_id, commit_sha, ts_ns, "
                "       on_chain_confirmed, anchor_id "
                "FROM agent_commit_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "total_commits":      0,
                "latest_hash":        "",
                "latest_agent_id":    "",
                "latest_commit_sha":  "",
                "latest_ts_ns":       0,
                "on_chain_confirmed": False,
                "anchor_id":          -1,
                "timestamp":          _tac.time(),
            }
        return {
            "total_commits":      int(total),
            "latest_hash":        str(row["commit_hash"]),
            "latest_agent_id":    str(row["agent_id"]),
            "latest_commit_sha":  str(row["commit_sha"]),
            "latest_ts_ns":       int(row["ts_ns"]),
            "on_chain_confirmed": bool(row["on_chain_confirmed"]),
            "anchor_id":          int(row["anchor_id"]),
            "timestamp":          _tac.time(),
        }

    def get_agent_commit_history(self, agent_id: str = "", limit: int = 20) -> list[dict]:
        """Return last N AGENT_COMMIT v1 records, optionally filtered by agent_id.

        DESC ts_ns ordering (newest first). agent_id="" means all agents.
        """
        with self._conn() as conn:
            if agent_id:
                rows = conn.execute(
                    "SELECT id, commit_hash, agent_id, commit_sha, "
                    "       prev_commit_hash, repo_uri_sha, ts_ns, "
                    "       tx_hash, on_chain_confirmed, anchor_id, created_at "
                    "FROM agent_commit_log WHERE agent_id = ? "
                    "ORDER BY ts_ns DESC LIMIT ?",
                    (str(agent_id), int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, commit_hash, agent_id, commit_sha, "
                    "       prev_commit_hash, repo_uri_sha, ts_ns, "
                    "       tx_hash, on_chain_confirmed, anchor_id, created_at "
                    "FROM agent_commit_log ORDER BY ts_ns DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]
