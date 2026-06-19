"""VhpMixin — D-DECON-2 vhp_credentials domain extraction.

Extracted verbatim from store/_core.py via the diff-oracle pattern.
_init_schema (CREATE TABLE anchors) and ioid_devices helpers STAY in _core.
"""
from __future__ import annotations

import json
import time


class VhpMixin:
    """VHP / PHG credential / enrollment / enforcement methods; resolved via MRO."""
    def get_last_phg_checkpoint(self, device_id: str) -> dict | None:
        """Return the most recently *confirmed* PHG checkpoint for a device, or None.

        Phase 25: filters to confirmed=1 only so unconfirmed checkpoints are never
        used as the cumulative-score delta baseline.
        """
        with self._conn() as conn:
            row = conn.execute("""
                SELECT * FROM phg_checkpoints
                WHERE device_id = ? AND confirmed = 1
                ORDER BY id DESC
                LIMIT 1
            """, (device_id,)).fetchone()
            return dict(row) if row else None

    def store_phg_checkpoint(
        self,
        device_id: str,
        phg_score: int,
        record_count: int,
        bio_hash_hex: str,
        tx_hash: str,
        cumulative_score: int = 0,
        confirmed: bool = False,
    ):
        """Persist a committed PHG checkpoint for dashboard display.

        cumulative_score is the true cumulative PHG score at the time of commit.
        It is written to last_committed_score so that future delta calculations
        read the correct cumulative baseline (not the previous delta).
        confirmed=True when the transaction receipt status==1 was observed.
        """
        with self._conn() as conn:
            conn.execute("""
                INSERT OR IGNORE INTO phg_checkpoints
                    (device_id, phg_score, record_count, bio_hash, tx_hash, committed_at,
                     last_committed_score, confirmed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (device_id, phg_score, record_count, bio_hash_hex, tx_hash, time.time(),
                  cumulative_score, int(confirmed)))

    def get_phg_checkpoints(self, device_id: str, limit: int = 20) -> list[dict]:
        """Return the most recent PHG checkpoints for a device."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM phg_checkpoints
                WHERE device_id = ?
                ORDER BY committed_at DESC
                LIMIT ?
            """, (device_id, limit)).fetchall()
            return [dict(r) for r in rows]

    def mark_checkpoint_confirmed(self, tx_hash: str) -> None:
        """Mark a PHG checkpoint as confirmed by on-chain event (Phase 25)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE phg_checkpoints SET confirmed = 1 WHERE tx_hash = ?",
                (tx_hash,),
            )

    def get_unconfirmed_checkpoints(self, age_s: float = 300.0) -> list[dict]:
        """Return PHG checkpoints that are older than age_s seconds and still unconfirmed (Phase 25)."""
        cutoff = time.time() - age_s
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT * FROM phg_checkpoints
                WHERE confirmed = 0 AND committed_at < ?
                ORDER BY committed_at ASC
            """, (cutoff,)).fetchall()
            return [dict(r) for r in rows]

    def store_credential_mint(
        self, device_id: str, credential_id: int, tx_hash: str
    ) -> None:
        """Record a successfully minted PHGCredential. INSERT OR IGNORE (idempotent)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO phg_credential_mints "
                "(device_id, credential_id, tx_hash, minted_at) VALUES (?,?,?,?)",
                (device_id, credential_id, tx_hash, time.time()),
            )

    def get_credential_mint(self, device_id: str) -> dict | None:
        """Return credential mint record for device, or None if not minted (Phase 28)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT device_id, credential_id, tx_hash, minted_at "
                "FROM phg_credential_mints WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def upsert_enrollment(
        self,
        device_id: str,
        sessions_nominal: int,
        sessions_total: int,
        avg_humanity: float,
        status: str,
        tx_hash: str = "",
    ) -> None:
        """Insert or update enrollment progress for a device. Idempotent."""
        now = time.time()
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO device_enrollments
                    (device_id, sessions_nominal, sessions_total, avg_humanity,
                     status, tx_hash, last_updated)
                VALUES (?,?,?,?,?,?,?)
                ON CONFLICT(device_id) DO UPDATE SET
                    sessions_nominal=excluded.sessions_nominal,
                    sessions_total=excluded.sessions_total,
                    avg_humanity=excluded.avg_humanity,
                    status=excluded.status,
                    tx_hash=excluded.tx_hash,
                    eligible_at=CASE WHEN excluded.status='eligible' AND status!='eligible'
                                     THEN ? ELSE eligible_at END,
                    credentialed_at=CASE WHEN excluded.status='credentialed'
                                         THEN ? ELSE credentialed_at END,
                    last_updated=?
            """, (device_id, sessions_nominal, sessions_total, avg_humanity,
                  status, tx_hash, now, now, now, now))

    def get_enrollment(self, device_id: str) -> dict | None:
        """Return enrollment row for device, or None if no row exists."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM device_enrollments WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def get_eligible_unenrolled(self) -> list[dict]:
        """Devices that are eligible but not yet credentialed."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM device_enrollments WHERE status='eligible' "
                "ORDER BY eligible_at"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_leaderboard(self, limit: int = 20) -> list[dict]:
        """Return top devices by confirmed cumulative PHG score (Phase 28)."""
        with self._conn() as conn:
            rows = conn.execute("""
                SELECT device_id, MAX(last_committed_score) AS cumulative_score,
                       MAX(record_count) AS record_count
                FROM phg_checkpoints WHERE confirmed = 1
                GROUP BY device_id
                ORDER BY cumulative_score DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def set_device_risk_label(self, device_id: str, risk_label: str,
                               label_evidence: dict, prior_label: str = "") -> None:
        """Upsert a per-device risk trajectory label (Phase 35)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO device_risk_labels"
                " (device_id, risk_label, label_evidence, label_set_at, prior_label)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   risk_label=excluded.risk_label,"
                "   label_evidence=excluded.label_evidence,"
                "   label_set_at=excluded.label_set_at,"
                "   prior_label=excluded.prior_label",
                (device_id, risk_label, json.dumps(label_evidence), time.time(), prior_label),
            )

    def get_device_risk_label(self, device_id: str) -> dict | None:
        """Return the risk trajectory label for a device (Phase 35)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM device_risk_labels WHERE device_id=?", (device_id,)
            ).fetchone()
        if not row:
            return None
        d = dict(row)
        d["label_evidence"] = json.loads(d.get("label_evidence", "{}"))
        return d

    def get_devices_by_risk_label(self, risk_label: str) -> list:
        """Return all devices with the specified risk_label (Phase 35)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM device_risk_labels WHERE risk_label=?"
                " ORDER BY label_set_at DESC",
                (risk_label,),
            ).fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["label_evidence"] = json.loads(d.get("label_evidence", "{}"))
            result.append(d)
        return result

    def store_detection_policy(self, device_id: str, multiplier: float,
                                basis_label: str, expires_at: float) -> None:
        """Upsert an adaptive PITL threshold multiplier for a device (Phase 36)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO detection_policies"
                " (device_id, multiplier, basis_label, set_at, expires_at)"
                " VALUES (?, ?, ?, ?, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   multiplier=excluded.multiplier, basis_label=excluded.basis_label,"
                "   set_at=excluded.set_at, expires_at=excluded.expires_at",
                (device_id, multiplier, basis_label, time.time(), expires_at),
            )

    def get_detection_policy(self, device_id: str) -> dict | None:
        """Return active detection policy for device, or None if none/expired (Phase 36)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM detection_policies WHERE device_id=? AND expires_at > ?",
                (device_id, time.time()),
            ).fetchone()
        return dict(row) if row else None

    def get_all_active_policies(self) -> list:
        """Return all non-expired detection policies ordered by set_at DESC (Phase 36)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM detection_policies WHERE expires_at > ?"
                " ORDER BY set_at DESC",
                (time.time(),),
            ).fetchall()
        return [dict(r) for r in rows]

    def clear_detection_policy(self, device_id: str) -> None:
        """Remove detection policy for a device (Phase 36)."""
        with self._conn() as conn:
            conn.execute(
                "DELETE FROM detection_policies WHERE device_id=?", (device_id,)
            )

    def get_credential_enforcement(self, device_id: str) -> dict | None:
        """Return credential enforcement row for a device, or None (Phase 37)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM credential_enforcement WHERE device_id=?", (device_id,)
            ).fetchone()
        return dict(row) if row else None

    def increment_consecutive_critical(self, device_id: str) -> int:
        """Increment consecutive_critical counter for a device; return new count (Phase 37)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement (device_id, consecutive_critical, last_updated)"
                " VALUES (?, 1, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   consecutive_critical = consecutive_critical + 1,"
                "   last_updated = excluded.last_updated",
                (device_id, time.time()),
            )
            row = conn.execute(
                "SELECT consecutive_critical FROM credential_enforcement WHERE device_id=?",
                (device_id,),
            ).fetchone()
        return int(row[0]) if row else 1

    def reset_consecutive_critical(self, device_id: str) -> None:
        """Reset consecutive_critical to 0 for a device (Phase 37)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement (device_id, consecutive_critical, last_updated)"
                " VALUES (?, 0, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   consecutive_critical = 0, last_updated = excluded.last_updated",
                (device_id, time.time()),
            )

    def store_credential_suspension(self, device_id: str,
                                     evidence_hash: str, until: float) -> None:
        """Record a credential suspension in the DB (Phase 37)."""
        now = time.time()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement"
                " (device_id, consecutive_critical, suspended, suspended_since,"
                "  suspended_until, evidence_hash, last_updated)"
                " VALUES (?, 0, 1, ?, ?, ?, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   suspended=1, suspended_since=excluded.suspended_since,"
                "   suspended_until=excluded.suspended_until,"
                "   evidence_hash=excluded.evidence_hash,"
                "   last_updated=excluded.last_updated",
                (device_id, now, until, evidence_hash, now),
            )

    def is_credential_suspended(self, device_id: str) -> bool:
        """Return True if device has an active credential suspension (Phase 37)."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT suspended FROM credential_enforcement WHERE device_id=?",
                (device_id,),
            ).fetchone()
        return bool(row[0]) if row else False

    def clear_credential_suspension(self, device_id: str) -> None:
        """Clear suspension state for a device (Phase 37)."""
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO credential_enforcement"
                " (device_id, consecutive_critical, suspended, last_updated)"
                " VALUES (?, 0, 0, ?)"
                " ON CONFLICT(device_id) DO UPDATE SET"
                "   suspended=0, suspended_since=NULL, suspended_until=NULL,"
                "   evidence_hash=NULL, last_updated=excluded.last_updated",
                (device_id, time.time()),
            )

    def get_all_suspended_credentials(self) -> list:
        """Return all currently suspended credential enforcement rows (Phase 37)."""
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM credential_enforcement WHERE suspended=1"
                " ORDER BY suspended_since DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def get_expired_suspensions(self) -> list[dict]:
        """Return suspended rows whose suspension window has elapsed (Phase 67).

        Used by RulingEnforcementAgent._check_expired_suspensions() to auto-reinstate.
        Only returns rows where suspended=1, suspended_until < now(), reinstated is falsy.
        """
        now = time.time()
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM credential_enforcement"
                " WHERE suspended=1 AND suspended_until IS NOT NULL AND suspended_until < ?"
                " AND (reinstated IS NULL OR reinstated=0)",
                (now,),
            ).fetchall()
        return [dict(r) for r in rows]

    def mark_suspension_reinstated(self, device_id: str) -> None:
        """Mark a device's credential suspension as reinstated (Phase 67)."""
        with self._conn() as conn:
            conn.execute(
                "UPDATE credential_enforcement SET reinstated=1, reinstated_at=? WHERE device_id=?",
                (time.time(), device_id),
            )

    def get_device_suspension(self, device_id: str) -> dict | None:
        """Return active suspension state for device from credential_enforcement, or None."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM credential_enforcement WHERE device_id=? "
                "AND suspended=1 AND (reinstated IS NULL OR reinstated=0) "
                "ORDER BY last_updated DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def insert_vhp_issuance(
        self,
        device_id: str,
        token_id: int = 0,
        tx_hash: str = "",
        expires_at: float = 0.0,
        cert_level: int = 1,
        consecutive_clean: int = 0,
        to_address: str = "",
    ) -> int:
        """Persist a VHP token issuance record. Returns row id."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO vhp_issuances "
                "(device_id, token_id, tx_hash, expires_at, cert_level, consecutive_clean, to_address) "
                "VALUES (?,?,?,?,?,?,?)",
                (device_id, token_id, tx_hash, expires_at, cert_level, consecutive_clean, to_address),
            )
            return cur.lastrowid

    def get_vhp_status(self, device_id: str) -> dict | None:
        """Return the latest VHP issuance for a device, or None if none found."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM vhp_issuances WHERE device_id=? ORDER BY created_at DESC LIMIT 1",
                (device_id,),
            ).fetchone()
        return dict(row) if row else None

    def insert_vhp_renewal(
        self,
        device_id: str,
        token_id: int,
        old_expires_at: float,
        new_expires_at: float,
        tx_hash: str = "",
        dry_run: bool = False,
    ) -> int:
        """Persist a VHP renewal record (Phase 102)."""
        with self._conn() as conn:
            cur = conn.execute(
                """INSERT INTO vhp_renewal_log
                   (device_id, token_id, old_expires_at, new_expires_at,
                    tx_hash, dry_run)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (device_id, token_id, old_expires_at, new_expires_at,
                 tx_hash, int(dry_run)),
            )
            return cur.lastrowid

    def get_vhp_renewal_log(
        self, device_id: str | None = None, limit: int = 20
    ) -> list[dict]:
        """Return renewal log entries, optionally filtered by device_id (Phase 102)."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    """SELECT id, device_id, token_id, old_expires_at,
                              new_expires_at, tx_hash, dry_run, created_at
                       FROM vhp_renewal_log
                       WHERE device_id = ?
                       ORDER BY created_at DESC LIMIT ?""",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT id, device_id, token_id, old_expires_at,
                              new_expires_at, tx_hash, dry_run, created_at
                       FROM vhp_renewal_log
                       ORDER BY created_at DESC LIMIT ?""",
                    (limit,),
                ).fetchall()
            return [
                {
                    "id": r[0], "device_id": r[1], "token_id": r[2],
                    "old_expires_at": r[3], "new_expires_at": r[4],
                    "tx_hash": r[5], "dry_run": bool(r[6]), "created_at": r[7],
                }
                for r in rows
            ]

    def get_expiring_vhps(self, cutoff_ts: float) -> list[dict]:
        """Return vhp_issuances where now < expires_at < cutoff_ts (Phase 102)."""
        now = __import__("time").time()
        with self._conn() as conn:
            rows = conn.execute(
                """SELECT device_id, token_id, expires_at
                   FROM vhp_issuances
                   WHERE expires_at > ? AND expires_at < ?
                   ORDER BY expires_at ASC""",
                (now, cutoff_ts),
            ).fetchall()
            return [
                {"device_id": r[0], "token_id": r[1], "expires_at": r[2]}
                for r in rows
            ]

    def get_total_vhp_count(self) -> int:
        """Return COUNT(*) of all vhp_issuances records (Phase 102)."""
        with self._conn() as conn:
            row = conn.execute("SELECT COUNT(*) FROM vhp_issuances").fetchone()
            return int(row[0]) if row else 0

    def get_first_vhp_status(self) -> dict | None:
        """Return earliest VHP issuance record + is_valid + is_simulation flags (Phase 103).
        is_simulation=True when tx_hash starts with 'sim_'.
        Returns None when no VHP has ever been issued.
        """
        import time as _t
        with self._conn() as conn:
            row = conn.execute(
                "SELECT device_id, token_id, tx_hash, expires_at, cert_level, "
                "consecutive_clean, to_address, created_at "
                "FROM vhp_issuances ORDER BY created_at ASC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        tx_hash = row[2] or ""
        expires_at = row[3] or 0.0
        return {
            "device_id": row[0],
            "token_id": row[1],
            "tx_hash": tx_hash,
            "expires_at": expires_at,
            "cert_level": row[4],
            "consecutive_clean": row[5],
            "to_address": row[6] or "",
            "created_at": row[7],
            "is_valid": expires_at > _t.time(),
            "is_simulation": tx_hash.startswith("sim_"),
        }

    def get_epoch_window_analytics(self, limit: int = 1000) -> dict:
        """Return analytics over poad_age_seconds from vhp_dual_gate_log.

        Returns: dict with total_gate5_checks, staleness_blocked_count, checked_count
        (rows with poad_age_seconds >= 0), p50/p95/p99 age in seconds, max_age_seconds,
        recommended_window_seconds (2× p95 or 86400 if <10 samples).
        """
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM vhp_dual_gate_log LIMIT ?", (limit,)
            ).fetchone()[0]
            blocked = conn.execute(
                "SELECT COUNT(*) FROM vhp_dual_gate_log WHERE epoch_window_ok = 0"
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT poad_age_seconds FROM vhp_dual_gate_log "
                "WHERE poad_age_seconds >= 0 ORDER BY poad_age_seconds ASC LIMIT ?",
                (limit,),
            ).fetchall()
        ages = [r[0] for r in rows]
        n = len(ages)

        def _pct(lst, p):
            if not lst:
                return -1.0
            idx = int(len(lst) * p / 100.0)
            idx = min(idx, len(lst) - 1)
            return lst[idx]

        p50  = _pct(ages, 50)
        p95  = _pct(ages, 95)
        p99  = _pct(ages, 99)
        maxv = max(ages) if ages else -1.0
        # Recommend 2× p95, floored at 3600s (1h), capped at 604800s (7d)
        # Falls back to 86400 if fewer than 10 samples
        if n >= 10 and p95 > 0:
            rec = max(3600.0, min(604800.0, p95 * 2.0))
        else:
            rec = 86400.0
        return {
            "total_gate5_checks":      total,
            "staleness_blocked_count": blocked,
            "checked_count":           n,
            "p50_age_seconds":         p50,
            "p95_age_seconds":         p95,
            "p99_age_seconds":         p99,
            "max_age_seconds":         maxv,
            "recommended_window_seconds": rec,
        }

    def get_epoch_window_analytics_by_device(
        self, limit_per_device: int = 100, top_n: int = 20
    ) -> "list[dict]":
        """Return per-device epoch freshness analytics sorted by p95 DESC (worst first).

        Each entry: device_id, check_count, blocked_count, p50_age_seconds,
        p95_age_seconds, last_check_ts.
        Only devices with at least 1 checked entry (poad_age_seconds >= 0) are included.
        """
        with self._conn() as conn:
            device_rows = conn.execute(
                "SELECT DISTINCT device_id FROM vhp_dual_gate_log "
                "WHERE poad_age_seconds >= 0"
            ).fetchall()

        def _pct(lst, p):
            if not lst:
                return -1.0
            idx = min(int(len(lst) * p / 100.0), len(lst) - 1)
            return lst[idx]

        results = []
        for dr in device_rows:
            dev = dr[0]
            with self._conn() as conn:
                age_rows = conn.execute(
                    "SELECT poad_age_seconds, created_at FROM vhp_dual_gate_log "
                    "WHERE device_id = ? AND poad_age_seconds >= 0 "
                    "ORDER BY poad_age_seconds ASC LIMIT ?",
                    (dev, limit_per_device),
                ).fetchall()
                blocked = conn.execute(
                    "SELECT COUNT(*) FROM vhp_dual_gate_log "
                    "WHERE device_id = ? AND epoch_window_ok = 0",
                    (dev,),
                ).fetchone()[0]
                last_ts = conn.execute(
                    "SELECT MAX(created_at) FROM vhp_dual_gate_log WHERE device_id = ?",
                    (dev,),
                ).fetchone()[0]
            ages = [r[0] for r in age_rows]
            results.append({
                "device_id":       dev,
                "check_count":     len(ages),
                "blocked_count":   blocked,
                "p50_age_seconds": _pct(ages, 50),
                "p95_age_seconds": _pct(ages, 95),
                "last_check_ts":   last_ts or 0.0,
            })

        # Sort by p95 DESC — worst offenders first
        results.sort(key=lambda x: x["p95_age_seconds"], reverse=True)
        return results[:top_n]

    def insert_vhp_dual_gate_log(
        self,
        device_id: str,
        poad_hash: str,
        eligible: bool,
        poac_valid: bool,
        poad_valid: bool,
        mint_allowed: bool,
        poad_age_seconds: float = -1.0,
        epoch_window_ok: bool = True,
    ) -> int:
        import time as _t
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO vhp_dual_gate_log "
                "(device_id, poad_hash, eligible, poac_valid, poad_valid, mint_allowed, "
                "poad_age_seconds, epoch_window_ok, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (device_id, poad_hash, int(eligible), int(poac_valid),
                 int(poad_valid), int(mint_allowed),
                 float(poad_age_seconds), int(epoch_window_ok), _t.time()),
            )
            return cur.lastrowid

    def get_vhp_dual_gate_log(
        self, device_id: "str | None" = None, limit: int = 20
    ) -> "list[dict]":
        """Return vhp_dual_gate_log rows, newest first. Optionally filter by device_id."""
        with self._conn() as conn:
            if device_id:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, "
                    "mint_allowed, poad_age_seconds, epoch_window_ok, created_at "
                    "FROM vhp_dual_gate_log "
                    "WHERE device_id = ? ORDER BY id DESC LIMIT ?",
                    (device_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT id, device_id, poad_hash, eligible, poac_valid, poad_valid, "
                    "mint_allowed, poad_age_seconds, epoch_window_ok, created_at "
                    "FROM vhp_dual_gate_log "
                    "ORDER BY id DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [
            {"id": r[0], "device_id": r[1], "poad_hash": r[2],
             "eligible": bool(r[3]), "poac_valid": bool(r[4]),
             "poad_valid": bool(r[5]), "mint_allowed": bool(r[6]),
             "poad_age_seconds": r[7], "epoch_window_ok": bool(r[8]),
             "created_at": r[9]}
            for r in rows
        ]

    def insert_reenrollment_badge_log(
        self,
        player_id: str,
        attestation_hash: str,
        badge_token_id: int,
        ttl_days: float,
        on_chain_tx: str,
        dry_run: bool,
    ) -> int:
        """Insert a VHP re-enrollment badge log record (Phase 187)."""
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO vhp_reenrollment_badge_log "
                "(player_id, attestation_hash, badge_token_id, ttl_days, "
                "on_chain_tx, dry_run, created_at) VALUES (?,?,?,?,?,?,?)",
                (
                    player_id,
                    attestation_hash,
                    int(badge_token_id),
                    float(ttl_days),
                    on_chain_tx,
                    1 if dry_run else 0,
                    time.time(),
                ),
            )
        return cur.lastrowid  # type: ignore[return-value]

    def get_reenrollment_badge_status(self, player_id: "str | None" = None) -> dict:
        """Return VHP re-enrollment badge status (Phase 187)."""
        try:
            with self._conn() as conn:
                if player_id:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, badge_token_id, ttl_days, "
                        "on_chain_tx, dry_run, created_at "
                        "FROM vhp_reenrollment_badge_log WHERE player_id=? ORDER BY id DESC LIMIT 1",
                        (player_id,),
                    ).fetchone()
                    total_badges = conn.execute(
                        "SELECT COUNT(*) FROM vhp_reenrollment_badge_log WHERE player_id=?",
                        (player_id,),
                    ).fetchone()[0]
                else:
                    row = conn.execute(
                        "SELECT player_id, attestation_hash, badge_token_id, ttl_days, "
                        "on_chain_tx, dry_run, created_at "
                        "FROM vhp_reenrollment_badge_log ORDER BY id DESC LIMIT 1"
                    ).fetchone()
                    total_badges = conn.execute(
                        "SELECT COUNT(*) FROM vhp_reenrollment_badge_log"
                    ).fetchone()[0]
        except Exception:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "badge_token_id": 0,
                "re_enrollment_count": 0,
                "total_badges": 0,
                "ttl_days": 90.0,
                "dry_run": True,
            }
        if row is None:
            return {
                "player_id": player_id or "",
                "attestation_hash": "",
                "badge_token_id": 0,
                "re_enrollment_count": 0,
                "total_badges": 0,
                "ttl_days": 90.0,
                "dry_run": True,
            }
        return {
            "player_id":          row[0],
            "attestation_hash":   row[1],
            "badge_token_id":     int(row[2]),
            "re_enrollment_count": int(total_badges),
            "total_badges":       int(total_badges),
            "ttl_days":           float(row[3]),
            "dry_run":            bool(row[5]),
        }
