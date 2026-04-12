"""
MigrationRunner — VAPI-EXT Phase 204+

Versioned SQLite schema management with tamper detection.

Design principles (same philosophy as PoAC chain link integrity):
  - Each migration file is identified by its filename and SHA-256 hash at application time.
  - If a migration file is modified after it was applied, MigrationTamperError is raised.
    The same principle applies here: a modified migration represents a data integrity violation.
  - Migrations are idempotent: already-applied files are skipped.
  - Execution order is alphabetical by filename — prefixing files with NNN_ ensures ordering.

Usage:
    MigrationRunner(db_path).run_pending()

Sub-protocols drop a .sql file into bridge/vapi_bridge/migrations/ using their prefix:
    vapi_ext_001_sub_protocol_registry.sql  (VAPI_CORE meta-tables)
    vapi_ext_002_agent_manifest.sql          (VAPI_CORE agent catalogue)
    mobile_001_session_tables.sql            (VAPI_MOBILE tables)
    pragma_001_commitment_registry.sql       (PRAGMA_JUDGE tables)

The runner scans the migrations/ directory and runs all unapplied files in sorted order.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sqlite3
import time
from pathlib import Path

log = logging.getLogger(__name__)

_MIGRATIONS_DIR = Path(__file__).parent  # bridge/vapi_bridge/migrations/

_CREATE_SCHEMA_MIGRATIONS = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    migration_id TEXT PRIMARY KEY,  -- filename (e.g., vapi_ext_001_sub_protocol_registry.sql)
    sha256_hash  TEXT NOT NULL,     -- SHA-256 of file content at application time
    applied_at   REAL NOT NULL      -- Unix timestamp
);
"""


class MigrationTamperError(Exception):
    """Raised when a migration file has been modified after it was applied.

    This is a critical integrity error: the schema was bootstrapped from one version
    of the SQL but the file on disk now contains different content. The database state
    may be inconsistent.
    """


class MigrationRunner:
    """Applies pending SQL migration files to a SQLite database.

    Args:
        db_path: Path to the SQLite database file.
        migrations_dir: Directory containing .sql migration files.
                        Defaults to the migrations/ package directory.
    """

    def __init__(
        self,
        db_path: str,
        migrations_dir: "str | Path | None" = None,
    ) -> None:
        self._db_path = db_path
        self._migrations_dir = Path(migrations_dir) if migrations_dir else _MIGRATIONS_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run_pending(self) -> list[str]:
        """Apply all unapplied migration files in sorted order.

        Returns the list of migration IDs that were applied in this call.
        Raises MigrationTamperError if any applied file has been modified.
        """
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(_CREATE_SCHEMA_MIGRATIONS)
            conn.commit()

            applied = self._get_applied(conn)
            pending = self._discover_pending(applied)
            applied_now: list[str] = []

            for migration_id, sql_path in pending:
                content = sql_path.read_text(encoding="utf-8")
                sha256 = _sha256(content)

                # Tamper check: if this migration_id is in applied but hash differs,
                # a previously-applied file was modified — integrity violation.
                if migration_id in applied:
                    if applied[migration_id] != sha256:
                        raise MigrationTamperError(
                            f"Migration '{migration_id}' was applied with hash "
                            f"'{applied[migration_id]}' but current file hash is "
                            f"'{sha256}'. The migration file has been modified after "
                            "application — this is a schema integrity violation."
                        )
                    # Same hash → already applied idempotently, skip
                    continue

                log.info("MigrationRunner: applying '%s'", migration_id)
                try:
                    conn.executescript(content)
                    conn.execute(
                        "INSERT OR IGNORE INTO schema_migrations "
                        "(migration_id, sha256_hash, applied_at) VALUES (?, ?, ?)",
                        (migration_id, sha256, time.time()),
                    )
                    conn.commit()
                    applied_now.append(migration_id)
                    log.info("MigrationRunner: applied '%s' OK", migration_id)
                except Exception as exc:
                    log.error(
                        "MigrationRunner: FAILED to apply '%s': %s", migration_id, exc
                    )
                    raise

            return applied_now

    def get_applied(self) -> dict[str, str]:
        """Returns a dict of {migration_id: sha256_hash} for all applied migrations."""
        with sqlite3.connect(self._db_path, timeout=10) as conn:
            conn.execute(_CREATE_SCHEMA_MIGRATIONS)
            return self._get_applied(conn)

    def check_integrity(self) -> list[str]:
        """Check all applied migrations against their files on disk.

        Returns a list of migration_ids that have been tampered (hash mismatch).
        Returns an empty list if all applied migrations are intact.
        Does NOT raise — use this for health checks.
        """
        applied = self.get_applied()
        tampered: list[str] = []
        for migration_id, stored_hash in applied.items():
            sql_path = self._migrations_dir / migration_id
            if not sql_path.exists():
                log.warning(
                    "MigrationRunner: applied migration '%s' file not found on disk",
                    migration_id,
                )
                continue
            current_hash = _sha256(sql_path.read_text(encoding="utf-8"))
            if current_hash != stored_hash:
                tampered.append(migration_id)
        return tampered

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _get_applied(self, conn: sqlite3.Connection) -> dict[str, str]:
        """Returns {migration_id: sha256_hash} for all rows in schema_migrations."""
        cur = conn.execute("SELECT migration_id, sha256_hash FROM schema_migrations")
        return {row[0]: row[1] for row in cur.fetchall()}

    def _discover_pending(
        self,
        applied: dict[str, str],
    ) -> list[tuple[str, Path]]:
        """Return sorted list of (migration_id, path) for all .sql files in migrations_dir.

        Includes both unapplied files AND already-applied files (for tamper checking).
        """
        if not self._migrations_dir.is_dir():
            return []
        files = sorted(
            f for f in self._migrations_dir.iterdir()
            if f.suffix == ".sql" and f.is_file()
        )
        return [(f.name, f) for f in files]


def _sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
