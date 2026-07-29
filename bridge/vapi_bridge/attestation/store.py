"""Attestation database operations.

New table 'attestations' only — no modifications to existing
sessions, messages, or decisions tables.
"""

from __future__ import annotations

import json
import sqlite3
import logging
from typing import Optional, List, Dict, Any
from .types import AttestationEnvelope

log = logging.getLogger(__name__)

# ── Schema ───────────────────────────────────────────────

CREATE_ATTESTATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS attestations (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id        TEXT NOT NULL,
    tick              INTEGER NOT NULL,
    timestamp         REAL NOT NULL,
    envelope_json     TEXT NOT NULL,
    attestation_hash  TEXT NOT NULL,
    cross_modal_hash  TEXT NOT NULL,
    pv_ci_fingerprint TEXT NOT NULL DEFAULT '',
    previous_hash     TEXT NOT NULL DEFAULT '',
    created_at        TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
CREATE INDEX IF NOT EXISTS idx_att_attestation_hash
    ON attestations(attestation_hash);
CREATE INDEX IF NOT EXISTS idx_att_session_tick
    ON attestations(session_id, tick);
CREATE INDEX IF NOT EXISTS idx_att_timestamp
    ON attestations(timestamp);
"""


class AttestationStore:
    """Persists attestation envelopes to the session database."""

    def __init__(self, db_path: str):
        self._db_path = db_path
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")  # concurrent read/write
        return conn

    def _init_db(self):
        """Create the attestations table if it doesn't exist."""
        try:
            with self._get_conn() as conn:
                conn.executescript(CREATE_ATTESTATIONS_TABLE)
        except Exception as exc:
            log.warning("AttestationStore init failed: %s", exc)

    def append(self, envelope: AttestationEnvelope) -> bool:
        """Append an attestation envelope to the database.

        Returns True on success, False on failure.
        """
        try:
            data = envelope.to_dict()
            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO attestations
                       (session_id, tick, timestamp, envelope_json,
                        attestation_hash, cross_modal_hash,
                        pv_ci_fingerprint, previous_hash)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        data["session_id"],
                        data["tick"],
                        data["timestamp"],
                        json.dumps(data, default=str),
                        data["envelope_hash"],
                        data["cross_modal_hash"],
                        data["pv_ci_fingerprint"],
                        data["previous_envelope_hash"],
                    ),
                )
            return True
        except Exception as exc:
            log.error("Failed to append attestation: %s", exc)
            return False

    def get_by_session(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Get attestations for a session, ordered by tick ascending."""
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT * FROM attestations
                       WHERE session_id = ?
                       ORDER BY tick ASC
                       LIMIT ? OFFSET ?""",
                    (session_id, limit, offset),
                ).fetchall()
                return [dict(r) for r in rows]
        except Exception as exc:
            log.error("Failed to query attestations: %s", exc)
            return []

    def get_by_hash(self, attestation_hash: str) -> Optional[Dict[str, Any]]:
        """Get a specific attestation by its hash."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM attestations WHERE attestation_hash = ?",
                    (attestation_hash,),
                ).fetchone()
                return dict(row) if row else None
        except Exception as exc:
            log.error("Failed to query attestation by hash: %s", exc)
            return None

    def get_latest_for_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get the most recent attestation for a session."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    """SELECT * FROM attestations
                       WHERE session_id = ?
                       ORDER BY tick DESC LIMIT 1""",
                    (session_id,),
                ).fetchone()
                return dict(row) if row else None
        except Exception as exc:
            log.error("Failed to query latest attestation: %s", exc)
            return None

    def count_by_session(self, session_id: str) -> int:
        """Count attestations for a session."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT COUNT(*) as c FROM attestations WHERE session_id = ?",
                    (session_id,),
                ).fetchone()
                return row["c"] if row else 0
        except Exception as exc:
            log.error("Failed to count attestations: %s", exc)
            return 0

    def delete_older_than(self, cutoff_timestamp: float) -> int:
        """Delete attestations older than a timestamp. Returns count deleted."""
        try:
            with self._get_conn() as conn:
                result = conn.execute(
                    "DELETE FROM attestations WHERE timestamp < ?",
                    (cutoff_timestamp,),
                )
                return result.rowcount
        except Exception as exc:
            log.error("Failed to delete old attestations: %s", exc)
            return 0

    def get_session_attestation_range(
        self, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get first and last attestation for a session (tick range)."""
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    """SELECT
                           MIN(tick) as first_tick,
                           MAX(tick) as last_tick,
                           MIN(timestamp) as first_ts,
                           MAX(timestamp) as last_ts,
                           COUNT(*) as total
                       FROM attestations WHERE session_id = ?""",
                    (session_id,),
                ).fetchone()
                return dict(row) if row and row["total"] > 0 else None
        except Exception as exc:
            log.error("Failed to query attestation range: %s", exc)
            return None