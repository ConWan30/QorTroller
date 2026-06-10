"""
ZkbaVpmMixin — DECON-1 Stream 2 Phase 2.1 leaf-domain extraction.

Houses Store helpers for six tables in the ZKBA + VPM + witness + MLGA +
CFSS + physical-data domain:
  - cfss_lane_drift_log
  - bt_witness_log
  - mlga_session_log
  - zkba_artifact_log
  - vpm_artifact_log
  - physical_data_attestation_log

Mixin pattern (per audits/decon-store-map.md §F-DECON-2.1): these methods
are pulled out of `Store` as a sibling class; `Store` re-inherits them in
`_core.py` so `self.method_x()` resolves byte-identically via MRO. Public
import surface unchanged — `from vapi_bridge.store import Store` continues
to expose the same callable methods.

Table CREATE statements remain in `_core.py::Store._init_schema()` per
D-DECON-2 sub-decision (4) — cross-domain schema definition stays
centralized.

Mechanical extraction: zero logic edits. Any bug present here was present
in `_core.py` before the move.
"""
from __future__ import annotations

import time


class ZkbaVpmMixin:
    # --- Phase O4-VPM-INT follow-up: CFSS lane drift helpers ---
    #
    # Findings from cfss_drift_sweeper.py (continuous Cedar policy
    # CFSS lane authority detection). Each row = one matrix-row
    # CFSS_VIOLATION. Consumed by the 27th FSCA contradiction rule
    # CFSS_LANE_AUTHORITY_DRIFT (CRITICAL severity).

    def insert_cfss_lane_drift(
        self,
        *,
        sweep_id: str,
        agent_id: str,
        action: str,
        resource: str | None,
        expected_effect: str,
        actual_effect: str,
        bundle_path: str = "",
        evidence_json: str = "",
    ) -> int:
        """Persist one CFSS lane-authority drift finding. Never raises."""
        try:
            now = time.time()
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO cfss_lane_drift_log "
                    "(sweep_id, agent_id, action, resource, "
                    "expected_effect, actual_effect, bundle_path, "
                    "evidence_json, created_at) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        sweep_id, agent_id, action, resource,
                        expected_effect, actual_effect,
                        bundle_path, evidence_json, now,
                    ),
                )
                return int(cur.lastrowid) if cur.lastrowid else 0
        except Exception:
            return 0

    def get_cfss_lane_drift_recent(
        self,
        since_seconds: int = 3600,
        limit: int = 50,
    ) -> list[dict]:
        """Return CFSS drift findings within the trailing window."""
        try:
            since = time.time() - max(1, int(since_seconds))
            limit = max(1, min(500, int(limit)))
            with self._conn() as conn:
                return [
                    dict(r) for r in conn.execute(
                        "SELECT * FROM cfss_lane_drift_log "
                        "WHERE created_at >= ? "
                        "ORDER BY created_at DESC LIMIT ?",
                        (since, limit),
                    ).fetchall()
                ]
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Phase 242-BT Stream 1 — bt_witness_log helpers
    # ------------------------------------------------------------------
    def insert_bt_witness_event(
        self,
        *,
        commitment_hex: str,
        witness_pubkey_hex: str,
        device_id_hex: str,
        session_id_hex: str,
        feature_root_hex: str,
        n_features: int,
        transport_code: int,
        ts_ns: int,
        trigger_reason: str = "",
    ) -> int:
        """Persist one BT-WITNESS commitment. Returns new row id; 0 on
        UNIQUE collision (anti-replay — same commitment already recorded).
        Fail-open: returns 0 on any DB error, never raises.

        Stream 1 callers MUST pass n_features=0 (feature schema deferred
        to Stream 2 post-Stage-2 measurement per the v1.1 canonical
        anchor §5).
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO bt_witness_log "
                    "(commitment_hex, witness_pubkey_hex, device_id_hex, "
                    " session_id_hex, feature_root_hex, n_features, "
                    " transport_code, ts_ns, trigger_reason, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        commitment_hex,
                        witness_pubkey_hex,
                        device_id_hex,
                        session_id_hex,
                        feature_root_hex,
                        int(n_features),
                        int(transport_code),
                        int(ts_ns),
                        trigger_reason,
                        time.time(),
                    ),
                )
                if cur.lastrowid:
                    return int(cur.lastrowid)
                row = conn.execute(
                    "SELECT id FROM bt_witness_log WHERE commitment_hex = ?",
                    (commitment_hex,),
                ).fetchone()
                return int(row["id"]) if row else 0
        except Exception:
            return 0

    def get_bt_witness_status(self) -> dict:
        """Summary of BT-WITNESS activity. Fail-open: returns the empty
        shape on DB error or empty table."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) AS total, "
                    "       MAX(ts_ns) AS latest_ts_ns, "
                    "       SUM(CASE WHEN on_chain_confirmed=1 THEN 1 ELSE 0 END) AS confirmed "
                    "FROM bt_witness_log"
                ).fetchone()
                latest = conn.execute(
                    "SELECT commitment_hex, witness_pubkey_hex, session_id_hex, ts_ns "
                    "FROM bt_witness_log ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
            total = int(row["total"] or 0) if row else 0
            return {
                "total_events":       total,
                "on_chain_confirmed": int(row["confirmed"] or 0) if row else 0,
                "latest_ts_ns":       int(row["latest_ts_ns"] or 0) if row else 0,
                "latest_commitment":  (dict(latest)["commitment_hex"] if latest else ""),
                "latest_session_id":  (dict(latest)["session_id_hex"] if latest else ""),
                "timestamp":          time.time(),
            }
        except Exception:
            return {
                "total_events": 0,
                "on_chain_confirmed": 0,
                "latest_ts_ns": 0,
                "latest_commitment": "",
                "latest_session_id": "",
                "timestamp": time.time(),
            }

    # ------------------------------------------------------------------
    # Phase O5-MLGA Stage 2 — mlga_session_log helpers
    # ------------------------------------------------------------------
    def insert_mlga_session(
        self,
        *,
        session_id: str,
        session_start_ts_ns: int,
        session_end_ts_ns: int,
        n_poac_records: int,
        n_trigger_pulls_r2: int,
        n_trigger_pulls_l2: int,
        apop_state_counts_json: str,
        bt_observability: int,
        gic_advances_in_session: int,
        dataproof_hex: str,
    ) -> int:
        """Persist one MLGA session record. Returns new row id; 0 on
        UNIQUE collision (session_id + dataproof_hex anti-replay) OR DB
        error. Fail-open per Mythos contract."""
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT OR IGNORE INTO mlga_session_log "
                    "(session_id, session_start_ts_ns, session_end_ts_ns, "
                    " n_poac_records, n_trigger_pulls_r2, n_trigger_pulls_l2, "
                    " apop_state_counts_json, bt_observability, "
                    " gic_advances_in_session, dataproof_hex, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        session_id,
                        int(session_start_ts_ns),
                        int(session_end_ts_ns),
                        int(n_poac_records),
                        int(n_trigger_pulls_r2),
                        int(n_trigger_pulls_l2),
                        apop_state_counts_json,
                        int(bt_observability),
                        int(gic_advances_in_session),
                        dataproof_hex,
                        time.time(),
                    ),
                )
                if cur.lastrowid:
                    return int(cur.lastrowid)
                row = conn.execute(
                    "SELECT id FROM mlga_session_log "
                    "WHERE session_id = ? AND dataproof_hex = ?",
                    (session_id, dataproof_hex),
                ).fetchone()
                return int(row["id"]) if row else 0
        except Exception:
            return 0

    def get_mlga_session_status(self, limit: int = 10) -> dict:
        """Summary of recent MLGA captures. Fail-open."""
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    "SELECT * FROM mlga_session_log "
                    "ORDER BY session_start_ts_ns DESC LIMIT ?",
                    (max(1, min(100, int(limit))),),
                ).fetchall()
                summary = conn.execute(
                    "SELECT COUNT(*) AS total, "
                    "       SUM(n_poac_records) AS total_records, "
                    "       SUM(n_trigger_pulls_r2) AS total_r2, "
                    "       SUM(n_trigger_pulls_l2) AS total_l2, "
                    "       SUM(gic_advances_in_session) AS total_gic, "
                    "       MAX(session_end_ts_ns) AS latest_end "
                    "FROM mlga_session_log"
                ).fetchone()
            s = dict(summary) if summary else {}
            return {
                "total_sessions":      int(s.get("total") or 0),
                "total_poac_records":  int(s.get("total_records") or 0),
                "total_r2_pulls":      int(s.get("total_r2") or 0),
                "total_l2_pulls":      int(s.get("total_l2") or 0),
                "total_gic_advances":  int(s.get("total_gic") or 0),
                "latest_session_end_ts_ns": int(s.get("latest_end") or 0),
                "recent_sessions":     [dict(r) for r in rows],
                "timestamp":           time.time(),
            }
        except Exception:
            return {
                "total_sessions": 0,
                "total_poac_records": 0,
                "total_r2_pulls": 0,
                "total_l2_pulls": 0,
                "total_gic_advances": 0,
                "latest_session_end_ts_ns": 0,
                "recent_sessions": [],
                "timestamp": time.time(),
            }

    # --- Phase O3-ZKBA-TRACK1: ZKBA artifact log (PATTERN-017 family) ---

    def insert_zkba_artifact(
        self,
        *,
        zkba_class: int,
        proof_weight: int,
        commitment_hex: str,
        preimage_json: str,
        ts_ns: int,
        manifest_uri: str | None = None,
        compiler_output_hash_hex: str | None = None,
    ) -> int:
        """Insert one ZKBA artifact row. Returns row id.

        UNIQUE(commitment_hex) enforced — re-inserting the same commitment
        returns the existing row id (matches corpus_snapshot_log idempotency
        precedent).  anchor_tx_hash is intentionally NOT writable in Track 1
        (populated by Stream A3 parallel_zkba_anchor.py post-activation).
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO zkba_artifact_log "
                    "(commitment_hex, zkba_class, proof_weight, preimage_json, "
                    " ts_ns, manifest_uri, compiler_output_hash_hex, "
                    " anchor_tx_hash, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)",
                    (
                        str(commitment_hex), int(zkba_class), int(proof_weight),
                        str(preimage_json), int(ts_ns),
                        str(manifest_uri) if manifest_uri is not None else None,
                        str(compiler_output_hash_hex) if compiler_output_hash_hex is not None else None,
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM zkba_artifact_log WHERE commitment_hex = ?",
                    (str(commitment_hex),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_zkba_artifact_status(self, commitment_hex: str) -> dict | None:
        """Return one ZKBA artifact row by commitment_hex, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, commitment_hex, zkba_class, proof_weight, "
                "       preimage_json, ts_ns, manifest_uri, "
                "       compiler_output_hash_hex, anchor_tx_hash, created_at "
                "FROM zkba_artifact_log WHERE commitment_hex = ?",
                (str(commitment_hex),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_zkba_artifact_history(self, limit: int = 20) -> list[dict]:
        """Return last N ZKBA artifacts in DESC ts_ns order (newest first)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, commitment_hex, zkba_class, proof_weight, ts_ns, "
                "       manifest_uri, compiler_output_hash_hex, anchor_tx_hash, "
                "       created_at "
                "FROM zkba_artifact_log ORDER BY ts_ns DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_zkba_artifact_summary(self) -> dict:
        """Phase O3-ZKBA-TRACK1 (post-C5) — aggregate stats over zkba_artifact_log.

        Returned dict shape (matches VAPIZKBA.status() SDK wire contract at
        sdk/vapi_sdk.py:9272-9283):

            {
                "total_artifacts":        int,
                "anchored_count":         int,        # rows with anchor_tx_hash IS NOT NULL
                "track1_invariant_holds": bool,        # anchored_count == 0 holds across Track 1
                "class_breakdown":        {zkba_class_int: count_int, ...},
                "latest":                 dict | None,  # newest row (DESC ts_ns) or None
            }

        Reads only — no mutation.  Fail-open on DB errors via outer try/except
        returning the zero-state shape (total=0, anchored=0, holds=True,
        breakdown={}, latest=None).
        """
        try:
            with self._conn() as conn:
                total_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM zkba_artifact_log"
                ).fetchone()
                anchored_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM zkba_artifact_log "
                    "WHERE anchor_tx_hash IS NOT NULL"
                ).fetchone()
                breakdown_rows = conn.execute(
                    "SELECT zkba_class, COUNT(*) AS n FROM zkba_artifact_log "
                    "GROUP BY zkba_class"
                ).fetchall()
                latest_row = conn.execute(
                    "SELECT id, commitment_hex, zkba_class, proof_weight, ts_ns, "
                    "       manifest_uri, compiler_output_hash_hex, anchor_tx_hash, "
                    "       created_at "
                    "FROM zkba_artifact_log ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
            total = int(total_row["n"]) if total_row else 0
            anchored = int(anchored_row["n"]) if anchored_row else 0
            breakdown = {int(r["zkba_class"]): int(r["n"]) for r in breakdown_rows}
            latest = dict(latest_row) if latest_row is not None else None
            return {
                "total_artifacts":        total,
                "anchored_count":         anchored,
                "track1_invariant_holds": anchored == 0,
                "class_breakdown":        breakdown,
                "latest":                 latest,
            }
        except Exception:
            return {
                "total_artifacts":        0,
                "anchored_count":         0,
                "track1_invariant_holds": True,
                "class_breakdown":        {},
                "latest":                 None,
            }

    # --- Phase O4-VPM-INT B.0: vpm_artifact_log helpers ---

    def insert_vpm_artifact(
        self,
        *,
        commitment_hex: str,
        vpm_id: str,
        zkba_class: int,
        proof_weight: int,
        visual_state: str,
        capture_mode: str,
        integrity_label_hash_hex: str,
        wrapper_schema: str,
        zkba_manifest_hash_hex: str,
        manifest_uri: str | None,
        compiler_output_hash_hex: str | None,
        preimage_json: str,
        ts_ns: int,
    ) -> int:
        """Insert one VPM artifact row. Returns row id.

        UNIQUE(commitment_hex) enforced — re-inserting the same commitment
        returns the existing row id (matches zkba_artifact_log idempotency
        precedent from commit 625007ab).

        All fields keyword-only to keep the insert call site self-describing
        at compile-vpm-artifact orchestrators + at the bridge POST /operator/
        vpm-compile endpoint.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO vpm_artifact_log "
                    "(commitment_hex, vpm_id, zkba_class, proof_weight, "
                    " visual_state, capture_mode, integrity_label_hash_hex, "
                    " wrapper_schema, zkba_manifest_hash_hex, manifest_uri, "
                    " compiler_output_hash_hex, preimage_json, ts_ns, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(commitment_hex), str(vpm_id),
                        int(zkba_class), int(proof_weight),
                        str(visual_state), str(capture_mode),
                        str(integrity_label_hash_hex),
                        str(wrapper_schema), str(zkba_manifest_hash_hex),
                        str(manifest_uri) if manifest_uri is not None else None,
                        str(compiler_output_hash_hex) if compiler_output_hash_hex is not None else None,
                        str(preimage_json), int(ts_ns),
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM vpm_artifact_log WHERE commitment_hex = ?",
                    (str(commitment_hex),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_vpm_artifact_status(self, commitment_hex: str) -> dict | None:
        """Return one VPM artifact row by commitment_hex, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id, commitment_hex, vpm_id, zkba_class, proof_weight, "
                "       visual_state, capture_mode, integrity_label_hash_hex, "
                "       wrapper_schema, zkba_manifest_hash_hex, manifest_uri, "
                "       compiler_output_hash_hex, preimage_json, ts_ns, created_at "
                "FROM vpm_artifact_log WHERE commitment_hex = ?",
                (str(commitment_hex),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_vpm_artifact_history(
        self,
        vpm_id: str | None = None,
        visual_state: str | None = None,
        since_minutes: int = 0,
        limit: int = 20,
    ) -> list[dict]:
        """Return VPM artifacts filtered by optional vpm_id / visual_state /
        since_minutes window, DESC ts_ns (newest first), capped at `limit`.

        `since_minutes`=0 means no time filter. Filter parameters are
        composable; passing none = unbounded query (clamped by `limit`).
        """
        clauses: list[str] = []
        args: list = []
        if vpm_id is not None and vpm_id != "":
            clauses.append("vpm_id = ?")
            args.append(str(vpm_id))
        if visual_state is not None and visual_state != "":
            clauses.append("visual_state = ?")
            args.append(str(visual_state))
        if since_minutes > 0:
            cutoff = time.time() - (int(since_minutes) * 60.0)
            clauses.append("created_at >= ?")
            args.append(cutoff)
        where_sql = (" WHERE " + " AND ".join(clauses)) if clauses else ""
        args.append(int(limit))
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, commitment_hex, vpm_id, zkba_class, proof_weight, "
                "       visual_state, capture_mode, integrity_label_hash_hex, "
                "       wrapper_schema, zkba_manifest_hash_hex, manifest_uri, "
                "       compiler_output_hash_hex, ts_ns, created_at "
                f"FROM vpm_artifact_log{where_sql} ORDER BY ts_ns DESC LIMIT ?",
                tuple(args),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_vpm_artifact_summary(self) -> dict:
        """Phase O4-VPM-INT B.0 — aggregate stats over vpm_artifact_log.

        Mirrors the zkba_artifact_log summary shape but with VPM-specific
        breakdowns. Returned dict shape:

            {
                "total_artifacts":    int,
                "vpm_id_breakdown":   {vpm_id_str: count_int, ...},
                "visual_state_breakdown": {state_str: count_int, ...},
                "latest":             dict | None,
            }

        Reads only — no mutation. Fail-open on DB errors via outer
        try/except returning the zero-state shape.
        """
        try:
            with self._conn() as conn:
                total_row = conn.execute(
                    "SELECT COUNT(*) AS n FROM vpm_artifact_log"
                ).fetchone()
                vpm_id_rows = conn.execute(
                    "SELECT vpm_id, COUNT(*) AS n FROM vpm_artifact_log "
                    "GROUP BY vpm_id"
                ).fetchall()
                state_rows = conn.execute(
                    "SELECT visual_state, COUNT(*) AS n FROM vpm_artifact_log "
                    "GROUP BY visual_state"
                ).fetchall()
                latest_row = conn.execute(
                    "SELECT id, commitment_hex, vpm_id, zkba_class, proof_weight, "
                    "       visual_state, capture_mode, ts_ns, manifest_uri, "
                    "       created_at "
                    "FROM vpm_artifact_log ORDER BY ts_ns DESC LIMIT 1"
                ).fetchone()
            total = int(total_row["n"]) if total_row else 0
            vpm_id_breakdown = {str(r["vpm_id"]): int(r["n"]) for r in vpm_id_rows}
            state_breakdown = {str(r["visual_state"]): int(r["n"]) for r in state_rows}
            latest = dict(latest_row) if latest_row is not None else None
            return {
                "total_artifacts":        total,
                "vpm_id_breakdown":       vpm_id_breakdown,
                "visual_state_breakdown": state_breakdown,
                "latest":                 latest,
            }
        except Exception:
            return {
                "total_artifacts":        0,
                "vpm_id_breakdown":       {},
                "visual_state_breakdown": {},
                "latest":                 None,
            }

    # --- Phase O0 Stream 3-prep Session 2: PHYSICAL_DATA_ATTESTATION-v1 helpers ---

    def insert_physical_data_attestation(
        self,
        pda_commitment: str,
        hardware_data_hash: str,
        agent_id: str,
        attestation_type: str,
        attestation_type_hash: str,
        ts_ns: int,
        tx_hash: str = "",
        on_chain_confirmed: bool = False,
        anchor_id: int = -1,
    ) -> int:
        """Insert one PHYSICAL_DATA_ATTESTATION v1 row into
        physical_data_attestation_log. Returns row id.

        UNIQUE(pda_commitment) enforced — duplicate inserts (same PDA
        hash from re-attesting the same physical-data artifact) are
        idempotent: the duplicate raises sqlite3.IntegrityError which
        we translate to "already recorded" by returning the existing
        row id. Mirrors insert_agent_commit / insert_corpus_snapshot.

        Phase O0 Stream 3-prep Session 2 — Pass 2C Section 4.2.
        """
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO physical_data_attestation_log "
                    "(pda_commitment, hardware_data_hash, agent_id, "
                    " attestation_type, attestation_type_hash, ts_ns, "
                    " tx_hash, on_chain_confirmed, anchor_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(pda_commitment), str(hardware_data_hash),
                        str(agent_id), str(attestation_type),
                        str(attestation_type_hash), int(ts_ns),
                        str(tx_hash), 1 if on_chain_confirmed else 0,
                        int(anchor_id), time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            # Likely UNIQUE collision — return the existing row id
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM physical_data_attestation_log "
                    "WHERE pda_commitment = ?",
                    (str(pda_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_physical_data_attestation_status(self) -> dict:
        """Return latest PHYSICAL_DATA_ATTESTATION v1 record summary.

        Returns 8 keys: total_attestations, latest_pda_commitment,
        latest_agent_id, latest_attestation_type, latest_ts_ns,
        on_chain_confirmed, anchor_id, timestamp.
        """
        import time as _tac
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) AS n FROM physical_data_attestation_log"
            ).fetchone()["n"]
            row = conn.execute(
                "SELECT pda_commitment, agent_id, attestation_type, ts_ns, "
                "       on_chain_confirmed, anchor_id "
                "FROM physical_data_attestation_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {
                "total_attestations":       0,
                "latest_pda_commitment":    "",
                "latest_agent_id":          "",
                "latest_attestation_type":  "",
                "latest_ts_ns":             0,
                "on_chain_confirmed":       False,
                "anchor_id":                -1,
                "timestamp":                _tac.time(),
            }
        return {
            "total_attestations":       int(total),
            "latest_pda_commitment":    str(row["pda_commitment"]),
            "latest_agent_id":          str(row["agent_id"]),
            "latest_attestation_type":  str(row["attestation_type"]),
            "latest_ts_ns":             int(row["ts_ns"]),
            "on_chain_confirmed":       bool(row["on_chain_confirmed"]),
            "anchor_id":                int(row["anchor_id"]),
            "timestamp":                _tac.time(),
        }

    def get_physical_data_attestation_history(
        self,
        agent_id: str = "",
        attestation_type: str = "",
        limit: int = 20,
    ) -> list[dict]:
        """Return last N PHYSICAL_DATA_ATTESTATION v1 records.

        Filterable by agent_id and/or attestation_type. DESC ts_ns
        ordering (newest first). Empty filter strings disable that
        filter. Mirrors get_agent_commit_history() pattern with the
        added attestation_type filter (Pass 2C Section 4.2 indexed).
        """
        cols = (
            "SELECT id, pda_commitment, hardware_data_hash, agent_id, "
            "       attestation_type, attestation_type_hash, ts_ns, "
            "       tx_hash, on_chain_confirmed, anchor_id, created_at "
            "FROM physical_data_attestation_log "
        )
        with self._conn() as conn:
            if agent_id and attestation_type:
                rows = conn.execute(
                    cols
                    + "WHERE agent_id = ? AND attestation_type = ? "
                      "ORDER BY ts_ns DESC LIMIT ?",
                    (str(agent_id), str(attestation_type), int(limit)),
                ).fetchall()
            elif agent_id:
                rows = conn.execute(
                    cols
                    + "WHERE agent_id = ? ORDER BY ts_ns DESC LIMIT ?",
                    (str(agent_id), int(limit)),
                ).fetchall()
            elif attestation_type:
                rows = conn.execute(
                    cols
                    + "WHERE attestation_type = ? "
                      "ORDER BY ts_ns DESC LIMIT ?",
                    (str(attestation_type), int(limit)),
                ).fetchall()
            else:
                rows = conn.execute(
                    cols + "ORDER BY ts_ns DESC LIMIT ?",
                    (int(limit),),
                ).fetchall()
        return [dict(r) for r in rows]
