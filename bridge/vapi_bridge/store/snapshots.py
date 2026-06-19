"""SnapshotsGrindMixin — D-DECON-2 snapshots/grind/corpus domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern
(removal diff is the canonical source). CREATE TABLE statements stay
centralized in _core.py._init_schema per D-DECON-2.
"""
from __future__ import annotations

import time


class SnapshotsGrindMixin:
    """Domain methods extracted from Store; resolved via MRO."""
    def insert_corpus_entropy(self, score: float, per_player_json: str,

                              per_feature_json: str, low_entropy_features_json: str,

                              clustering_warning: bool, n_sessions: int,

                              session_type_filter: str = "touchpad_corners",

                              computed_at_ts: int = 0) -> int:

        """Insert a corpus entropy measurement (Phase 192)."""

        if computed_at_ts == 0:

            computed_at_ts = int(time.time())

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO corpus_entropy_log "

                "(corpus_entropy_score, per_player_entropy, per_feature_entropy, "

                "low_entropy_features, clustering_warning, n_sessions_analyzed, "

                "session_type_filter, computed_at_ts) VALUES (?,?,?,?,?,?,?,?)",

                (score, per_player_json, per_feature_json, low_entropy_features_json,

                 1 if clustering_warning else 0, n_sessions, session_type_filter,

                 computed_at_ts),

            )

        return cur.lastrowid  # type: ignore[return-value]



    def get_latest_corpus_entropy(self, session_type: str = "touchpad_corners") -> "dict | None":

        """Return most recent corpus entropy record (Phase 192)."""

        try:

            with self._conn() as conn:

                row = conn.execute(

                    "SELECT corpus_entropy_score, per_player_entropy, per_feature_entropy, "

                    "low_entropy_features, clustering_warning, n_sessions_analyzed, "

                    "session_type_filter, computed_at_ts, created_at "

                    "FROM corpus_entropy_log WHERE session_type_filter=? "

                    "ORDER BY computed_at_ts DESC LIMIT 1",

                    (session_type,),

                ).fetchone()

        except Exception:

            row = None

        if row is None:

            return None

        return {

            "corpus_entropy_score":  float(row[0]),

            "per_player_entropy":    row[1],

            "per_feature_entropy":   row[2],

            "low_entropy_features":  row[3],

            "clustering_warning":    bool(row[4]),

            "n_sessions_analyzed":   int(row[5]),

            "session_type_filter":   row[6],

            "computed_at_ts":        int(row[7]),

            "created_at":            row[8],

        }



    # Task 3: Proof-of-Erasure Certificate Engine



    def insert_federation_corpus_quality(self, bridge_id_hash: str, session_type: str,

                                         n_sessions: int, entropy_score: float,

                                         stationarity_score: float,

                                         centroid_velocity_mean: float,

                                         received_at_ts: int) -> int:

        """Insert anonymized federation corpus quality record (Phase 192, BP-007)."""

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO federation_corpus_quality_log "

                "(bridge_id_hash, session_type, n_sessions, entropy_score, "

                "stationarity_score, centroid_velocity_mean, received_at_ts) "

                "VALUES (?,?,?,?,?,?,?)",

                (bridge_id_hash, session_type, n_sessions, entropy_score,

                 stationarity_score, centroid_velocity_mean, received_at_ts),

            )

        return cur.lastrowid  # type: ignore[return-value]



    def get_federated_corpus_quality(self, session_type: str = "touchpad_corners",

                                     limit: int = 10) -> list:

        """Return recent federation corpus quality records (Phase 192)."""

        try:

            with self._conn() as conn:

                rows = conn.execute(

                    "SELECT bridge_id_hash, session_type, n_sessions, entropy_score, "

                    "stationarity_score, centroid_velocity_mean, federation_entropy_mean, "

                    "federation_outlier, outlier_sigma, received_at_ts, created_at "

                    "FROM federation_corpus_quality_log WHERE session_type=? "

                    "ORDER BY received_at_ts DESC LIMIT ?",

                    (session_type, limit),

                ).fetchall()

        except Exception:

            rows = []

        return [

            {

                "bridge_id_hash":         r[0],

                "session_type":           r[1],

                "n_sessions":             int(r[2]),

                "entropy_score":          float(r[3]),

                "stationarity_score":     float(r[4]),

                "centroid_velocity_mean": float(r[5]),

                "federation_entropy_mean": float(r[6]) if r[6] is not None else None,

                "federation_outlier":     bool(r[7]),

                "outlier_sigma":          float(r[8]) if r[8] is not None else None,

                "received_at_ts":         int(r[9]),

                "created_at":             r[10],

            }

            for r in rows

        ]



    # Task 5: Cross-Feature Temporal Correlation Engine



    def insert_feature_correlation(self, player_id: str, session_type: str,

                                   n_sessions_used: int, correlation_upper_tri: str,

                                   high_correlation_pairs: str,

                                   frobenius_vs_p1: "float | None",

                                   frobenius_vs_p2: "float | None",

                                   frobenius_vs_p3: "float | None",

                                   correlation_separable: bool,

                                   computed_at_ts: int = 0) -> int:

        """Insert per-player feature correlation matrix (Phase 192)."""

        if computed_at_ts == 0:

            computed_at_ts = int(time.time())

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO feature_correlation_log "

                "(player_id, session_type, n_sessions_used, correlation_upper_tri, "

                "high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3, "

                "correlation_separable, computed_at_ts) VALUES (?,?,?,?,?,?,?,?,?,?)",

                (player_id, session_type, n_sessions_used, correlation_upper_tri,

                 high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3,

                 1 if correlation_separable else 0, computed_at_ts),

            )

        return cur.lastrowid  # type: ignore[return-value]



    def get_feature_correlation(self, player_id: str = "",

                                session_type: str = "touchpad_corners") -> "dict | None":

        """Return most recent correlation entry for player_id (Phase 192)."""

        try:

            with self._conn() as conn:

                if player_id:

                    row = conn.execute(

                        "SELECT player_id, session_type, n_sessions_used, correlation_upper_tri, "

                        "high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3, "

                        "correlation_separable, computed_at_ts, created_at "

                        "FROM feature_correlation_log WHERE player_id=? AND session_type=? "

                        "ORDER BY computed_at_ts DESC LIMIT 1",

                        (player_id, session_type),

                    ).fetchone()

                else:

                    row = conn.execute(

                        "SELECT player_id, session_type, n_sessions_used, correlation_upper_tri, "

                        "high_correlation_pairs, frobenius_vs_p1, frobenius_vs_p2, frobenius_vs_p3, "

                        "correlation_separable, computed_at_ts, created_at "

                        "FROM feature_correlation_log WHERE session_type=? "

                        "ORDER BY computed_at_ts DESC LIMIT 1",

                        (session_type,),

                    ).fetchone()

        except Exception:

            row = None

        if row is None:

            return None

        return {

            "player_id":              row[0],

            "session_type":           row[1],

            "n_sessions_used":        int(row[2]),

            "correlation_upper_tri":  row[3],

            "high_correlation_pairs": row[4],

            "frobenius_vs_p1":        float(row[5]) if row[5] is not None else None,

            "frobenius_vs_p2":        float(row[6]) if row[6] is not None else None,

            "frobenius_vs_p3":        float(row[7]) if row[7] is not None else None,

            "correlation_separable":  bool(row[8]),

            "computed_at_ts":         int(row[9]),

            "created_at":             row[10],

        }



    # Task 6: Data Readiness Certificate Engine



    def insert_data_readiness_certificate(self, certificate_hash: str,

                                          certification_status: str,

                                          blocking_failures: str,

                                          advisory_warnings: str,

                                          dimension_results: str,

                                          separation_ratio: float,

                                          valid_until_ts: int,

                                          ts_ns: int) -> int:

        """Insert a data readiness certificate (idempotent on UNIQUE hash). Phase 192."""

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT OR IGNORE INTO data_readiness_certificate_log "

                "(certificate_hash, certification_status, blocking_failures, advisory_warnings, "

                "dimension_results, separation_ratio, valid_until_ts, ts_ns) "

                "VALUES (?,?,?,?,?,?,?,?)",

                (certificate_hash, certification_status, blocking_failures, advisory_warnings,

                 dimension_results, separation_ratio, valid_until_ts, ts_ns),

            )

        return cur.lastrowid or 0  # type: ignore[return-value]



    def get_latest_data_readiness_certificate(self) -> "dict | None":

        """Return most recent data readiness certificate (Phase 192)."""

        try:

            with self._conn() as conn:

                row = conn.execute(

                    "SELECT certificate_hash, certification_status, blocking_failures, "

                    "advisory_warnings, dimension_results, separation_ratio, on_chain_tx_hash, "

                    "anchored, valid_until_ts, ts_ns, created_at "

                    "FROM data_readiness_certificate_log ORDER BY ts_ns DESC LIMIT 1"

                ).fetchone()

        except Exception:

            row = None

        if row is None:

            return None

        return {

            "certificate_hash":    row[0],

            "certification_status": row[1],

            "blocking_failures":   row[2],

            "advisory_warnings":   row[3],

            "dimension_results":   row[4],

            "separation_ratio":    float(row[5]),

            "on_chain_tx_hash":    row[6],

            "anchored":            bool(row[7]),

            "valid_until_ts":      int(row[8]),

            "ts_ns":               int(row[9]),

            "created_at":          row[10],

        }



    def anchor_data_readiness_certificate(self, certificate_hash: str, tx_hash: str) -> None:

        """Mark a data readiness certificate as anchored on-chain (Phase 192)."""

        with self._conn() as conn:

            conn.execute(

                "UPDATE data_readiness_certificate_log SET on_chain_tx_hash=?, anchored=1 "

                "WHERE certificate_hash=?",

                (tx_hash, certificate_hash),

            )



    # Task 7: Session Contribution Weight Table



    def insert_session_contribution_weight(self, session_file: str, player_id: str,

                                           session_type: str,

                                           session_captured_at_ts: int,

                                           age_days: float, tbd_weight: float,

                                           type_multiplier: float,

                                           stationarity_multiplier: float,

                                           effective_weight: float,

                                           centroid_influence_rank: "int | None" = None,

                                           computed_at_ts: int = 0) -> int:

        """Insert session contribution weight (Phase 192). FROZEN: lambda=ln(2)/90."""

        if computed_at_ts == 0:

            computed_at_ts = int(time.time())

        with self._conn() as conn:

            cur = conn.execute(

                "INSERT INTO session_contribution_weight_log "

                "(session_file, player_id, session_type, session_captured_at_ts, age_days, "

                "tbd_weight, type_multiplier, stationarity_multiplier, effective_weight, "

                "centroid_influence_rank, computed_at_ts) VALUES (?,?,?,?,?,?,?,?,?,?,?)",

                (session_file, player_id, session_type, session_captured_at_ts, age_days,

                 tbd_weight, type_multiplier, stationarity_multiplier, effective_weight,

                 centroid_influence_rank, computed_at_ts),

            )

        return cur.lastrowid  # type: ignore[return-value]



    def get_session_weights(self, player_id: str = "",

                            limit: int = 50) -> list:

        """Return session contribution weights, ordered by effective_weight DESC (Phase 192)."""

        try:

            with self._conn() as conn:

                if player_id:

                    rows = conn.execute(

                        "SELECT session_file, player_id, session_type, session_captured_at_ts, "

                        "age_days, tbd_weight, type_multiplier, stationarity_multiplier, "

                        "effective_weight, centroid_influence_rank, computed_at_ts, created_at "

                        "FROM session_contribution_weight_log WHERE player_id=? "

                        "ORDER BY effective_weight DESC LIMIT ?",

                        (player_id, limit),

                    ).fetchall()

                else:

                    rows = conn.execute(

                        "SELECT session_file, player_id, session_type, session_captured_at_ts, "

                        "age_days, tbd_weight, type_multiplier, stationarity_multiplier, "

                        "effective_weight, centroid_influence_rank, computed_at_ts, created_at "

                        "FROM session_contribution_weight_log "

                        "ORDER BY effective_weight DESC LIMIT ?",

                        (limit,),

                    ).fetchall()

        except Exception:

            rows = []

        return [

            {

                "session_file":           r[0],

                "player_id":              r[1],

                "session_type":           r[2],

                "session_captured_at_ts": int(r[3]),

                "age_days":               float(r[4]),

                "tbd_weight":             float(r[5]),

                "type_multiplier":        float(r[6]),

                "stationarity_multiplier": float(r[7]),

                "effective_weight":       float(r[8]),

                "centroid_influence_rank": int(r[9]) if r[9] is not None else None,

                "computed_at_ts":         int(r[10]),

                "created_at":             r[11],

            }

            for r in rows

        ]



    def get_session_weight(self, session_file: str) -> float:

        """Return effective_weight for a specific session file (Phase 192, 1.0 if not found)."""

        try:

            with self._conn() as conn:

                row = conn.execute(

                    "SELECT effective_weight FROM session_contribution_weight_log "

                    "WHERE session_file=? ORDER BY computed_at_ts DESC LIMIT 1",

                    (session_file,),

                ).fetchone()

        except Exception:

            row = None

        return float(row[0]) if row else 1.0



    # -----------------------------------------------------------------------

    # Phase 193: FleetSignalCoherenceAgent (Agent #36) — fleet_coherence_log

    # -----------------------------------------------------------------------



    def get_prev_watchdog_event_hash(self, grind_session_id: str) -> bytes | None:

        """Return the most recent WEC hash bytes for the given grind session, or None.



        Scoped by grind_session_id so a new grind run starts a fresh WEC chain

        (parallels INV-GIC-001 grind_session_id scoping).

        """

        with self._conn() as conn:

            if grind_session_id:

                row = conn.execute(

                    "SELECT wec_hash FROM watchdog_event_log "

                    "WHERE grind_session_id = ? "

                    "ORDER BY ts_ns DESC LIMIT 1",

                    (grind_session_id,),

                ).fetchone()

            else:

                row = conn.execute(

                    "SELECT wec_hash FROM watchdog_event_log "

                    "ORDER BY ts_ns DESC LIMIT 1"

                ).fetchone()

        if row is None:

            return None

        return bytes.fromhex(row["wec_hash"])



    def insert_watchdog_event(

        self,

        event_code: int,

        event_name: str,

        pid: int,

        grind_session_id: str,

        ts_ns: int,

        metadata_json: str = "{}",

    ) -> str:

        """Append one watchdog event to the WEC chain. Returns wec_hash hex.



        WEC formula is delegated to watchdog_chain.compute_wec / genesis_wec —

        the formula module is the single source of truth (parallels grind_chain).



        Monotonicity guard: if ts_ns <= prev event ts_ns for this session,

        bump to prev_ts + 1 to preserve chain ordering across NTP backsteps.

        """

        from ..watchdog_chain import compute_wec, genesis_wec



        # Monotonicity: ensure ts_ns strictly increases within a session

        with self._conn() as conn:

            row = conn.execute(

                "SELECT MAX(ts_ns) FROM watchdog_event_log WHERE grind_session_id = ?",

                (grind_session_id,),

            ).fetchone()

        prev_ts = int(row[0]) if (row and row[0] is not None) else 0

        if ts_ns <= prev_ts:

            ts_ns = prev_ts + 1



        prev_wec = self.get_prev_watchdog_event_hash(grind_session_id)

        if prev_wec is None:

            prev_wec = genesis_wec(grind_session_id, ts_ns)

            prev_wec_hex = ""  # genesis link — no on-chain prior hash to record

        else:

            prev_wec_hex = prev_wec.hex()



        wec = compute_wec(prev_wec, event_code, pid, grind_session_id, ts_ns)

        wec_hex = wec.hex()



        with self._conn() as conn:

            conn.execute(

                "INSERT INTO watchdog_event_log "

                "(event_code, event_name, pid, grind_session_id, "

                " wec_hash, prev_wec_hash, metadata_json, ts_ns, created_at) "

                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",

                (

                    int(event_code), str(event_name)[:64], int(pid),

                    str(grind_session_id),

                    wec_hex, prev_wec_hex, str(metadata_json),

                    int(ts_ns), time.time(),

                ),

            )

        return wec_hex



    def get_watchdog_event_chain_status(

        self, grind_session_id: str = "", limit: int = 100

    ) -> dict:

        """Recompute and verify the WEC chain for a grind session.



        Returns:

            grind_session_id, chain_length, latest_wec_hash (hex), chain_intact (bool),

            last_event_code (int|None), last_event_name (str), last_event_ts (float),

            restarts_last_hour (int), genesis_ts (float).

        """

        from ..watchdog_chain import compute_wec, genesis_wec, EVENT_CODES



        with self._conn() as conn:

            if grind_session_id:

                rows = conn.execute(

                    "SELECT event_code, event_name, pid, wec_hash, ts_ns "

                    "FROM watchdog_event_log "

                    "WHERE grind_session_id = ? "

                    "ORDER BY ts_ns ASC LIMIT ?",

                    (grind_session_id, int(limit)),

                ).fetchall()

            else:

                rows = conn.execute(

                    "SELECT event_code, event_name, pid, wec_hash, ts_ns, grind_session_id "

                    "FROM watchdog_event_log "

                    "ORDER BY ts_ns ASC LIMIT ?",

                    (int(limit),),

                ).fetchall()



        if not rows:

            return {

                "grind_session_id":      grind_session_id,

                "chain_length":          0,

                "latest_wec_hash":       "",

                "chain_intact":          True,  # vacuously intact

                "last_event_code":       None,

                "last_event_name":       "",

                "last_event_ts":         0.0,

                "restarts_last_hour":    0,

                "genesis_ts":            0.0,

            }



        # Verify chain

        rows = [dict(r) for r in rows]

        sid_for_chain = grind_session_id or rows[-1].get("grind_session_id", "")

        chain_intact = True

        for i, row in enumerate(rows):

            ts_ns = int(row["ts_ns"])

            ec = int(row["event_code"])

            pid = int(row["pid"])

            stored_hex = row["wec_hash"]

            if i == 0:

                prev = genesis_wec(sid_for_chain, ts_ns)

            else:

                prev = bytes.fromhex(rows[i - 1]["wec_hash"])

            expected = compute_wec(prev, ec, pid, sid_for_chain, ts_ns)

            if expected.hex() != stored_hex:

                chain_intact = False

                break



        # Restarts last hour: BRIDGE_RESTART_TRIGGERED events in last 3600s

        restart_code = EVENT_CODES["BRIDGE_RESTART_TRIGGERED"]

        now_ns = time.time_ns()

        cutoff_ns = now_ns - 3_600_000_000_000  # 1 hour in ns

        restarts_last_hour = sum(

            1 for r in rows

            if int(r["event_code"]) == restart_code and int(r["ts_ns"]) >= cutoff_ns

        )



        latest = rows[-1]

        return {

            "grind_session_id":      sid_for_chain,

            "chain_length":          len(rows),

            "latest_wec_hash":       latest["wec_hash"],

            "chain_intact":          chain_intact,

            "last_event_code":       int(latest["event_code"]),

            "last_event_name":       str(latest.get("event_name", "")),

            "last_event_ts":         float(latest["ts_ns"]) / 1e9,

            "restarts_last_hour":    restarts_last_hour,

            "genesis_ts":            float(rows[0]["ts_ns"]) / 1e9,

        }



    # --- Phase 236-CORPUS-SNAPSHOT ---



    def insert_corpus_snapshot(

        self,

        snapshot_commitment: str,

        wiki_hash: str,

        agent_root: str,

        separation_ratio: float,

        corpus_n: int,

        ts_ns: int,

        trigger_reason: str = "",

        on_chain_confirmed: bool = False,

        tx_hash: str = "",

        ipfs_cid: str = "",

    ) -> int:

        """Insert one corpus snapshot row. Returns row id.



        UNIQUE(snapshot_commitment) enforced — duplicate inserts (e.g. two

        triggers firing on the same wiki+ratio+corpus+fleet+ts_ns) are

        idempotent: the duplicate raises sqlite3.IntegrityError which we

        translate to "already recorded" by returning the existing row id.

        """

        try:

            with self._conn() as conn:

                cur = conn.execute(

                    "INSERT INTO corpus_snapshot_log "

                    "(snapshot_commitment, wiki_hash, agent_root, separation_ratio, "

                    " corpus_n, ts_ns, on_chain_confirmed, ipfs_cid, tx_hash, "

                    " trigger_reason, created_at) "

                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",

                    (

                        str(snapshot_commitment), str(wiki_hash), str(agent_root),

                        float(separation_ratio), int(corpus_n), int(ts_ns),

                        1 if on_chain_confirmed else 0,

                        str(ipfs_cid), str(tx_hash), str(trigger_reason)[:128],

                        time.time(),

                    ),

                )

                return int(cur.lastrowid)

        except Exception:

            # Likely UNIQUE collision — return the existing row id

            with self._conn() as conn:

                row = conn.execute(

                    "SELECT id FROM corpus_snapshot_log WHERE snapshot_commitment = ?",

                    (str(snapshot_commitment),),

                ).fetchone()

            return int(row["id"]) if row else 0



    def get_corpus_snapshot_status(self) -> dict:

        """Return latest corpus snapshot with chain length.



        Returns 10 keys: total_snapshots, latest_commitment, wiki_hash,

        agent_root, separation_ratio, corpus_n, last_snapshot_ts,

        on_chain_confirmed, trigger_reason, timestamp.

        """

        import time as _t236s

        with self._conn() as conn:

            total = (conn.execute(

                "SELECT COUNT(*) FROM corpus_snapshot_log"

            ).fetchone() or (0,))[0]

            row = conn.execute(

                "SELECT snapshot_commitment, wiki_hash, agent_root, separation_ratio, "

                "       corpus_n, ts_ns, on_chain_confirmed, trigger_reason "

                "FROM corpus_snapshot_log ORDER BY ts_ns DESC LIMIT 1"

            ).fetchone()

        if row is None:

            return {

                "total_snapshots":    0,

                "latest_commitment":  "",

                "wiki_hash":          "",

                "agent_root":         "",

                "separation_ratio":   0.0,

                "corpus_n":           0,

                "last_snapshot_ts":   0.0,

                "on_chain_confirmed": False,

                "trigger_reason":     "",

                "timestamp":          _t236s.time(),

            }

        return {

            "total_snapshots":    int(total),

            "latest_commitment":  str(row[0]),

            "wiki_hash":          str(row[1]),

            "agent_root":         str(row[2]),

            "separation_ratio":   float(row[3]),

            "corpus_n":           int(row[4]),

            "last_snapshot_ts":   float(row[5]) / 1e9,

            "on_chain_confirmed": bool(row[6]),

            "trigger_reason":     str(row[7]),

            "timestamp":          _t236s.time(),

        }



    def get_corpus_snapshot_history(self, limit: int = 20) -> list[dict]:

        """Return last N snapshots in DESC ts_ns order (newest first)."""

        with self._conn() as conn:

            rows = conn.execute(

                "SELECT id, snapshot_commitment, wiki_hash, agent_root, "

                "       separation_ratio, corpus_n, ts_ns, on_chain_confirmed, "

                "       trigger_reason, created_at "

                "FROM corpus_snapshot_log ORDER BY ts_ns DESC LIMIT ?",

                (int(limit),),

            ).fetchall()

        return [dict(r) for r in rows]



    # --- Phase 237-ZK-SEPPROOF: BIOMETRIC-SNAPSHOT-v1 anchor history ---



