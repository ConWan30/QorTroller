"""IoswarmMixin — D-DECON-2 ioswarm domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern
(removal diff is the canonical source). CREATE TABLE statements stay
centralized in _core.py._init_schema per D-DECON-2.
"""
from __future__ import annotations

import json
import time


class IoswarmMixin:
    """Domain methods extracted from Store; resolved via MRO."""
    def insert_ioswarm_consensus(

        self,

        device_id: str,

        node_verdicts_json: str,

        quorum_verdict: str,

        quorum_reached: bool,

        block_quorum_met: bool,

        agreement_ratio: float,

        node_count: int,

        swarm_verdict_score: float,

        hold_escalation_flag: bool,

        verdict_distribution_json: str = "{}",

        session_id: "str | None" = None,

    ) -> int:

        """Insert an ioSwarm consensus result. Returns new row id."""

        import time as _t

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO ioswarm_consensus_log "

                "(device_id, session_id, node_verdicts_json, quorum_verdict, quorum_reached, "

                "block_quorum_met, agreement_ratio, node_count, swarm_verdict_score, "

                "hold_escalation_flag, verdict_distribution_json, created_at) "

                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (

                    device_id, session_id, node_verdicts_json, quorum_verdict,

                    int(quorum_reached), int(block_quorum_met), agreement_ratio, node_count,

                    swarm_verdict_score, int(hold_escalation_flag),

                    verdict_distribution_json, _t.time(),

                ),

            )

            return cur.lastrowid



    def get_ioswarm_consensus_log(

        self,

        device_id: "str | None" = None,

        limit: int = 20,

    ) -> "list[dict]":

        """Return ioSwarm consensus log entries, newest first. Optional device_id filter."""

        import json as _j

        with self._conn() as conn:

            if device_id is not None:

                rows = conn.execute(

                    "SELECT id, device_id, session_id, node_verdicts_json, quorum_verdict, "

                    "quorum_reached, block_quorum_met, agreement_ratio, node_count, "

                    "swarm_verdict_score, hold_escalation_flag, verdict_distribution_json, "

                    "created_at FROM ioswarm_consensus_log "

                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",

                    (device_id, limit),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT id, device_id, session_id, node_verdicts_json, quorum_verdict, "

                    "quorum_reached, block_quorum_met, agreement_ratio, node_count, "

                    "swarm_verdict_score, hold_escalation_flag, verdict_distribution_json, "

                    "created_at FROM ioswarm_consensus_log "

                    "ORDER BY created_at DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        result = []

        for row in rows:

            result.append({

                "id": row[0], "device_id": row[1], "session_id": row[2],

                "node_verdicts": _j.loads(row[3]),

                "quorum_verdict": row[4],

                "quorum_reached": bool(row[5]), "block_quorum_met": bool(row[6]),

                "agreement_ratio": row[7], "node_count": row[8],

                "swarm_verdict_score": row[9],

                "hold_escalation_flag": bool(row[10]),

                "verdict_distribution": _j.loads(row[11]),

                "created_at": row[12],

            })

        return result



    # --- Phase 109B: ioSwarm renewal log ---



    def insert_ioswarm_renewal(

        self,

        device_id: str,

        token_id: int,

        quorum_verdict: "str | None",

        agreement_ratio: float,

        node_count: int,

        renewal_approved: int,

        node_verdicts_json: str = "[]",

    ) -> int:

        """Insert ioSwarm renewal evaluation record. Returns new row id."""

        import time as _t

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO ioswarm_renewal_log "

                "(device_id, token_id, quorum_verdict, agreement_ratio, node_count, "

                "renewal_approved, node_verdicts_json, created_at) "

                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",

                (

                    device_id,

                    token_id,

                    quorum_verdict,

                    agreement_ratio,

                    node_count,

                    renewal_approved,

                    node_verdicts_json,

                    _t.time(),

                ),

            )

            return cur.lastrowid



    def get_ioswarm_renewal_log(

        self,

        device_id: "str | None" = None,

        limit: int = 20,

    ) -> "list[dict]":

        """Return ioSwarm renewal log entries, newest first. Optional device_id filter."""

        import json as _j

        with self._conn() as conn:

            if device_id is not None:

                rows = conn.execute(

                    "SELECT id, device_id, token_id, quorum_verdict, agreement_ratio, "

                    "node_count, renewal_approved, node_verdicts_json, created_at "

                    "FROM ioswarm_renewal_log "

                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",

                    (device_id, limit),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT id, device_id, token_id, quorum_verdict, agreement_ratio, "

                    "node_count, renewal_approved, node_verdicts_json, created_at "

                    "FROM ioswarm_renewal_log "

                    "ORDER BY created_at DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        result = []

        for row in rows:

            result.append({

                "id": row[0],

                "device_id": row[1],

                "token_id": row[2],

                "quorum_verdict": row[3],

                "agreement_ratio": row[4],

                "node_count": row[5],

                "renewal_approved": bool(row[6]),

                "node_verdicts": _j.loads(row[7]),

                "created_at": row[8],

            })

        return result



    # --- Phase 109C: ioSwarm Adjudication Log ---



    def insert_ioswarm_adjudication(

        self,

        device_id: str,

        session_id: str,

        classj_quorum_verdict: "str | None",

        classj_agreement_ratio: float,

        triage_quorum_verdict: "str | None",

        triage_agreement_ratio: float,

        dual_veto: bool,

        node_count: int,

        classj_verdicts_json: str = "[]",

        triage_verdicts_json: str = "[]",

    ) -> int:

        """Insert an ioSwarm adjudication record and return the new row ID."""

        import time as _t

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO ioswarm_adjudication_log "

                "(device_id, session_id, classj_quorum_verdict, classj_agreement_ratio, "

                "triage_quorum_verdict, triage_agreement_ratio, dual_veto, node_count, "

                "classj_verdicts_json, triage_verdicts_json, created_at) "

                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (

                    device_id,

                    session_id or "",

                    classj_quorum_verdict,

                    classj_agreement_ratio,

                    triage_quorum_verdict,

                    triage_agreement_ratio,

                    int(bool(dual_veto)),

                    node_count,

                    classj_verdicts_json,

                    triage_verdicts_json,

                    _t.time(),

                ),

            )

            return cur.lastrowid



    def get_ioswarm_adjudication_log(

        self,

        device_id: "str | None" = None,

        limit: int = 20,

    ) -> "list[dict]":

        """Return recent ioSwarm adjudication log entries."""

        import json as _j

        with self._conn() as conn:

            if device_id:

                rows = conn.execute(

                    "SELECT id, device_id, session_id, classj_quorum_verdict, "

                    "classj_agreement_ratio, triage_quorum_verdict, triage_agreement_ratio, "

                    "dual_veto, node_count, classj_verdicts_json, triage_verdicts_json, created_at "

                    "FROM ioswarm_adjudication_log "

                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",

                    (device_id, limit),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT id, device_id, session_id, classj_quorum_verdict, "

                    "classj_agreement_ratio, triage_quorum_verdict, triage_agreement_ratio, "

                    "dual_veto, node_count, classj_verdicts_json, triage_verdicts_json, created_at "

                    "FROM ioswarm_adjudication_log "

                    "ORDER BY created_at DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        result = []

        for row in rows:

            result.append({

                "id": row[0],

                "device_id": row[1],

                "session_id": row[2],

                "classj_quorum_verdict": row[3],

                "classj_agreement_ratio": row[4],

                "triage_quorum_verdict": row[5],

                "triage_agreement_ratio": row[6],

                "dual_veto": bool(row[7]),

                "node_count": row[8],

                "classj_verdicts": _j.loads(row[9]),

                "triage_verdicts": _j.loads(row[10]),

                "created_at": row[11],

            })

        return result



    # --- Phase 110: ioSwarm VHP Mint Authorization Log ---



    def insert_ioswarm_vhp_mint(

        self,

        device_id: str,

        authorized: bool,

        quorum_verdict: str,

        agreement_ratio: float,

        node_count: int,

        consecutive_clean: int,

        recent_block_count: int,

        node_verdicts_json: str = "[]",

        swarm_fingerprint: "str | None" = None,

        error_msg: "str | None" = None,

    ) -> int:

        import time as _t

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO ioswarm_vhp_mint_log "

                "(device_id, authorized, quorum_verdict, agreement_ratio, node_count, "

                "consecutive_clean, recent_block_count, node_verdicts_json, swarm_fingerprint, "

                "error_msg, created_at) "

                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (

                    device_id,

                    int(authorized),

                    quorum_verdict,

                    float(agreement_ratio),

                    int(node_count),

                    int(consecutive_clean),

                    int(recent_block_count),

                    node_verdicts_json,

                    swarm_fingerprint,

                    error_msg,

                    _t.time(),

                ),

            )

            return cur.lastrowid



    def get_ioswarm_vhp_mint_log(

        self,

        device_id: "str | None" = None,

        limit: int = 20,

    ) -> list[dict]:

        with self._conn() as conn:

            if device_id:

                rows = conn.execute(

                    "SELECT id, device_id, authorized, quorum_verdict, agreement_ratio, "

                    "node_count, consecutive_clean, recent_block_count, node_verdicts_json, "

                    "swarm_fingerprint, error_msg, created_at "

                    "FROM ioswarm_vhp_mint_log "

                    "WHERE device_id = ? ORDER BY created_at DESC LIMIT ?",

                    (device_id, limit),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT id, device_id, authorized, quorum_verdict, agreement_ratio, "

                    "node_count, consecutive_clean, recent_block_count, node_verdicts_json, "

                    "swarm_fingerprint, error_msg, created_at "

                    "FROM ioswarm_vhp_mint_log "

                    "ORDER BY created_at DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        result = []

        for row in rows:

            result.append({

                "id":                  row[0],

                "device_id":           row[1],

                "authorized":          bool(row[2]),

                "quorum_verdict":      row[3],

                "agreement_ratio":     row[4],

                "node_count":          row[5],

                "consecutive_clean":   row[6],

                "recent_block_count":  row[7],

                "node_verdicts":       json.loads(row[8]),

                "swarm_fingerprint":   row[9],

                "error_msg":           row[10],

                "created_at":          row[11],

            })

        return result



    # --- Phase 111: PoAd Registry ---



    def insert_poad_registry(

        self,

        device_id: str,

        poad_hash: str,

        dual_veto: bool,

        classj_verdict: "str | None",

        triage_verdict: "str | None",

        ts_ns: int,

        on_chain_tx: "str | None" = None,

    ) -> int:

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT OR IGNORE INTO poad_registry_log "

                "(device_id, poad_hash, dual_veto, classj_verdict, triage_verdict, ts_ns, on_chain_tx) "

                "VALUES (?, ?, ?, ?, ?, ?, ?)",

                (device_id, poad_hash, int(dual_veto), classj_verdict, triage_verdict,

                 ts_ns, on_chain_tx),

            )

            return cur.lastrowid



    def get_poad_registry_log(

        self,

        device_id: "str | None" = None,

        limit: int = 20,

    ) -> "list[dict]":

        with self._conn() as conn:

            if device_id:

                rows = conn.execute(

                    "SELECT id, device_id, poad_hash, dual_veto, classj_verdict, "

                    "triage_verdict, ts_ns, on_chain_tx, created_at "

                    "FROM poad_registry_log WHERE device_id = ? "

                    "ORDER BY created_at DESC LIMIT ?",

                    (device_id, limit),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT id, device_id, poad_hash, dual_veto, classj_verdict, "

                    "triage_verdict, ts_ns, on_chain_tx, created_at "

                    "FROM poad_registry_log ORDER BY created_at DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        result = []

        for row in rows:

            result.append({

                "id":              row[0],

                "device_id":       row[1],

                "poad_hash":       row[2],

                "dual_veto":       bool(row[3]),

                "classj_verdict":  row[4],

                "triage_verdict":  row[5],

                "ts_ns":           row[6],

                "on_chain_tx":     row[7],

                "created_at":      row[8],

            })

        return result



    def update_poad_on_chain_tx(self, poad_hash: str, on_chain_tx: str) -> None:

        with self._conn() as conn:

            conn.execute(

                "UPDATE poad_registry_log SET on_chain_tx = ? WHERE poad_hash = ?",

                (on_chain_tx, poad_hash),

            )



    def get_unanchored_poad_entries(self, limit: int = 10) -> "list[dict]":

        """Return poad_registry_log rows with on_chain_tx IS NULL, oldest first."""

        with self._conn() as conn:

            rows = conn.execute(

                "SELECT id, device_id, poad_hash, dual_veto, classj_verdict, "

                "triage_verdict, ts_ns FROM poad_registry_log "

                "WHERE on_chain_tx IS NULL ORDER BY created_at ASC LIMIT ?",

                (limit,),

            ).fetchall()

        return [

            {"id": r[0], "device_id": r[1], "poad_hash": r[2], "dual_veto": bool(r[3]),

             "classj_verdict": r[4], "triage_verdict": r[5], "ts_ns": r[6]}

            for r in rows

        ]



    # --- Phase 113: Dual-Primitive Gate ---



    def insert_dual_eligibility_check(

        self,

        device_id: str,

        poad_hash: str,

        eligible: bool,

        poac_valid: bool,

        poad_valid: bool,

    ) -> int:

        """Insert a dual-primitive eligibility check result (Phase 113)."""

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO dual_eligibility_checks "

                "(device_id, poad_hash, eligible, poac_valid, poad_valid) "

                "VALUES (?, ?, ?, ?, ?)",

                (device_id, poad_hash, int(eligible), int(poac_valid), int(poad_valid)),

            )

            return cur.lastrowid



    def get_dual_eligibility_history(self, device_id: "str | None" = None, limit: int = 100) -> "list[dict]":

        """Return dual_eligibility_checks rows, newest first. Optionally filter by device_id."""

        with self._conn() as conn:

            if device_id:

                rows = conn.execute(

                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, created_at "

                    "FROM dual_eligibility_checks WHERE device_id = ? "

                    "ORDER BY id DESC LIMIT ?",

                    (device_id, limit),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, created_at "

                    "FROM dual_eligibility_checks ORDER BY id DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        return [

            {"id": r[0], "device_id": r[1], "poad_hash": r[2],

             "eligible": bool(r[3]), "poac_valid": bool(r[4]), "poad_valid": bool(r[5]),

             "created_at": r[6]}

            for r in rows

        ]



    # --- Phase 116 — Epoch-Window Analytics ---



    def get_latest_poad_hash_for_device(self, device_id: str) -> "str | None":

        """Return the most recent poad_hash from poad_registry_log for device_id, or None."""

        with self._conn() as conn:

            row = conn.execute(

                "SELECT poad_hash FROM poad_registry_log "

                "WHERE device_id = ? ORDER BY id DESC LIMIT 1",

                (device_id,),

            ).fetchone()

        return row[0] if row else None



    def get_poad_ts_ns_for_device(self, device_id: str) -> "int | None":

        """Return ts_ns of the most recent poad_registry_log entry for device_id, or None."""

        with self._conn() as conn:

            row = conn.execute(

                "SELECT ts_ns FROM poad_registry_log "

                "WHERE device_id = ? ORDER BY id DESC LIMIT 1",

                (device_id,),

            ).fetchone()

        return int(row[0]) if row and row[0] is not None else None



    def insert_swarm_quorum_validation(

        self,

        node_count: int,

        distinct_stakers: int,

        quorum_valid: bool,

        gate_address: str = "",

    ) -> int:

        """Insert a swarm quorum validation result (Phase 130A)."""

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO swarm_quorum_validation_log "

                "(node_count, distinct_stakers, quorum_valid, gate_address, created_at) "

                "VALUES (?,?,?,?,?)",

                (int(node_count), int(distinct_stakers),

                 1 if quorum_valid else 0, str(gate_address), time.time()),

            )

            return cur.lastrowid



    def get_swarm_quorum_validation_log(self, limit: int = 10) -> "list[dict]":

        """Return recent swarm quorum validation entries, newest first (Phase 130A)."""

        with self._conn() as conn:

            rows = conn.execute(

                "SELECT id, node_count, distinct_stakers, quorum_valid, gate_address, created_at "

                "FROM swarm_quorum_validation_log "

                "ORDER BY id DESC LIMIT ?",

                (limit,),

            ).fetchall()

        return [dict(r) for r in rows]



    def insert_ioswarm_node_registry(self, node_url: str, staker_address: str = "", active: bool = True, node_version: str = "") -> int:

        """Phase 131: Register an ioSwarm live node URL."""

        with self._conn() as con:

            cur = con.execute(

                "INSERT OR IGNORE INTO ioswarm_node_registry "

                "(node_url, staker_address, active, node_version, registered_at) "

                "VALUES (?, ?, ?, ?, ?)",

                (node_url, staker_address, int(active), node_version, __import__("time").time()),

            )

            return cur.lastrowid or 0



    def get_ioswarm_node_registry(self, active_only: bool = False) -> list:

        """Phase 131: Return registered ioSwarm node entries."""

        query = "SELECT * FROM ioswarm_node_registry"

        if active_only:

            query += " WHERE active=1"

        query += " ORDER BY registered_at ASC"

        with self._conn() as con:

            rows = con.execute(query).fetchall()

        return [dict(r) for r in rows]



    def update_ioswarm_node_last_seen(self, node_url: str, ts: float, staker_address: str = "") -> None:

        """Phase 131: Update last_seen_ts for a registered ioSwarm node."""

        with self._conn() as con:

            if staker_address:

                con.execute(

                    "UPDATE ioswarm_node_registry SET last_seen_ts=?, staker_address=? WHERE node_url=?",

                    (ts, staker_address, node_url),

                )

            else:

                con.execute(

                    "UPDATE ioswarm_node_registry SET last_seen_ts=? WHERE node_url=?",

                    (ts, node_url),

                )



    # ------------------------------------------------------------------

    # Phase 132: IoSwarm Node Health Log

    # ------------------------------------------------------------------



    def insert_ioswarm_node_health(

        self,

        node_url: str,

        healthy: bool,

        latency_ms: float,

        staker_address: str = "",

        error_msg: str = "",

    ) -> int:

        """Phase 132: Record a health poll result for a live ioSwarm node."""

        polled_at = time.time()

        with self._conn() as con:

            cur = con.execute(

                "INSERT INTO ioswarm_node_health_log "

                "(node_url, healthy, latency_ms, staker_address, error_msg, polled_at, created_at) "

                "VALUES (?, ?, ?, ?, ?, ?, ?)",

                (node_url, int(healthy), latency_ms, staker_address, error_msg, polled_at, polled_at),

            )

            return cur.lastrowid



    def get_ioswarm_node_health(self, node_url: str | None = None, limit: int = 50) -> list:

        """Phase 132: Retrieve recent health poll records, optionally filtered by node_url."""

        with self._conn() as con:

            if node_url:

                rows = con.execute(

                    "SELECT * FROM ioswarm_node_health_log WHERE node_url=? "

                    "ORDER BY polled_at DESC LIMIT ?",

                    (node_url, limit),

                ).fetchall()

            else:

                rows = con.execute(

                    "SELECT * FROM ioswarm_node_health_log ORDER BY polled_at DESC LIMIT ?",

                    (limit,),

                ).fetchall()

        return [dict(r) for r in rows]



    # ------------------------------------------------------------------

    # Phase 133: IoSwarm PoAd Auto-Anchor

    # ------------------------------------------------------------------



    def insert_ioswarm_poad_anchor(

        self,

        device_id: str,

        session_id: str = "",

        dual_veto: bool = False,

        swarm_fingerprint: str = "",

        poad_hash: str = "",

        on_chain_tx: str | None = None,

        anchor_status: str = "pending",

    ) -> int:

        """Phase 133: Insert a PoAd auto-anchor record."""

        with self._conn() as conn:

            cur = conn.execute(

                """INSERT INTO ioswarm_poad_anchor_log

                   (device_id, session_id, dual_veto, swarm_fingerprint,

                    poad_hash, on_chain_tx, anchor_status, created_at)

                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",

                (device_id, session_id, int(dual_veto), swarm_fingerprint,

                 poad_hash, on_chain_tx, anchor_status, time.time()),

            )

            return cur.lastrowid



    def update_ioswarm_poad_anchor_tx(

        self,

        anchor_id: int,

        on_chain_tx: str,

        anchor_status: str,

    ) -> None:

        """Phase 133: Update an anchor record's tx hash and status."""

        with self._conn() as conn:

            conn.execute(

                "UPDATE ioswarm_poad_anchor_log SET on_chain_tx=?, anchor_status=? WHERE id=?",

                (on_chain_tx, anchor_status, anchor_id),

            )



    def get_ioswarm_poad_anchor_log(self, limit: int = 50) -> list:

        """Phase 133: Retrieve recent PoAd anchor records, newest first."""

        with self._conn() as conn:

            rows = conn.execute(

                "SELECT * FROM ioswarm_poad_anchor_log ORDER BY created_at DESC LIMIT ?",

                (limit,),

            ).fetchall()

        return [dict(r) for r in rows]



    # ------------------------------------------------------------------

    # Phase 131B: USB Stability Monitor — PS5 coexistence logging

    # ------------------------------------------------------------------



