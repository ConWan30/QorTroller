"""ChainLogMixin — D-DECON-2 chain_anchors domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern
(removal diff is the canonical source). CREATE TABLE statements stay
centralized in _core.py._init_schema per D-DECON-2.
"""
from __future__ import annotations

import time


class ChainLogMixin:
    """Domain methods extracted from Store; resolved via MRO."""
    def insert_oracle_publication(
        self,
        oracle_type: str,
        device_id: str,
        tx_hash: str | None,
        payload_json: str,
    ) -> int:
        """Log an oracle publication event. Returns row id."""
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO oracle_publications "
                "(oracle_type, device_id, tx_hash, payload_json, published_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (oracle_type, device_id, tx_hash, payload_json, now),
            )
            return cur.lastrowid

    def get_oracle_publications(
        self, oracle_type: str | None = None, limit: int = 50
    ) -> list[dict]:
        """Return oracle publication log, optionally filtered by oracle_type."""
        with self._conn() as conn:
            if oracle_type:
                rows = conn.execute(
                    "SELECT * FROM oracle_publications WHERE oracle_type=? "
                    "ORDER BY published_at DESC LIMIT ?",
                    (oracle_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM oracle_publications "
                    "ORDER BY published_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [dict(r) for r in rows]

    def insert_gate_attestation(
        self,
        attestation_hash: str,
        consecutive_clean: int,
        gate_n: int,
        divergence_rate: float,
        on_chain_tx: str | None = None,
    ) -> int:
        """Persist a gate attestation hash (Phase 84). Returns row id.

        INSERT OR IGNORE — idempotent; same attestation_hash is a no-op (no exception).
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT OR IGNORE INTO gate_attestations "
                "(attestation_hash, consecutive_clean, gate_n, divergence_rate, "
                " on_chain_tx, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    attestation_hash,
                    consecutive_clean,
                    gate_n,
                    divergence_rate,
                    on_chain_tx,
                    time.time(),
                ),
            )
            return cur.lastrowid

    def get_gate_attestations(self, limit: int = 10) -> list[dict]:
        """Return the most recent gate attestation records (Phase 84), newest-first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM gate_attestations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(r) for r in rows]

    def insert_protocol_coherence_log(
        self,
        merkle_root: str,
        agent_count: int,
        anchor_hash: str = "",
        on_chain_confirmed: bool = False,
        allowlist_hash: str = "",
        governance_provenance_hash: str = "",
    ) -> int:
        """Insert a PoPC Merkle root anchor record (Phase 221/224/227).

        Args:
            merkle_root:               Hex string of the Merkle root (64 chars).
            agent_count:               Number of agents included in the Merkle tree.
            anchor_hash:               On-chain tx hash if anchored; empty if local only.
            on_chain_confirmed:        True when the tx was confirmed on IoTeX testnet.
            allowlist_hash:            SHA-256 of INVARIANTS_ALLOWLIST.json at anchor time (Phase 224).
            governance_provenance_hash: Latest governance provenance hash anchored on-chain (Phase 227).

        Returns:
            Row id of the inserted record.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO protocol_coherence_log "
                "(merkle_root, agent_count, anchor_hash, on_chain_confirmed, created_at, "
                "allowlist_hash, governance_provenance_hash) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(merkle_root),
                    int(agent_count),
                    str(anchor_hash),
                    1 if on_chain_confirmed else 0,
                    now,
                    str(allowlist_hash),
                    str(governance_provenance_hash),
                ),
            )
            return cur.lastrowid or 0

    def get_protocol_coherence_status(self) -> dict:
        """Return the most recent PoPC anchor status (Phase 221/227).

        Returns dict with keys:
            total_anchors / latest_merkle_root / agent_count /
            on_chain_confirmed / last_anchor_ts / governance_provenance_hash / timestamp
        """
        import time as _t221
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM protocol_coherence_log"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT merkle_root, agent_count, on_chain_confirmed, created_at, "
                "COALESCE(governance_provenance_hash, '') "
                "FROM protocol_coherence_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row:
            return {
                "total_anchors":              int(total),
                "latest_merkle_root":         str(row[0]),
                "agent_count":                int(row[1]),
                "on_chain_confirmed":         bool(row[2]),
                "last_anchor_ts":             float(row[3]),
                "governance_provenance_hash": str(row[4]),
                "timestamp":                  _t221.time(),
            }
        return {
            "total_anchors":              0,
            "latest_merkle_root":         None,
            "agent_count":                0,
            "on_chain_confirmed":         False,
            "last_anchor_ts":             None,
            "governance_provenance_hash": "",
            "timestamp":                  _t221.time(),
        }

    def get_protocol_coherence_history(self, limit: int = 10) -> list:
        """Return the most recent PoPC anchor records (Phase 221).

        Returns list of dicts with keys:
            id / merkle_root / agent_count / on_chain_confirmed / created_at
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, merkle_root, agent_count, on_chain_confirmed, created_at "
                "FROM protocol_coherence_log ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            {
                "id":                int(r[0]),
                "merkle_root":       str(r[1]),
                "agent_count":       int(r[2]),
                "on_chain_confirmed": bool(r[3]),
                "created_at":        float(r[4]),
            }
            for r in rows
        ]

    def insert_bbg_proposal_log(
        self,
        proposal_hash: str,
        proposer_address: str = "",
        vhp_token_id: int = 0,
        vhp_expires_at: float = 0.0,
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
    ) -> int:
        """Insert a BBG governance proposal record (Phase 222).

        Returns:
            Row id of the inserted record.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO bbg_proposal_log "
                "(proposal_hash, proposer_address, vhp_token_id, vhp_expires_at, "
                "on_chain_confirmed, tx_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    str(proposal_hash),
                    str(proposer_address),
                    int(vhp_token_id),
                    float(vhp_expires_at),
                    1 if on_chain_confirmed else 0,
                    str(tx_hash),
                    now,
                ),
            )
            return cur.lastrowid or 0

    def get_bbg_status(self) -> dict:
        """Return the BBG proposal status (Phase 222).

        Returns dict with keys:
            total_proposals / latest_proposal_hash / latest_proposer /
            on_chain_confirmed / last_proposal_ts / timestamp
        """
        import time as _t222
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM bbg_proposal_log"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT proposal_hash, proposer_address, on_chain_confirmed, created_at "
                "FROM bbg_proposal_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()
        if row:
            return {
                "total_proposals":     int(total),
                "latest_proposal_hash": str(row[0]),
                "latest_proposer":     str(row[1]),
                "on_chain_confirmed":  bool(row[2]),
                "last_proposal_ts":    float(row[3]),
                "timestamp":           _t222.time(),
            }
        return {
            "total_proposals":     0,
            "latest_proposal_hash": None,
            "latest_proposer":     None,
            "on_chain_confirmed":  False,
            "last_proposal_ts":    None,
            "timestamp":           _t222.time(),
        }

    def get_bbg_proposal_history(self, limit: int = 10) -> list:
        """Return the most recent BBG proposal records (Phase 222).

        Returns list of dicts with keys:
            id / proposal_hash / proposer_address / vhp_token_id /
            on_chain_confirmed / created_at
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, proposal_hash, proposer_address, vhp_token_id, "
                "on_chain_confirmed, created_at "
                "FROM bbg_proposal_log ORDER BY created_at DESC LIMIT ?",
                (int(limit),),
            ).fetchall()
        return [
            {
                "id":               int(r[0]),
                "proposal_hash":    str(r[1]),
                "proposer_address": str(r[2]),
                "vhp_token_id":     int(r[3]),
                "on_chain_confirmed": bool(r[4]),
                "created_at":       float(r[5]),
            }
            for r in rows
        ]

    def insert_invariant_gate_log(
        self,
        gate_pass: bool,
        total_checked: int,
        failures_json: str = "[]",
        run_source: str = "manual",
        previous_allowlist_hash: str = "",
        new_allowlist_hash: str = "",
        reason_category: str = "",
        reason_text: str = "",
        vhp_token_id: str = "",
    ) -> int:
        """Record a PV-CI invariant gate run result (Phase 223/224/228).

        Args:
            gate_pass:               True if all invariants passed.
            total_checked:           Number of invariants evaluated.
            failures_json:           JSON-encoded list of failure description strings.
            run_source:              'manual', 'ci', 'api', or 'governance:<cat>:<text>'.
            previous_allowlist_hash: SHA-256 of allowlist before --generate (Phase 224).
            new_allowlist_hash:      SHA-256 of allowlist after --generate (Phase 224).
            reason_category:         Governance category (refactor/bugfix/...) (Phase 224).
            reason_text:             Human-readable governance rationale (Phase 224).
            vhp_token_id:            VHP token ID supplied for invariant_change events (Phase 228).
        Returns:
            row id of the inserted record.
        """
        import time as _t223
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO invariant_gate_log "
                "(gate_pass, total_checked, failures_json, run_source, created_at, "
                "previous_allowlist_hash, new_allowlist_hash, reason_category, reason_text, "
                "vhp_token_id) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    int(bool(gate_pass)),
                    int(total_checked),
                    failures_json,
                    run_source,
                    _t223.time(),
                    str(previous_allowlist_hash),
                    str(new_allowlist_hash),
                    str(reason_category),
                    str(reason_text),
                    str(vhp_token_id),
                ),
            )
            return int(cur.lastrowid)

    def get_invariant_gate_status(self) -> dict:
        """Return PV-CI invariant gate summary (Phase 223).

        Returns dict with keys:
            pv_ci_enabled / gate_pass / total_checked / failure_count /
            last_failures / last_run_ts / timestamp
        """
        import json as _json223
        import time as _t223

        with self._conn() as conn:
            row = conn.execute(
                "SELECT gate_pass, total_checked, failures_json, created_at "
                "FROM invariant_gate_log ORDER BY created_at DESC LIMIT 1"
            ).fetchone()

        if row:
            failures = _json223.loads(row[1] if False else row["failures_json"])
            return {
                "pv_ci_enabled":  True,
                "gate_pass":      bool(row["gate_pass"]),
                "total_checked":  int(row["total_checked"]),
                "failure_count":  len(failures),
                "last_failures":  failures,
                "last_run_ts":    float(row["created_at"]),
                "timestamp":      _t223.time(),
            }
        return {
            "pv_ci_enabled":  True,
            "gate_pass":      None,
            "total_checked":  0,
            "failure_count":  0,
            "last_failures":  [],
            "last_run_ts":    None,
            "timestamp":      _t223.time(),
        }

    def insert_allowlist_change_log(
        self,
        previous_hash: str,
        new_hash: str,
        merkle_root_at_change: str = "",
        reason_from_gate_log: "str | None" = None,
    ) -> int:
        """Record a detected allowlist hash change (Phase 224).

        Called by ProtocolCoherenceAgent when allowlist_hash changes between anchor cycles.
        reason_from_gate_log is fetched from the most recent invariant_gate_log entry
        within 60 seconds; NULL if no matching governance event was found (suspicious).

        Returns:
            Row id of the inserted record.
        """
        import time as _t224
        detected_at = str(_t224.time())
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO allowlist_change_log "
                "(previous_hash, new_hash, merkle_root_at_change, detected_at, reason_from_gate_log) "
                "VALUES (?, ?, ?, ?, ?)",
                (
                    str(previous_hash),
                    str(new_hash),
                    str(merkle_root_at_change),
                    detected_at,
                    reason_from_gate_log,
                ),
            )
            return cur.lastrowid or 0

    def get_allowlist_change_status(self) -> dict:
        """Return allowlist change log summary (Phase 224).

        Returns dict with keys:
            total_changes / suspicious_count / latest_previous_hash /
            latest_new_hash / latest_detected_at / timestamp
        """
        import time as _t224
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM allowlist_change_log"
            ).fetchone() or (0,))[0]
            suspicious = (conn.execute(
                "SELECT COUNT(*) FROM allowlist_change_log WHERE reason_from_gate_log IS NULL"
            ).fetchone() or (0,))[0]
            row = conn.execute(
                "SELECT previous_hash, new_hash, detected_at, reason_from_gate_log "
                "FROM allowlist_change_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if row:
            return {
                "total_changes":       int(total),
                "suspicious_count":    int(suspicious),
                "latest_previous_hash": str(row[0]),
                "latest_new_hash":     str(row[1]),
                "latest_detected_at":  str(row[2]),
                "timestamp":           _t224.time(),
            }
        return {
            "total_changes":       0,
            "suspicious_count":    0,
            "latest_previous_hash": None,
            "latest_new_hash":     None,
            "latest_detected_at":  None,
            "timestamp":           _t224.time(),
        }

    def insert_governance_provenance(
        self,
        governance_provenance_hash: str,
        previous_provenance_hash: str,
        new_allowlist_hash: str,
        reason_category: str,
        reason_text: str,
    ) -> int:
        """Record a provenance chain entry for an allowlist governance event (Phase 225).

        The governance_provenance_hash is SHA-256(prev_prov || new_hash || category || text || ts_ns_8b),
        forming a tamper-evident hash-linked audit trail.

        Returns:
            Row id of the inserted record.
        """
        import time as _t225
        ts = _t225.time()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO governance_provenance_chain "
                "(governance_provenance_hash, previous_provenance_hash, new_allowlist_hash, "
                "reason_category, reason_text, created_at) VALUES (?,?,?,?,?,?)",
                (governance_provenance_hash, previous_provenance_hash, new_allowlist_hash,
                 reason_category, reason_text, ts),
            )
            row_id = int(cur.lastrowid or 0)
            # Also stamp the most recent invariant_gate_log row with the hash
            conn.execute(
                "UPDATE invariant_gate_log SET governance_provenance_hash = ? "
                "WHERE id = (SELECT MAX(id) FROM invariant_gate_log)",
                (governance_provenance_hash,),
            )
        return row_id

    def get_governance_provenance_history(self, limit: int = 20) -> list:
        """Return the most recent governance provenance chain entries (Phase 225).

        Returns list of dicts ordered newest-first with keys:
            id / governance_provenance_hash / previous_provenance_hash / new_allowlist_hash /
            reason_category / reason_text / created_at
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, governance_provenance_hash, previous_provenance_hash, "
                "new_allowlist_hash, reason_category, reason_text, created_at "
                "FROM governance_provenance_chain ORDER BY id DESC LIMIT ?",
                (max(1, int(limit)),),
            ).fetchall()
        return [
            {
                "id":                         int(r["id"]),
                "governance_provenance_hash":  str(r["governance_provenance_hash"]),
                "previous_provenance_hash":    str(r["previous_provenance_hash"]),
                "new_allowlist_hash":          str(r["new_allowlist_hash"]),
                "reason_category":             str(r["reason_category"]),
                "reason_text":                 str(r["reason_text"]),
                "created_at":                  float(r["created_at"]),
            }
            for r in rows
        ]

    def get_latest_governance_provenance_hash(self) -> str:
        """Return the most recent governance_provenance_hash from governance_provenance_chain (Phase 225).

        Returns '0' * 64 (genesis sentinel) when no entries exist.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT governance_provenance_hash FROM governance_provenance_chain "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
        return str(row["governance_provenance_hash"]) if row else "0" * 64

    def insert_age_weight_analysis_log(
        self,
        probe_type: str,
        raw_ratio: float,
        age_weighted_ratio: float,
        halflife_days: float,
        n_sessions_used: int,
    ) -> int:
        """Insert an age-weighted separation ratio analysis result (Phase 175).

        temporal_drift_index = raw_ratio - age_weighted_ratio.
          positive  → old sessions inflate ratio (P1 non-stationarity)
          negative  → new sessions stronger (player stabilising)
          near-zero → biometrically stationary (ideal)
        drift_direction: P1_NONSTATIONARITY | IMPROVING | STABLE
        """
        tdi = round(float(raw_ratio) - float(age_weighted_ratio), 6)
        if tdi > 0.05:
            direction = "P1_NONSTATIONARITY"
        elif tdi < -0.05:
            direction = "IMPROVING"
        else:
            direction = "STABLE"
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO age_weight_analysis_log "
                "(probe_type, raw_ratio, age_weighted_ratio, temporal_drift_index, "
                "halflife_days, n_sessions_used, drift_direction, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    str(probe_type),
                    float(raw_ratio),
                    float(age_weighted_ratio),
                    tdi,
                    float(halflife_days),
                    int(n_sessions_used),
                    direction,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_age_weight_analysis_status(self, limit: int = 1) -> "list[dict]":
        """Return most recent age-weight analysis results, newest first (Phase 175)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT id, probe_type, raw_ratio, age_weighted_ratio, "
                "temporal_drift_index, halflife_days, n_sessions_used, "
                "drift_direction, created_at "
                "FROM age_weight_analysis_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [
            {
                "id":                   r[0],
                "probe_type":           r[1],
                "raw_ratio":            float(r[2]),
                "age_weighted_ratio":   float(r[3]),
                "temporal_drift_index": float(r[4]),
                "halflife_days":        float(r[5]),
                "n_sessions_used":      int(r[6]),
                "drift_direction":      r[7],
                "created_at":           r[8],
            }
            for r in rows
        ]

    def insert_poac_chain_audit_log(
        self,
        device_id: str,
        total_records: int,
        valid_links: int,
        broken_links: int,
    ) -> int:
        """Insert a PoAC chain integrity audit result (Phase 176).

        integrity_score = valid_links / total_links (0.0 when total=0 → score=1.0 vacuous).
        audit_passed = True when integrity_score >= 1.0 (no broken links).
        W1 mitigation: only aggregate counts stored — no broken record IDs.
        """
        if total_records > 0:
            integrity_score = round(float(valid_links) / float(total_records), 6)
        else:
            integrity_score = 1.0  # vacuously intact
        audit_passed = 1 if broken_links == 0 else 0
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO poac_chain_audit_log "
                "(device_id, total_records, valid_links, broken_links, "
                "integrity_score, audit_passed, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    str(device_id),
                    int(total_records),
                    int(valid_links),
                    int(broken_links),
                    integrity_score,
                    audit_passed,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_poac_chain_audit_status(
        self, device_id: "str | None" = None, limit: int = 1
    ) -> "list[dict]":
        """Return most recent chain audit results (Phase 176).

        If device_id is provided, filters to that device only.
        Returns newest-first. W1: never exposes broken record IDs.
        """
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, total_records, valid_links, broken_links, "
                    "integrity_score, audit_passed, created_at "
                    "FROM poac_chain_audit_log WHERE device_id=? "
                    "ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, total_records, valid_links, broken_links, "
                    "integrity_score, audit_passed, created_at "
                    "FROM poac_chain_audit_log ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {
                "id":              r[0],
                "device_id":       r[1],
                "total_records":   int(r[2]),
                "valid_links":     int(r[3]),
                "broken_links":    int(r[4]),
                "integrity_score": float(r[5]),
                "audit_passed":    bool(r[6]),
                "created_at":      r[7],
            }
            for r in rows
        ]

    def insert_ceremony_audit_entry(
        self,
        ceremony_id: str,
        circuit_name: str,
        participant_address: str,
        contribution_hash: str,
        ts_ns: int = 0,
    ) -> int:
        """Insert a ZK ceremony participant entry (Phase 179).

        Anti-replay: UNIQUE(ceremony_id, participant_address, circuit_name).
        Duplicate entries raise sqlite3.IntegrityError (caller should catch and skip).
        Returns new row id on success.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO ceremony_audit_log "
                "(ceremony_id, circuit_name, participant_address, "
                "contribution_hash, ts_ns, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    str(ceremony_id),
                    str(circuit_name),
                    str(participant_address),
                    str(contribution_hash),
                    int(ts_ns),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_ceremony_audit_status(self) -> "dict":
        """Return ceremony audit summary for GET /agent/ceremony-audit-status (Phase 179).

        Returns 7 keys: ceremony_audit_enabled/total_entries/distinct_participants/
        circuits_audited/min_participants/audit_passed/timestamp.
        audit_passed=True when distinct_participants >= min_participants across all circuits.
        When ceremony_audit_enabled=False (default): audit_passed=True (gate inactive).
        """
        ts_now = time.time()
        with self._conn() as conn:
            total_entries = conn.execute(
                "SELECT COUNT(*) FROM ceremony_audit_log"
            ).fetchone()[0]
            distinct_participants = conn.execute(
                "SELECT COUNT(DISTINCT participant_address) FROM ceremony_audit_log"
            ).fetchone()[0]
            circuits_row = conn.execute(
                "SELECT COUNT(DISTINCT circuit_name) FROM ceremony_audit_log"
            ).fetchone()
            circuits_audited = int(circuits_row[0]) if circuits_row else 0
        return {
            "ceremony_audit_enabled":   False,  # always reported; caller overlays from cfg
            "total_entries":            int(total_entries),
            "distinct_participants":    int(distinct_participants),
            "circuits_audited":         circuits_audited,
            "min_participants":         3,       # caller overlays from cfg
            "audit_passed":             True,    # caller overlays when enabled
            "timestamp":                ts_now,
        }

    def insert_coherence_entry(self, entry: dict) -> str:
        """INSERT OR IGNORE on coherence_id (idempotent). Returns coherence_id.
        evidence_json must already be BP-007 scrubbed (no raw biometric fields)."""
        import json as _json
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT OR IGNORE INTO fleet_coherence_log "
                    "(coherence_id, failure_mode, rule_name, agents_involved, severity, "
                    " explanation, resolution, evidence_json, phase_detected, ts_ns) "
                    "VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        entry["coherence_id"],
                        entry["failure_mode"],
                        entry["rule_name"],
                        entry["agents_involved"]
                        if isinstance(entry["agents_involved"], str)
                        else _json.dumps(entry["agents_involved"]),
                        entry["severity"],
                        entry["explanation"],
                        entry["resolution"],
                        entry.get("evidence_json", "[]"),
                        entry.get("phase_detected", 193),
                        entry.get("ts_ns", 0),
                    ),
                )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
        return entry["coherence_id"]

    def get_open_coherence_entries(
        self,
        severity: "str | None" = None,
        failure_mode: "str | None" = None,
    ) -> "list[dict]":
        """Return all unresolved fleet_coherence_log entries, optionally filtered."""
        import json as _json
        clauses = ["resolved = 0"]
        params: list = []
        if severity:
            clauses.append("severity = ?")
            params.append(severity)
        if failure_mode:
            clauses.append("failure_mode = ?")
            params.append(failure_mode)
        where = " AND ".join(clauses)
        try:
            with self._conn() as conn:
                rows = conn.execute(
                    f"SELECT * FROM fleet_coherence_log WHERE {where} "
                    "ORDER BY created_at DESC LIMIT 100",
                    params,
                ).fetchall()
        except Exception:
            return []
        cols = [
            "id", "coherence_id", "failure_mode", "rule_name", "agents_involved",
            "severity", "explanation", "resolution", "evidence_json",
            "promoted_to_wif", "wif_entry_id", "wiki_contradict_written",
            "alert_published", "resolved", "resolved_at", "resolved_by",
            "phase_detected", "ts_ns", "created_at",
        ]
        result = []
        for row in rows:
            d = dict(zip(cols, row))
            d["promoted_to_wif"] = bool(d["promoted_to_wif"])
            d["resolved"] = bool(d["resolved"])
            try:
                d["agents_involved"] = _json.loads(d["agents_involved"])
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
            result.append(d)
        return result

    def get_coherence_summary(self) -> dict:
        """Return aggregated fleet coherence status for GET /agent/fleet-coherence-summary."""
        from datetime import datetime, timezone
        try:
            with self._conn() as conn:
                total_row = conn.execute(
                    "SELECT COUNT(*) FROM fleet_coherence_log WHERE resolved=0"
                ).fetchone()
                total_open = int(total_row[0]) if total_row else 0

                sev_rows = conn.execute(
                    "SELECT severity, COUNT(*) FROM fleet_coherence_log "
                    "WHERE resolved=0 GROUP BY severity"
                ).fetchall()
                by_severity = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
                for sev, cnt in sev_rows:
                    if sev in by_severity:
                        by_severity[sev] = int(cnt)

                mode_rows = conn.execute(
                    "SELECT failure_mode, COUNT(*) FROM fleet_coherence_log "
                    "WHERE resolved=0 GROUP BY failure_mode"
                ).fetchall()
                by_mode = {"CONTRADICTION": 0, "ORPHAN": 0, "INVERSION": 0}
                for mode, cnt in mode_rows:
                    if mode in by_mode:
                        by_mode[mode] = int(cnt)

                promo_row = conn.execute(
                    "SELECT COUNT(*) FROM fleet_coherence_log WHERE promoted_to_wif=1"
                ).fetchone()
                promoted = int(promo_row[0]) if promo_row else 0

                last_row = conn.execute(
                    "SELECT created_at FROM fleet_coherence_log ORDER BY created_at DESC LIMIT 1"
                ).fetchone()
                last_checked = last_row[0] if last_row else ""
        except Exception:
            total_open, by_severity, by_mode, promoted, last_checked = (
                0,
                {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0},
                {"CONTRADICTION": 0, "ORPHAN": 0, "INVERSION": 0},
                0,
                "",
            )
        return {
            "total_open":      total_open,
            "by_severity":     by_severity,
            "by_mode":         by_mode,
            "promoted_to_wif": promoted,
            "last_checked_at": last_checked,
        }

    def mark_coherence_resolved(self, coherence_id: str, resolved_by: str) -> None:
        """Mark a coherence entry as resolved."""
        from datetime import datetime, timezone
        ts = datetime.now(timezone.utc).isoformat()
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE fleet_coherence_log SET resolved=1, resolved_at=?, resolved_by=? "
                    "WHERE coherence_id=?",
                    (ts, resolved_by, coherence_id),
                )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    def mark_coherence_promoted(self, coherence_id: str, wif_id: str) -> None:
        """Mark a coherence entry as promoted to a WIF entry."""
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE fleet_coherence_log SET promoted_to_wif=1, wif_entry_id=? "
                    "WHERE coherence_id=?",
                    (wif_id, coherence_id),
                )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    def upsert_coherence_fingerprint(self, rule_name: str, failure_mode: str) -> None:
        """Insert or increment occurrence_count for rule_name in coherence_fingerprint_log.

        Called once per detection cycle per rule that fires. Sets persistent=1 when
        occurrence_count reaches N_PROMOTE_THRESHOLD (3). Fail-open: never raises.
        Uses two-statement insert-or-ignore + update pattern for broad SQLite compatibility.
        """
        N_PROMOTE_THRESHOLD = 3
        try:
            from datetime import datetime, timezone
            now = datetime.now(timezone.utc).isoformat()
            with self._conn() as conn:
                # Step 1: ensure row exists (occurrence_count starts at 0 so
                #          the UPDATE always owns the increment logic)
                conn.execute(
                    "INSERT OR IGNORE INTO coherence_fingerprint_log "
                    "(rule_name, failure_mode, first_seen_at, last_seen_at, "
                    " occurrence_count, persistent) "
                    "VALUES (?, ?, ?, ?, 0, 0)",
                    (rule_name, failure_mode, now, now),
                )
                # Step 2: increment occurrence_count and flip persistent when threshold met
                conn.execute(
                    "UPDATE coherence_fingerprint_log SET "
                    "  occurrence_count = occurrence_count + 1, "
                    "  last_seen_at     = ?, "
                    "  failure_mode     = ?, "
                    "  persistent       = CASE WHEN (occurrence_count + 1) >= ? "
                    "                    THEN 1 ELSE persistent END "
                    "WHERE rule_name = ?",
                    (now, failure_mode, N_PROMOTE_THRESHOLD, rule_name),
                )
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

    def get_coherence_fingerprint_status(self) -> dict:
        """Return summary of coherence_fingerprint_log for GET /agent/coherence-fingerprint-status.

        Returns: total_rules, persistent_count, total_occurrences, top_rules (list),
                 maturity_penalty (0.0–1.0), timestamp.
        """
        try:
            import sqlite3 as _sq194
            with _sq194.connect(self._db_path) as conn:
                conn.row_factory = _sq194.Row
                total_row = conn.execute(
                    "SELECT COUNT(*) as n FROM coherence_fingerprint_log"
                ).fetchone()
                total_rules = int(total_row["n"]) if total_row else 0

                pers_row = conn.execute(
                    "SELECT COUNT(*) as n FROM coherence_fingerprint_log WHERE persistent=1"
                ).fetchone()
                persistent_count = int(pers_row["n"]) if pers_row else 0

                occ_row = conn.execute(
                    "SELECT SUM(occurrence_count) as s FROM coherence_fingerprint_log"
                ).fetchone()
                total_occurrences = int(occ_row["s"]) if (occ_row and occ_row["s"] is not None) else 0

                top_rows = conn.execute(
                    "SELECT rule_name, failure_mode, occurrence_count, persistent, "
                    "       first_seen_at, last_seen_at "
                    "FROM coherence_fingerprint_log "
                    "ORDER BY occurrence_count DESC LIMIT 5"
                ).fetchall()
                top_rules = [dict(r) for r in top_rows]

            maturity_penalty = round(min(1.0, persistent_count * 0.10), 4)
            return {
                "total_rules":       total_rules,
                "persistent_count":  persistent_count,
                "total_occurrences": total_occurrences,
                "maturity_penalty":  maturity_penalty,
                "top_rules":         top_rules,
            }
        except Exception:
            return {
                "total_rules":       0,
                "persistent_count":  0,
                "total_occurrences": 0,
                "maturity_penalty":  0.0,
                "top_rules":         [],
            }

    def get_persistent_contradictions(self) -> list:
        """Return all rules with persistent=1 (occurrence_count >= N_PROMOTE_THRESHOLD).

        Used by ProtocolMaturityScoringAgent._threat_forecast_accuracy_component()
        to apply the persistent contradiction penalty.
        """
        try:
            import sqlite3 as _sq194b
            with _sq194b.connect(self._db_path) as conn:
                conn.row_factory = _sq194b.Row
                rows = conn.execute(
                    "SELECT rule_name, failure_mode, occurrence_count, last_seen_at "
                    "FROM coherence_fingerprint_log WHERE persistent=1 "
                    "ORDER BY occurrence_count DESC"
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception:
            return []

