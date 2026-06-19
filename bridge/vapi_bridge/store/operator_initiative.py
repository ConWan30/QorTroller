"""OperatorInitiativeMixin — D-DECON-2 operator_initiative domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern
(removal diff is the canonical source). The auto_supersede + chain_spending
clusters (INV-O3-SUPERSEDE-003 / INV-PATH-B-002, no _init_schema anchor) and
_init_schema itself STAY in _core.py per the 2026-06-19 FROZEN-span scan;
only the 26 unpinned domain methods move here. Resolved via MRO.
"""
from __future__ import annotations

import time


class OperatorInitiativeMixin:
    """Operator Initiative (activation/shadow/drift/drafts/advancement) methods
    extracted from Store; resolved via MRO."""
    def get_operator_agent_activation_log(
        self,
        agent_id: str | None = None,
        limit: int = 20,
    ) -> list[dict]:
        """Return paginated activation history (most recent first).

        If agent_id is None, returns rows for all agents.  Otherwise filters
        to the specific Q9-frozen agentId.  Caps at 200 rows regardless of
        requested limit to prevent unbounded queries.
        """
        limit = max(1, min(200, int(limit)))
        with self._conn() as conn:
            if agent_id is None:
                rows = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "ORDER BY activated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "WHERE agent_id = ? ORDER BY activated_at DESC LIMIT ?",
                    (agent_id, limit),
                ).fetchall()
            return [dict(r) for r in rows]

    def get_current_operational_phase(self, agent_id: str) -> str:
        """Return latest to_phase for the agent, or 'O0_DORMANT' if no activations.

        This is the off-chain mirror of the agent's on-chain operational state.
        FSCA SCOPE_HASH_GOVERNANCE_DRIFT (Phase O1 C2/C3 deferred) cross-checks
        this against AgentScope.getScopeRoot to detect divergence.
        """
        with self._conn() as conn:
            row_get_to_phase = conn.execute(
                "SELECT to_phase FROM operator_agent_activation_log "
                "WHERE agent_id = ? ORDER BY activated_at DESC LIMIT 1",
                (agent_id,),
            ).fetchone()
            if row_get_to_phase is None:
                return "O0_DORMANT"
            return str(row_get_to_phase["to_phase"])

    def get_operator_agent_shadow_log(
        self,
        agent_id: str | None = None,
        decision_filter: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Paginated shadow log read (most recent first).

        Args:
            agent_id: filter to one agent or None for all
            decision_filter: filter to one CedarDecision value or None for all
            limit: capped at 500 to prevent unbounded queries
        """
        limit = max(1, min(500, int(limit)))
        with self._conn() as conn:
            sql = "SELECT * FROM operator_agent_shadow_log WHERE 1=1"
            args: list = []
            if agent_id is not None:
                sql += " AND agent_id = ?"
                args.append(agent_id)
            if decision_filter is not None:
                sql += " AND decision = ?"
                args.append(decision_filter)
            sql += " ORDER BY evaluated_at DESC LIMIT ?"
            args.append(limit)
            rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(r) for r in rows]

    def get_operator_agent_shadow_summary(
        self,
        agent_id: str | None = None,
    ) -> dict:
        """Aggregated decision counts for an agent (or fleet-wide).

        Returns:
            {
                "total": int,
                "by_decision": {decision: count, ...},
                "latest_at": float | None,
                "earliest_at": float | None,
            }
        """
        with self._conn() as conn:
            base_where = "WHERE agent_id = ?" if agent_id else ""
            base_args = (agent_id,) if agent_id else ()
            total = conn.execute(
                f"SELECT COUNT(*) FROM operator_agent_shadow_log {base_where}",
                base_args,
            ).fetchone()[0]
            by_dec_rows = conn.execute(
                f"SELECT decision, COUNT(*) as n FROM operator_agent_shadow_log "
                f"{base_where} GROUP BY decision",
                base_args,
            ).fetchall()
            by_decision = {r["decision"]: int(r["n"]) for r in by_dec_rows}
            ts_row = conn.execute(
                f"SELECT MIN(evaluated_at) as earliest, MAX(evaluated_at) as latest "
                f"FROM operator_agent_shadow_log {base_where}",
                base_args,
            ).fetchone()
            return {
                "total":       int(total),
                "by_decision": by_decision,
                "latest_at":   ts_row["latest"] if ts_row else None,
                "earliest_at": ts_row["earliest"] if ts_row else None,
            }

    def get_operator_agent_drift_log(
        self,
        agent_id: str | None = None,
        drift_type: str | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Paginated drift log read (most recent first)."""
        limit = max(1, min(500, int(limit)))
        with self._conn() as conn:
            sql = "SELECT * FROM operator_agent_drift_log WHERE 1=1"
            args: list = []
            if agent_id is not None:
                sql += " AND agent_id = ?"
                args.append(agent_id)
            if drift_type is not None:
                sql += " AND drift_type = ?"
                args.append(drift_type)
            sql += " ORDER BY detected_at DESC LIMIT ?"
            args.append(limit)
            return [dict(r) for r in conn.execute(sql, tuple(args)).fetchall()]

    def get_latest_operator_agent_activation(self, agent_id: str) -> dict | None:
        """Return the most-recent activation_log row for one agent, with
        watcher-compatible field shape (bundle_filename + anchored_at_unix).

        Returns None when no activation exists.  Never raises."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "WHERE agent_id = ? "
                    "ORDER BY activated_at DESC LIMIT 1",
                    (agent_id,),
                ).fetchone()
            if row is None:
                return None
            d = dict(row)
            bundle_path = str(d.get("bundle_path", "") or "")
            d["bundle_filename"] = bundle_path.replace("\\", "/").rsplit("/", 1)[-1] if bundle_path else ""
            d["anchored_at_unix"] = float(d.get("activated_at", 0.0) or 0.0)
            return d
        except Exception:
            return None

    def get_first_operator_agent_activation(self, agent_id: str) -> dict | None:
        """Return the EARLIEST activation_log row for one agent (= when
        shadow observation began).  Same field shape as
        get_latest_operator_agent_activation.  Never raises."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM operator_agent_activation_log "
                    "WHERE agent_id = ? "
                    "ORDER BY activated_at ASC LIMIT 1",
                    (agent_id,),
                ).fetchone()
            if row is None:
                return None
            d = dict(row)
            bundle_path = str(d.get("bundle_path", "") or "")
            d["bundle_filename"] = bundle_path.replace("\\", "/").rsplit("/", 1)[-1] if bundle_path else ""
            d["anchored_at_unix"] = float(d.get("activated_at", 0.0) or 0.0)
            return d
        except Exception:
            return None

    def count_cedar_shadow_evaluations(self, agent_id: str) -> int:
        """Count rows in operator_agent_shadow_log for an agent.  Used by
        Phase O2 SUGGEST gate (PHASE_O2_EVAL_MIN_COUNT=100).  Returns 0
        on any failure (fail-open per INV-INITIATIVE-ADVANCEMENT-002)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_shadow_log "
                    "WHERE agent_id = ?",
                    (agent_id,),
                ).fetchone()
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    def count_operator_agent_drift_findings(
        self,
        *,
        agent_id: str,
        drift_type: str,
        since_seconds: int,
    ) -> int:
        """Count drift findings of a given type for an agent within the
        last N seconds.  Used by Phase O2 SUGGEST gate to enforce
        bundle/scope drift = 0 over the trailing 30-day window.  Returns 0
        on any failure (fail-open)."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_drift_log "
                    "WHERE agent_id = ? AND drift_type = ? AND detected_at >= ?",
                    (agent_id, drift_type, cutoff),
                ).fetchone()
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    def insert_operator_agent_draft(
        self,
        *,
        agent_id: str,
        action_category: str,   # 'skill' | 'tool'
        action_name: str,        # e.g. 'kms-sign' or 'provenance-recording'
        draft_uri: str,          # full draft://... URI
        payload_hash: str,       # SHA-256 of payload body, lowercase hex
        payload_bytes: int,
        kms_sig_present: bool = False,
    ) -> int:
        """Persist one draft payload produced by an Operator agent under
        O2 SUGGEST authority. Returns new row id; 0 on UNIQUE collision
        (same agent_id+payload_hash already persisted -- idempotent)."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO operator_agent_drafts "
                    "(agent_id, action_category, action_name, draft_uri, "
                    " payload_hash, payload_bytes, kms_sig_present, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(agent_id),
                        str(action_category),
                        str(action_name),
                        str(draft_uri),
                        str(payload_hash),
                        int(payload_bytes),
                        1 if kms_sig_present else 0,
                        time.time(),
                    ),
                )
                if cur.lastrowid:
                    return int(cur.lastrowid)
                # UNIQUE collision -- return existing row id
                row = conn.execute(
                    "SELECT id FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND payload_hash = ?",
                    (str(agent_id), str(payload_hash)),
                ).fetchone()
                return int(row["id"]) if row else 0
        except Exception:
            return 0

    def count_operator_agent_drafts(
        self,
        *,
        agent_id: str,
        since_seconds: int,
    ) -> int:
        """Count drafts produced by an agent within the last N seconds.
        Used by Phase O3-ACT-WATCHER PHASE_O3_DRAFT_PAYLOAD_MIN gate
        (default 50 drafts in a 30-day window). Returns 0 on any failure
        (fail-open per INV-INITIATIVE-ADVANCEMENT-002)."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS n FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND created_at >= ?",
                    (str(agent_id), cutoff),
                ).fetchone()
            return int(row["n"]) if row else 0
        except Exception:
            return 0

    def record_operator_decision(
        self,
        *,
        draft_id: int,
        decision: str,           # 'accept' | 'reject' | 'overturn_curator'
        reason: str | None = None,
    ) -> bool:
        """Operator review of a draft -- updates operator_decision +
        operator_decision_at + (optional) operator_disagreement_reason.
        Idempotent: re-recording the same decision is a no-op; recording
        a different decision overwrites (operator may revise their own
        review). Returns True on success, False on missing draft."""
        if decision not in ("accept", "reject", "overturn_curator"):
            return False
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "UPDATE operator_agent_drafts "
                    "SET operator_decision = ?, "
                    "    operator_decision_at = ?, "
                    "    operator_disagreement_reason = ? "
                    "WHERE id = ?",
                    (
                        str(decision),
                        time.time(),
                        str(reason) if reason else None,
                        int(draft_id),
                    ),
                )
                return int(cur.rowcount) > 0
        except Exception:
            return False

    def compute_operator_agent_disagreement_rate(
        self,
        *,
        agent_id: str,
        since_seconds: int,
    ) -> float:
        """Fraction of REVIEWED drafts where operator rejected.
        denominator = drafts with operator_decision IN ('accept', 'reject')
                      created within window
        numerator   = drafts with operator_decision = 'reject'
                      created within window

        Excludes 'overturn_curator' (Curator-specific; tracked separately
        by compute_operator_agent_false_positive_rate). Excludes drafts
        with NULL operator_decision (unreviewed -- not part of disagreement
        signal).

        Returns 0.0 on:
          - any DB failure
          - zero reviewed drafts in window (no signal yet)

        Used by Phase O3-ACT-WATCHER PHASE_O3_DISAGREEMENT_RATE_MAX gate
        (default 0.05 = 5%). Fail-open."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT "
                    "  SUM(CASE WHEN operator_decision = 'reject' THEN 1 ELSE 0 END) AS n_reject, "
                    "  SUM(CASE WHEN operator_decision IN ('accept','reject') THEN 1 ELSE 0 END) AS n_reviewed "
                    "FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND created_at >= ?",
                    (str(agent_id), cutoff),
                ).fetchone()
            if not row:
                return 0.0
            n_reject = int(row["n_reject"] or 0)
            n_reviewed = int(row["n_reviewed"] or 0)
            if n_reviewed <= 0:
                return 0.0
            return float(n_reject) / float(n_reviewed)
        except Exception:
            return 0.0

    def compute_operator_agent_false_positive_rate(
        self,
        *,
        agent_id: str,
        since_seconds: int,
    ) -> float:
        """Fraction of REVIEWED drafts where operator overturned the agent's
        verdict. Curator-specific: marketplace-listing-review verdicts that
        the operator reverses post-review count as false positives.

        denominator = drafts with operator_decision IN ('accept','reject',
                      'overturn_curator') created within window
        numerator   = drafts with operator_decision = 'overturn_curator'
                      created within window

        Returns 0.0 on:
          - any DB failure
          - zero reviewed drafts in window (no signal yet)

        Used by Phase O3-ACT-WATCHER PHASE_O3_FALSE_POSITIVE_RATE_MAX gate
        (Curator-only; default 0.0 = zero tolerance). Fail-open."""
        try:
            cutoff = time.time() - max(0, int(since_seconds))
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT "
                    "  SUM(CASE WHEN operator_decision = 'overturn_curator' THEN 1 ELSE 0 END) AS n_overturn, "
                    "  SUM(CASE WHEN operator_decision IN ('accept','reject','overturn_curator') THEN 1 ELSE 0 END) AS n_reviewed "
                    "FROM operator_agent_drafts "
                    "WHERE agent_id = ? AND created_at >= ?",
                    (str(agent_id), cutoff),
                ).fetchone()
            if not row:
                return 0.0
            n_overturn = int(row["n_overturn"] or 0)
            n_reviewed = int(row["n_reviewed"] or 0)
            if n_reviewed <= 0:
                return 0.0
            return float(n_overturn) / float(n_reviewed)
        except Exception:
            return 0.0

    def get_operator_agent_drafts(
        self,
        *,
        agent_id: str | None = None,
        decision: str | None = None,
        since_seconds: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Return drafts (most recent first), filtered by agent / decision /
        time window. Capped at 500 rows. Used by operator review surface
        (frontend dashboards) and by audit query tooling."""
        limit = max(1, min(500, int(limit)))
        try:
            sql = "SELECT * FROM operator_agent_drafts WHERE 1=1"
            args: list = []
            if agent_id is not None:
                sql += " AND agent_id = ?"
                args.append(str(agent_id))
            if decision is not None:
                sql += " AND operator_decision = ?"
                args.append(str(decision))
            if since_seconds is not None:
                cutoff = time.time() - max(0, int(since_seconds))
                sql += " AND created_at >= ?"
                args.append(cutoff)
            sql += " ORDER BY created_at DESC LIMIT ?"
            args.append(limit)
            with self._conn() as conn:
                rows = conn.execute(sql, tuple(args)).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def insert_operator_initiative_advancement_log(
        self,
        *,
        timestamp: float,
        fleet_phase_aligned: bool,
        fleet_at_o1_count: int,
        fleet_at_o2_ready_count: int,
        fleet_at_o3_ready_count: int,
        next_alignment_target: str,
        per_agent_json: str,
        frr_hex: str = "",
        frr_ts_ns: int = 0,
        error: str | None = None,
    ) -> int:
        """Persist one fleet-advancement evaluation cycle, including the
        FRR commitment.  Returns new row id; raises sqlite3.Error only
        on hard DB failures (caller handles)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO operator_initiative_advancement_log "
                "(timestamp, fleet_phase_aligned, fleet_at_o1_count, "
                "fleet_at_o2_ready_count, fleet_at_o3_ready_count, "
                "next_alignment_target, per_agent_json, frr_hex, frr_ts_ns, "
                "error, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    float(timestamp),
                    1 if fleet_phase_aligned else 0,
                    int(fleet_at_o1_count),
                    int(fleet_at_o2_ready_count),
                    int(fleet_at_o3_ready_count),
                    str(next_alignment_target),
                    str(per_agent_json),
                    str(frr_hex or ""),
                    int(frr_ts_ns or 0),
                    str(error) if error else None,
                    time.time(),
                ),
            )
            return int(cur.lastrowid)

    def get_latest_operator_initiative_advancement(self) -> dict | None:
        """Return the most-recent advancement-log row, or None."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT * FROM operator_initiative_advancement_log "
                    "ORDER BY timestamp DESC LIMIT 1",
                ).fetchone()
            return dict(row) if row else None
        except Exception:
            return None

    def get_operator_initiative_advancement_history(self, limit: int = 50) -> list[dict]:
        """Return advancement-log history (most recent first), capped at 500."""
        limit = max(1, min(500, int(limit)))
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM operator_initiative_advancement_log "
                    "ORDER BY timestamp DESC LIMIT ?",
                    (limit,),
                ).fetchall()
            return [dict(r) for r in rows]
        except Exception:
            return []

    def get_accepted_unexecuted_drafts(
        self, agent_id: str, limit: int = 5,
    ) -> "list[dict]":
        """Return drafts that the operator has accepted but the executor
        hasn't fired yet. Filtered by operator_decision='accept' AND
        executed_at IS NULL.

        Returns list of dicts with payload bytes decoded as payload_bytes_decoded
        (UTF-8 string assumed; the operator_agent_drafts.payload_bytes is bytes
        OR int per the schema column comment; this helper handles both).
        """
        try:
            limit = max(1, min(50, int(limit)))
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                rows = conn.execute(
                    "SELECT id, agent_id, action_category, action_name, "
                    "       draft_uri, payload_hash, payload_bytes, "
                    "       operator_decision, operator_decision_at, "
                    "       executed_at, executed_tx_hash, created_at "
                    "FROM operator_agent_drafts "
                    "WHERE agent_id = ? "
                    "AND operator_decision = 'accept' "
                    "AND (executed_at IS NULL OR executed_at = 0) "
                    "AND (refused_at IS NULL OR refused_at = 0) "
                    "ORDER BY id ASC LIMIT ?",
                    (str(agent_id), limit),
                ).fetchall()
            out = []
            for r in rows:
                d = dict(r)
                # Decode payload_bytes (may be int row count from schema or actual
                # bytes blob). Helper for executor consumption.
                pb = d.get("payload_bytes")
                if isinstance(pb, (bytes, bytearray)):
                    try:
                        d["payload_bytes_decoded"] = pb.decode("utf-8")
                    except Exception:
                        d["payload_bytes_decoded"] = ""
                else:
                    d["payload_bytes_decoded"] = str(pb or "")
                out.append(d)
            return out
        except Exception:
            return []

    def mark_draft_executed(self, draft_id: int, tx_hash: str) -> bool:
        """Mark a draft as executed by the live-write executor.
        Returns True on successful update, False on any failure."""
        try:
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                conn.execute(
                    "UPDATE operator_agent_drafts SET executed_at = ?, "
                    "executed_tx_hash = ? WHERE id = ?",
                    (time.time(), str(tx_hash or ""), int(draft_id)),
                )
            return True
        except Exception:
            return False

    def claim_draft_for_execution(self, draft_id: int) -> bool:
        """Atomically claim a draft for execution (strictly-once guarantee,
        2026-05-20). Sets executed_at iff it is currently NULL, in a single
        UPDATE; returns True ONLY for the caller that won the claim. A second
        concurrent executor/cycle sees rowcount==0 and must NOT execute. The
        winner proceeds to sign/anchor and then mark_draft_executed (which sets
        the real tx); a non-success path calls unclaim_draft_execution to
        release it for retry. This makes execution idempotent even if more than
        one executor instance is ever running."""
        try:
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                cur = conn.execute(
                    "UPDATE operator_agent_drafts SET executed_at = ? "
                    "WHERE id = ? AND (executed_at IS NULL OR executed_at = 0)",
                    (time.time(), int(draft_id)),
                )
                return int(cur.rowcount) == 1
        except Exception:
            return False

    def unclaim_draft_execution(self, draft_id: int) -> bool:
        """Release a claim (reset executed_at to NULL) so a draft retries on a
        later cycle — used when execution fails AFTER claiming (e.g. transient
        RPC/KMS error). Returns True on success."""
        try:
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                conn.execute(
                    "UPDATE operator_agent_drafts SET executed_at = NULL "
                    "WHERE id = ?",
                    (int(draft_id),),
                )
            return True
        except Exception:
            return False

    def mark_draft_refused(self, draft_id: int, reason: str) -> bool:
        """Mark a draft as TERMINALLY refused by the live-write executor so it
        drops out of get_accepted_unexecuted_drafts and is not re-attempted/
        re-logged every cycle (2026-05-20 refusal-churn cap). Use ONLY for
        structurally-permanent refusals (no executor route, or a chain-cost
        action under a budget=0 agent) — NOT for transient ones (RPC failure,
        daily budget exceeded) which should retry. Returns True on success."""
        try:
            with self._conn() as conn:
                self._ensure_operator_agent_chain_spending_table(conn)
                conn.execute(
                    "UPDATE operator_agent_drafts SET refused_at = ?, "
                    "refusal_reason = ? WHERE id = ?",
                    (time.time(), str(reason or "")[:200], int(draft_id)),
                )
            return True
        except Exception:
            return False
