"""BiometricMixin — D-DECON-2 biometric domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern.
_init_schema (CREATE TABLE anchors) STAY in _core.
"""
from __future__ import annotations

import json
import time


class BiometricMixin:
    """Biometric fingerprint / renewal / persona-break methods; via MRO."""
    def store_fingerprint_state(
        self,
        device_id: str,
        mean_dict: dict,
        var_dict: dict,
        n_sessions: int,
    ):
        """Persist the classifier's mean and variance arrays for cross-session distance computation."""
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO biometric_fingerprint_store
                    (device_id, mean_json, var_json, n_sessions, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(device_id) DO UPDATE SET
                    mean_json  = excluded.mean_json,
                    var_json   = excluded.var_json,
                    n_sessions = excluded.n_sessions,
                    updated_at = excluded.updated_at
            """, (
                device_id,
                json.dumps(mean_dict, sort_keys=True),
                json.dumps(var_dict, sort_keys=True),
                n_sessions,
                time.time(),
            ))

    def get_fingerprint_variance(self, device_id: str):
        """Return the stored variance vector as a numpy array, or None if not available.

        Returns numpy ndarray of shape (7,) in FEATURE_KEYS canonical order, or None.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT var_json FROM biometric_fingerprint_store WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            import numpy as np
            from ..continuity_prover import FEATURE_KEYS
            var_dict = json.loads(row["var_json"])
            # Return values in canonical FEATURE_KEYS order so the vector aligns with
            # the distance computation in ContinuityProver.compute_distance().
            return np.array([var_dict.get(k, 0.0) for k in FEATURE_KEYS], dtype=np.float64)
        except Exception:
            return None

    def mark_device_claimed(self, device_id: str, claimed_by: str):
        """Record that a device has been used in a continuity claim (anti-replay)."""
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO continuity_claims (device_id, claimed_by, claimed_at)
                VALUES (?, ?, ?)
            """, (device_id, claimed_by, time.time()))

    def is_device_claimed(self, device_id: str) -> bool:
        """Return True if this device has already been used in a continuity claim."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM continuity_claims WHERE device_id = ?", (device_id,)
            ).fetchone()
            return row is not None

    def get_continuity_chain(self, device_id: str) -> list[dict]:
        """Return all continuity claim records involving this device (as source or destination).

        Each entry: {device_id, claimed_by, claimed_at, direction}
        direction = "source" if this device was the old device; "destination" if the new one.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM continuity_claims WHERE device_id = ? OR claimed_by = ?",
                (device_id, device_id),
            ).fetchall()
            result = []
            for row in rows:
                entry = dict(row)
                entry["direction"] = "source" if entry["claimed_by"] != device_id else "destination"
                result.append(entry)
            return result

    def get_all_fingerprinted_devices(self) -> list[str]:
        """Return device IDs that have a stored biometric fingerprint."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT device_id FROM biometric_fingerprint_store"
            ).fetchall()
            return [r["device_id"] for r in rows]

    def get_controller_twin_snapshot(self, device_id: str) -> dict:
        """Aggregate all data for the My Controller 3D page (Phase 59)."""
        device   = self.get_device(device_id) or {}
        profile  = self.get_player_calibration_profile(device_id) or {}
        ioid     = self.get_ioid_device(device_id) or {}
        passport = self.get_tournament_passport(device_id) or {}
        audit_log = self.get_operator_audit_log(limit=10, device_id=device_id[:16])
        # Query biometric_fingerprint_store directly (Phase 59)
        with self._conn() as conn:
            _fp_row = conn.execute(
                "SELECT * FROM biometric_fingerprint_store WHERE device_id = ?",
                (device_id,),
            ).fetchone()
            biofp = dict(_fp_row) if _fp_row else {}
            recent = conn.execute(
                "SELECT record_hash, inference, pitl_l4_distance, pitl_humanity_prob, "
                "pitl_l4_features, created_at FROM records "
                "WHERE device_id = ? ORDER BY created_at DESC LIMIT 20",
                (device_id,),
            ).fetchall()
            insight_rows = conn.execute(
                "SELECT content, severity, insight_type, created_at "
                "FROM protocol_insights WHERE device_id = ? "
                "ORDER BY created_at DESC LIMIT 5",
                (device_id,),
            ).fetchall()
        dists = [r["pitl_l4_distance"] for r in recent if r["pitl_l4_distance"] is not None]
        trend = "UNKNOWN"
        if len(dists) >= 4:
            mid = len(dists) // 2
            first_h  = sum(dists[mid:]) / max(len(dists) - mid, 1)
            second_h = sum(dists[:mid]) / mid
            trend = ("DEGRADING" if first_h > second_h * 1.1
                     else "IMPROVING" if first_h < second_h * 0.9 else "STABLE")
        return {
            "device":    dict(device) if device else {},
            "calibration": {
                "anomaly_threshold":    profile.get("anomaly_threshold"),
                "continuity_threshold": profile.get("continuity_threshold"),
                "baseline_mean":        profile.get("baseline_mean"),
                "baseline_std":         profile.get("baseline_std"),
                "session_count":        profile.get("session_count", 0),
            },
            "biometric_fingerprint": {
                "mean_json":  biofp.get("mean_json"),
                "var_json":   biofp.get("var_json"),
                "n_sessions": biofp.get("n_sessions", 0),
            },
            "ioid":     {"registered": bool(ioid), "did": ioid.get("did"), "tx_hash": ioid.get("tx_hash")},
            "passport": {
                "issued": bool(passport),
                "passport_hash": passport.get("passport_hash"),
                "min_humanity_int": passport.get("min_humanity_int"),
                "on_chain": bool(passport.get("on_chain")),
                "issued_at": passport.get("issued_at"),
            },
            "audit_log": audit_log,
            "anomaly_trend": trend,
            "recent_records": [dict(r) for r in recent],
            "insights": [dict(r) for r in insight_rows],
        }

    def insert_gsr_sample(
        self,
        device_id: str,
        arousal_index: float,
        correlation: float,
        conductance_raw: float = 0.0,
        l7_features_json: str = "",
    ) -> int:
        """Persist a GSR biometric sample. Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO gsr_samples "
                "(device_id, arousal_index, correlation, conductance_raw, l7_features_json) "
                "VALUES (?,?,?,?,?)",
                (device_id, arousal_index, correlation, conductance_raw, l7_features_json),
            )
            return cur.lastrowid

    def get_gsr_samples(self, device_id: str, limit: int = 50) -> list:
        """Return GSR samples for a device, newest first."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM gsr_samples WHERE device_id=? ORDER BY created_at DESC LIMIT ?",
                (device_id, limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_ipact_renewal_head(self, device_id: str) -> dict | None:
        """Return the latest renewal commitment for a device (highest epoch_index), or None.

        Keys: commitment (bytes), epoch_index (int), ts_ns (int). Used to chain the next
        renewal (prev_commitment) and to seed the monotonic ts_ns / epoch guards.
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT commitment, epoch_index, ts_ns FROM ipact_renewal_commitments "
                "WHERE device_id = ? ORDER BY epoch_index DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "commitment": bytes.fromhex(row[0]),
            "epoch_index": int(row[1]),
            "ts_ns": int(row[2]),
        }

    def get_prev_ipact_ts_ns(self, device_id: str) -> int:
        """Return MAX(ts_ns) for a device's renewal commitments (0 if none).

        Mirrors get_prev_gic_ts_ns — the monotonicity guard input (INV-GIC-002 pattern).
        """
        with self._conn() as conn:
            row = conn.execute(
                "SELECT MAX(ts_ns) FROM ipact_renewal_commitments WHERE device_id = ?",
                (device_id,),
            ).fetchone()
        return int(row[0]) if row and row[0] is not None else 0

    def insert_ipact_renewal_commitment(
        self,
        device_id: str,
        token_id: int,
        epoch_index: int,
        prev_commitment: bytes,
        reattest_proof: bytes,
        commitment: bytes,
        ts_ns: int,
        enforced: bool = False,
    ) -> int:
        """Persist one renewal-cadence commitment link (Phase B ③).

        UNIQUE(device_id, epoch_index) enforces anti-replay at the DB layer.
        Stores 32-byte values as hex.
        """
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO ipact_renewal_commitments
                   (device_id, token_id, epoch_index, prev_commitment, reattest_proof,
                    commitment, ts_ns, enforced, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    device_id, int(token_id), int(epoch_index),
                    prev_commitment.hex(), reattest_proof.hex(), commitment.hex(),
                    int(ts_ns), int(bool(enforced)), __import__("time").time(),
                ),
            )
            return cur.lastrowid

    def get_ipact_renewal_chain(self, device_id: str) -> list[dict]:
        """Return a device's renewal links ordered by epoch_index ASC for verify_chain().

        Each dict: epoch_index (int), reattest_proof (bytes), ts_ns (int),
        commitment (bytes) — the exact shape ipact_renewal.verify_chain() consumes.
        """
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT epoch_index, reattest_proof, ts_ns, commitment "
                "FROM ipact_renewal_commitments WHERE device_id = ? "
                "ORDER BY epoch_index ASC",
                (device_id,),
            ).fetchall()
        return [
            {
                "epoch_index": int(r[0]),
                "reattest_proof": bytes.fromhex(r[1]),
                "ts_ns": int(r[2]),
                "commitment": bytes.fromhex(r[3]),
            }
            for r in rows
        ]

    def insert_gsr_hmac_validation(
        self,
        *,
        device_id: str,
        frame_size: int,
        valid: bool,
        rejection_reason: str = "",
        ts_ns: int = 0,
    ) -> int:
        """Log a GSR HMAC frame validation attempt (Phase 158 WIF-014)."""
        with self._conn() as con:
            cur = con.execute(
                "INSERT INTO gsr_hmac_validation_log "
                "(device_id, frame_size, valid, rejection_reason, ts_ns, created_at)"
                " VALUES (?,?,?,?,?,?)",
                (device_id, int(frame_size), int(valid), rejection_reason, int(ts_ns), time.time()),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_gsr_hmac_validation_status(self, limit: int = 20) -> dict:
        """Return HMAC validation summary + recent entries (Phase 158)."""
        with self._conn() as con:
            total = con.execute(
                "SELECT COUNT(*) FROM gsr_hmac_validation_log"
            ).fetchone()[0]
            valid_count = con.execute(
                "SELECT COUNT(*) FROM gsr_hmac_validation_log WHERE valid=1"
            ).fetchone()[0]
            rows = con.execute(
                "SELECT * FROM gsr_hmac_validation_log ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return {
            "gsr_hmac_enabled": False,  # populated by operator_api from cfg
            "total_validations": total,
            "valid_count": valid_count,
            "rejected_count": total - valid_count,
            "recent_entries": [dict(r) for r in rows],
        }

    def insert_biometric_renewal_chain_log(
        self,
        prev_commit_hash: str,
        new_commit_hash: str,
        n_consented: int,
        n_sessions: int,
        ttl_days: float,
        on_chain_tx: "str | None" = None,
        dry_run: bool = True,
        renewal_reason: str = "TTL_EXPIRY",
    ) -> int:
        """Insert a biometric renewal chain record (Phase 180).

        Stores the consent-bound renewal commitment chain entry.
        new_commit_hash = SHA-256(prev_hash + ratio_str + N + N_consented + players + ttl_days + ts_ns).
        Raises sqlite3.IntegrityError on duplicate new_commit_hash (anti-replay).
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO biometric_renewal_chain_log "
                "(prev_commit_hash, new_commit_hash, renewal_reason, "
                "n_consented, n_sessions, ttl_days, on_chain_tx, dry_run, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    str(prev_commit_hash),
                    str(new_commit_hash),
                    str(renewal_reason),
                    int(n_consented),
                    int(n_sessions),
                    float(ttl_days),
                    str(on_chain_tx) if on_chain_tx else None,
                    1 if dry_run else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_biometric_renewal_chain_status(self) -> "dict":
        """Return the renewal chain status for GET /agent/renewal-chain-status (Phase 180).

        Returns 7 keys: renewal_enabled/total_renewals/latest_renewal_ts/
        prev_commit_hash/new_commit_hash/ttl_days/timestamp.
        """
        ts_now = time.time()
        with self._conn() as conn:
            total_row = conn.execute(
                "SELECT COUNT(*) FROM biometric_renewal_chain_log"
            ).fetchone()
            total_renewals = int(total_row[0]) if total_row else 0
            latest_row = conn.execute(
                "SELECT prev_commit_hash, new_commit_hash, ttl_days, created_at "
                "FROM biometric_renewal_chain_log ORDER BY id DESC LIMIT 1"
            ).fetchone()
        if latest_row:
            return {
                "renewal_enabled":    False,      # caller overlays from cfg
                "total_renewals":     total_renewals,
                "latest_renewal_ts":  float(latest_row[3]),
                "prev_commit_hash":   str(latest_row[0]),
                "new_commit_hash":    str(latest_row[1]),
                "ttl_days":           float(latest_row[2]),
                "timestamp":          ts_now,
            }
        return {
            "renewal_enabled":    False,
            "total_renewals":     0,
            "latest_renewal_ts":  0.0,
            "prev_commit_hash":   "",
            "new_commit_hash":    "",
            "ttl_days":           90.0,
            "timestamp":          ts_now,
        }

    def insert_biometric_renewal_log(
        self,
        commit_hash: str,
        age_days: float,
        ttl_days: float,
        ttl_expired: bool,
        recalibration_required: bool,
        checked_by: str = "tournament_activation_chain_agent",
    ) -> int:
        """Insert a biometric credential TTL check record (Phase 178).

        Called by TournamentActivationChainAgent each time it evaluates whether the
        latest SeparationRatioRegistry.sol commitment has expired.
        ttl_expired=True blocks tournament authorization and sets recalibration_required=True.
        """
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO biometric_renewal_log "
                "(commit_hash, age_days, ttl_days, ttl_expired, "
                "recalibration_required, checked_by, created_at) "
                "VALUES (?,?,?,?,?,?,?)",
                (
                    str(commit_hash),
                    float(age_days),
                    float(ttl_days),
                    1 if ttl_expired else 0,
                    1 if recalibration_required else 0,
                    str(checked_by),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_biometric_credential_age_status(self, ttl_days: float = 90.0) -> "dict":
        """Return the current biometric credential age and TTL status (Phase 178).

        Computes age_days live from the most recent separation_ratio_registry_log commit
        and compares against ttl_days (default 90, overridden by cfg.biometric_credential_ttl_days).
        ttl_expired=True is computed HERE — the biometric_renewal_log is an audit trail only,
        not the authority on current expiry state.

        Returns a dict with 8 keys: ttl_enabled/commit_hash/commit_ts/age_days/
        ttl_days/ttl_expired/recalibration_required/timestamp.
        """
        import time as _time

        ts_now = _time.time()
        # Get latest on-chain commit timestamp from separation_ratio_registry_log
        with self._conn() as conn:
            reg_row = conn.execute(
                "SELECT commit_hash, created_at FROM separation_ratio_registry_log "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()

        if reg_row is not None:
            commit_hash = str(reg_row[0])
            commit_ts = float(reg_row[1])
            age_days = (ts_now - commit_ts) / 86400.0
        else:
            commit_hash = ""
            commit_ts = 0.0
            age_days = 0.0

        # Compute expiry live: only expired when a commit exists AND age exceeds TTL
        ttl_expired = bool(commit_hash) and (age_days > float(ttl_days))
        recalibration_required = ttl_expired

        return {
            "ttl_enabled":             True,
            "commit_hash":             commit_hash,
            "commit_ts":               commit_ts,
            "age_days":                round(age_days, 4),
            "ttl_days":                float(ttl_days),
            "ttl_expired":             ttl_expired,
            "recalibration_required":  recalibration_required,
            "timestamp":               ts_now,
        }

    def insert_biometric_stationarity_log(
        self,
        player_id: str,
        p_genuine_drift: float,
        p_adversarial_window: float,
        stationarity_verdict: str,
        chain_integrity_score: float,
        trend_velocity: float,
        temporal_drift_index: float,
        session_count_used: int,
    ) -> int:
        """Insert a biometric stationarity assessment (Phase 188)."""
        confidence = max(p_genuine_drift, p_adversarial_window)
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO biometric_stationarity_log "
                "(player_id, p_genuine_drift, p_adversarial_window, stationarity_verdict, "
                "biometric_stationarity_confidence, chain_integrity_score, trend_velocity, "
                "temporal_drift_index, session_count_used, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    player_id,
                    float(p_genuine_drift),
                    float(p_adversarial_window),
                    stationarity_verdict,
                    float(confidence),
                    float(chain_integrity_score),
                    float(trend_velocity),
                    float(temporal_drift_index),
                    int(session_count_used),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_biometric_stationarity_status(self, player_id: "str | None" = None) -> "dict | None":
        """Return latest biometric stationarity assessment (Phase 188)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, p_genuine_drift, p_adversarial_window, "
                        "stationarity_verdict, biometric_stationarity_confidence, "
                        "chain_integrity_score, trend_velocity, temporal_drift_index, "
                        "session_count_used, created_at "
                        "FROM biometric_stationarity_log WHERE player_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, p_genuine_drift, p_adversarial_window, "
                        "stationarity_verdict, biometric_stationarity_confidence, "
                        "chain_integrity_score, trend_velocity, temporal_drift_index, "
                        "session_count_used, created_at "
                        "FROM biometric_stationarity_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                total_adversarial = conn.execute(
                    "SELECT COUNT(*) FROM biometric_stationarity_log "
                    "WHERE stationarity_verdict='ADVERSARIAL_WINDOW'"
                ).fetchone()[0]
        except Exception:
            return None
        if row is None:
            return {
                "player_id": player_id or "",
                "p_genuine_drift": 0.0,
                "p_adversarial_window": 0.0,
                "stationarity_verdict": "STABLE",
                "biometric_stationarity_confidence": 0.5,
                "chain_integrity_score": 1.0,
                "trend_velocity": 0.0,
                "temporal_drift_index": 0.0,
                "session_count_used": 0,
                "total_adversarial_alerts": 0,
                "created_at": 0.0,
            }
        return {
            "player_id":                        row[0],
            "p_genuine_drift":                  float(row[1]),
            "p_adversarial_window":             float(row[2]),
            "stationarity_verdict":             row[3],
            "biometric_stationarity_confidence": float(row[4]),
            "chain_integrity_score":            float(row[5]),
            "trend_velocity":                   float(row[6]),
            "temporal_drift_index":             float(row[7]),
            "session_count_used":               int(row[8]),
            "total_adversarial_alerts":         int(total_adversarial),
            "created_at":                       float(row[9]),
        }

    def insert_attestation_opsec_log(
        self,
        player_id: str,
        timing_disclosure_risk: str,
        active_attestations: int,
        re_enrollment_window_active: bool,
        recommendation: str,
    ) -> int:
        """Insert an attestation OpSec advisory record (Phase 187)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO attestation_opsec_log "
                "(player_id, timing_disclosure_risk, active_attestations, "
                "re_enrollment_window_active, recommendation, created_at) "
                "VALUES (?,?,?,?,?,?)",
                (
                    player_id,
                    timing_disclosure_risk,
                    int(active_attestations),
                    1 if re_enrollment_window_active else 0,
                    recommendation,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_attestation_opsec_status(self, player_id: "str | None" = None) -> dict:
        """Return latest attestation OpSec advisory status (Phase 187)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, timing_disclosure_risk, active_attestations, "
                        "re_enrollment_window_active, recommendation, created_at "
                        "FROM attestation_opsec_log WHERE player_id=? ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, timing_disclosure_risk, active_attestations, "
                        "re_enrollment_window_active, recommendation, created_at "
                        "FROM attestation_opsec_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                total_high = conn.execute(
                    "SELECT COUNT(*) FROM attestation_opsec_log WHERE timing_disclosure_risk='HIGH'"
                ).fetchone()[0]
        except Exception:
            return {
                "player_id": player_id or "",
                "timing_disclosure_risk": "LOW",
                "active_attestations": 0,
                "re_enrollment_window_active": False,
                "recommendation": "STANDARD_TX_OK",
                "total_high_risk_events": 0,
                "created_at": 0.0,
            }
        if row is None:
            return {
                "player_id": player_id or "",
                "timing_disclosure_risk": "LOW",
                "active_attestations": 0,
                "re_enrollment_window_active": False,
                "recommendation": "STANDARD_TX_OK",
                "total_high_risk_events": int(total_high),
                "created_at": 0.0,
            }
        return {
            "player_id":                  row[0],
            "timing_disclosure_risk":     row[1],
            "active_attestations":        int(row[2]),
            "re_enrollment_window_active": bool(row[3]),
            "recommendation":             row[4],
            "total_high_risk_events":     int(total_high),
            "created_at":                 float(row[5]),
        }

    def insert_attestation_bound_renewal_log(
        self,
        player_id: str,
        attestation_hash: str,
        renewal_approved: bool,
        denial_reason: str,
        new_commit_hash: str,
    ) -> int:
        """Insert an attestation-bound renewal validation record (Phase 186)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO attestation_bound_renewal_log "
                "(player_id, attestation_hash, renewal_approved, denial_reason, "
                "new_commit_hash, created_at) VALUES (?,?,?,?,?,?)",
                (
                    player_id,
                    attestation_hash,
                    1 if renewal_approved else 0,
                    denial_reason,
                    new_commit_hash,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_attestation_bound_renewal_status(self, player_id: "str | None" = None) -> dict:
        """Return attestation-bound renewal status (Phase 186)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, renewal_approved, denial_reason, "
                        "new_commit_hash, created_at "
                        "FROM attestation_bound_renewal_log WHERE player_id=? "
                        "ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, renewal_approved, denial_reason, "
                        "new_commit_hash, created_at "
                        "FROM attestation_bound_renewal_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                total_blocked = conn.execute(
                    "SELECT COUNT(*) FROM attestation_bound_renewal_log WHERE renewal_approved=0"
                ).fetchone()[0]
                total_approved = conn.execute(
                    "SELECT COUNT(*) FROM attestation_bound_renewal_log WHERE renewal_approved=1"
                ).fetchone()[0]
        except Exception:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "renewal_approved": False,
                "denial_reason": "",
                "total_blocked": 0,
                "total_approved": 0,
            }
        if row is None:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "renewal_approved": False,
                "denial_reason": "",
                "total_blocked": int(total_blocked),
                "total_approved": int(total_approved),
            }
        return {
            "player_id":        row[0],
            "attestation_hash": row[1],
            "renewal_approved": bool(row[2]),
            "denial_reason":    row[3],
            "total_blocked":    int(total_blocked),
            "total_approved":   int(total_approved),
        }

    def insert_persona_break_attestation(
        self,
        player_id: str,
        hash: str,
        loo_trend: float,
        tdi: float,
        ttl_days: float,
        issued_at: float,
        expires_at: float,
    ) -> int:
        """Insert a persona break attestation token (Phase 185)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO persona_break_attestation_log "
                "(player_id, attestation_hash, active, issued_at, expires_at, "
                "loo_trend_at_break, tdi_at_break, ttl_days, created_at) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    player_id,
                    hash,
                    1,
                    float(issued_at),
                    float(expires_at),
                    float(loo_trend),
                    float(tdi),
                    float(ttl_days),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_active_attestation(self, player_id: str) -> dict:
        """Return latest active attestation for a player (Phase 185).

        Returns safe dict with active=False when no active row found.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT player_id, attestation_hash, active, issued_at, expires_at, "
                    "loo_trend_at_break, tdi_at_break, ttl_days, created_at "
                    "FROM persona_break_attestation_log "
                    "WHERE player_id=? AND active=1 ORDER BY id DESC LIMIT 1",
                    (player_id,),
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "player_id": player_id,
                "attestation_hash": "",
                "active": False,
                "issued_at": 0.0,
                "expires_at": 0.0,
                "loo_trend_at_break": 0.0,
                "tdi_at_break": 0.0,
                "ttl_days": 7.0,
            }
        return {
            "player_id":        row[0],
            "attestation_hash": row[1],
            "active":           bool(row[2]),
            "issued_at":        float(row[3]),
            "expires_at":       float(row[4]),
            "loo_trend_at_break": float(row[5]),
            "tdi_at_break":     float(row[6]),
            "ttl_days":         float(row[7]),
        }

    def expire_stale_attestations(self) -> int:
        """Set active=0 for all attestations past their expires_at (Phase 185).

        Returns count of rows deactivated.
        """
        now = time.time()
        with self._conn() as conn:
            cur = conn.execute(
                "UPDATE persona_break_attestation_log SET active=0 "
                "WHERE active=1 AND expires_at <= ?",
                (now,),
            )
        return cur.rowcount

    def insert_maturity_elevation_log(
        self,
        current_tier: str,
        target_tier: str,
        gap_to_target: float,
        elevation_plan_json: str,
        elevation_available: bool,
        critical_component: str,
        estimated_sessions_total: int,
    ) -> int:
        """Insert a maturity elevation assessment (Phase 183)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO maturity_elevation_log "
                "(current_tier, target_tier, gap_to_target, elevation_plan_json, "
                "elevation_available, critical_component, estimated_sessions_total, created_at) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (
                    current_tier,
                    target_tier,
                    float(gap_to_target),
                    elevation_plan_json,
                    1 if elevation_available else 0,
                    critical_component,
                    int(estimated_sessions_total),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_maturity_elevation_status(self) -> dict:
        """Return latest maturity elevation status (Phase 183)."""
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT current_tier, target_tier, gap_to_target, elevation_plan_json, "
                    "elevation_available, critical_component, estimated_sessions_total, created_at "
                    "FROM maturity_elevation_log ORDER BY id DESC LIMIT 1"
                ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "current_tier": "ALPHA",
                "target_tier": "BETA",
                "gap_to_target": 1.0,
                "elevation_plan_json": "{}",
                "elevation_available": False,
                "critical_component": "",
                "estimated_sessions_total": 0,
                "created_at": 0.0,
            }
        return {
            "current_tier":            row[0],
            "target_tier":             row[1],
            "gap_to_target":           float(row[2]),
            "elevation_plan_json":     row[3],
            "elevation_available":     bool(row[4]),
            "critical_component":      row[5],
            "estimated_sessions_total": int(row[6]),
            "created_at":              float(row[7]),
        }

    def insert_persona_break_log(
        self,
        player_id: str,
        loo_accuracy_trend: float,
        tdi_current: float,
        persona_break_detected: bool,
        urgency: str,
        n_snapshots: int,
    ) -> int:
        """Insert a persona break detection record (Phase 182)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO persona_break_log "
                "(player_id, loo_accuracy_trend, tdi_current, persona_break_detected, "
                "re_enrollment_urgency, n_snapshots_used, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    player_id,
                    float(loo_accuracy_trend),
                    float(tdi_current),
                    1 if persona_break_detected else 0,
                    urgency,
                    int(n_snapshots),
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_persona_break_status(self, player_id: "str | None" = None) -> dict:
        """Return latest persona break status (Phase 182).

        Returns safe defaults when no data exists.
        """
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, loo_accuracy_trend, tdi_current, "
                        "persona_break_detected, re_enrollment_urgency, n_snapshots_used, created_at "
                        "FROM persona_break_log WHERE player_id=? ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT player_id, loo_accuracy_trend, tdi_current, "
                        "persona_break_detected, re_enrollment_urgency, n_snapshots_used, created_at "
                        "FROM persona_break_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
        except Exception:
            row = None
        if row is None:
            return {
                "player_id":              player_id or "",
                "loo_accuracy_trend":     1.0,
                "tdi_current":            0.0,
                "persona_break_detected": False,
                "re_enrollment_urgency":  "MEDIUM",
                "n_snapshots_used":       0,
                "created_at":             0.0,
            }
        return {
            "player_id":              row[0],
            "loo_accuracy_trend":     float(row[1]),
            "tdi_current":            float(row[2]),
            "persona_break_detected": bool(row[3]),
            "re_enrollment_urgency":  row[4],
            "n_snapshots_used":       int(row[5]),
            "created_at":             float(row[6]),
        }

    def insert_renewal_consent_snapshot(
        self,
        new_commit_hash: str,
        n_consented: int,
        players_json: str,
        revoked: int,
        delta: bool,
    ) -> int:
        """Insert a renewal consent snapshot linked by new_commit_hash (Phase 181)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO renewal_consent_snapshot_log "
                "(new_commit_hash, n_consented_at_renewal, players_consented_json, "
                "revoked_at_renewal, corpus_delta_detected, created_at) VALUES (?,?,?,?,?,?)",
                (
                    new_commit_hash,
                    int(n_consented),
                    players_json,
                    int(revoked),
                    1 if delta else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_renewal_consent_snapshot(self, new_commit_hash: str) -> "dict | None":
        """Return renewal consent snapshot for a given commit hash (Phase 181).

        Returns None when hash not found.
        """
        try:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT new_commit_hash, n_consented_at_renewal, players_consented_json, "
                    "revoked_at_renewal, corpus_delta_detected, created_at "
                    "FROM renewal_consent_snapshot_log WHERE new_commit_hash=?",
                    (new_commit_hash,),
                ).fetchone()
        except Exception:
            return None
        if row is None:
            return None
        return {
            "new_commit_hash":        row[0],
            "n_consented_at_renewal": int(row[1]),
            "players_consented_json": row[2],
            "revoked_at_renewal":     int(row[3]),
            "corpus_delta_detected":  int(row[4]),
            "created_at":             float(row[5]),
        }

    def insert_biometric_snapshot(
        self,
        snapshot_commitment: str,
        feature_dim: int,
        sorted_player_ids: list,
        centroids_by_player: dict,
        cov_inv: list,
        ts_ns: int,
        ait_session_log_id: int = 0,
        trigger_reason: str = "",
        on_chain_confirmed: bool = False,
        tx_hash: str = "",
    ) -> int:
        """Insert one BIOMETRIC-SNAPSHOT-v1 row.  Returns row id.

        UNIQUE(snapshot_commitment) enforces idempotency: re-inserting the
        same commitment returns the existing row id (matching corpus_snapshot_log
        precedent at Phase 237.5).
        """
        import json as _j237s
        try:
            with self._conn() as conn:
                cur = conn.execute(
                    "INSERT INTO biometric_snapshot_log "
                    "(snapshot_commitment, feature_dim, n_players, sorted_player_ids, "
                    " centroids_json, cov_inv_json, ts_ns, on_chain_confirmed, tx_hash, "
                    " trigger_reason, ait_session_log_id, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        str(snapshot_commitment),
                        int(feature_dim),
                        int(len(sorted_player_ids)),
                        _j237s.dumps([int(x) for x in sorted_player_ids]),
                        _j237s.dumps(centroids_by_player),
                        _j237s.dumps(cov_inv),
                        int(ts_ns),
                        1 if on_chain_confirmed else 0,
                        str(tx_hash),
                        str(trigger_reason)[:128],
                        int(ait_session_log_id),
                        time.time(),
                    ),
                )
                return int(cur.lastrowid)
        except Exception:
            with self._conn() as conn:
                row = conn.execute(
                    "SELECT id FROM biometric_snapshot_log WHERE snapshot_commitment = ?",
                    (str(snapshot_commitment),),
                ).fetchone()
            return int(row["id"]) if row else 0

    def get_latest_biometric_snapshot(self) -> dict:
        """Return the most recent biometric snapshot or empty dict.

        Returned keys (when present): snapshot_commitment, feature_dim,
        n_players, sorted_player_ids, centroids_by_player, cov_inv, ts_ns,
        on_chain_confirmed, tx_hash, trigger_reason, ait_session_log_id.
        """
        import json as _j237g
        with self._conn() as conn:
            row = conn.execute(
                "SELECT snapshot_commitment, feature_dim, n_players, sorted_player_ids, "
                "       centroids_json, cov_inv_json, ts_ns, on_chain_confirmed, tx_hash, "
                "       trigger_reason, ait_session_log_id "
                "FROM biometric_snapshot_log ORDER BY ts_ns DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return {}
        # Defensive JSON parsing
        try:
            sids = _j237g.loads(row["sorted_player_ids"]) or []
        except Exception:
            sids = []
        try:
            cents = _j237g.loads(row["centroids_json"]) or {}
            # JSON keys are always strings — coerce back to int
            cents = {int(k): list(v) for k, v in cents.items()}
        except Exception:
            cents = {}
        try:
            cov = _j237g.loads(row["cov_inv_json"]) or []
        except Exception:
            cov = []
        return {
            "snapshot_commitment":  str(row["snapshot_commitment"]),
            "feature_dim":          int(row["feature_dim"]),
            "n_players":            int(row["n_players"]),
            "sorted_player_ids":    sids,
            "centroids_by_player":  cents,
            "cov_inv":              cov,
            "ts_ns":                int(row["ts_ns"]),
            "on_chain_confirmed":   bool(row["on_chain_confirmed"]),
            "tx_hash":              str(row["tx_hash"]),
            "trigger_reason":       str(row["trigger_reason"]),
            "ait_session_log_id":   int(row["ait_session_log_id"]),
        }

    def get_biometric_snapshot_status(self) -> dict:
        """Return summary of biometric_snapshot_log: total + latest.

        Mirrors get_corpus_snapshot_status shape so the operator endpoint
        can return both with consistent keys.
        """
        import time as _t237gs
        with self._conn() as conn:
            total = (conn.execute(
                "SELECT COUNT(*) FROM biometric_snapshot_log"
            ).fetchone() or (0,))[0]
        latest = self.get_latest_biometric_snapshot()
        return {
            "total_snapshots":     int(total),
            "latest_commitment":   latest.get("snapshot_commitment", ""),
            "feature_dim":         latest.get("feature_dim", 0),
            "n_players":           latest.get("n_players", 0),
            "ts_ns":               latest.get("ts_ns", 0),
            "on_chain_confirmed":  latest.get("on_chain_confirmed", False),
            "tx_hash":             latest.get("tx_hash", ""),
            "trigger_reason":      latest.get("trigger_reason", ""),
            "timestamp":           _t237gs.time(),
        }
