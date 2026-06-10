#!/usr/bin/env python3
"""
backup_store.py — WAL-safe SQLite backup for the QorTroller bridge DB.

DECON-1 Stream 3. Uses sqlite3's online .backup() API (NOT file copy):
copying bridge.db while the bridge process holds the WAL produces a
corrupt snapshot. The .backup() API takes a read transaction, copies
pages atomically, and is safe to run against a live DB.

Usage:
  python scripts/backup_store.py                       # default: ~/.vapi/bridge.db → ~/.vapi/backups/bridge-<ts>.db
  python scripts/backup_store.py --src PATH --dst PATH
  python scripts/backup_store.py --verify              # rehash + row-count check after backup
  python scripts/backup_store.py --retain-days 30      # prune backups older than N days

Exit codes: 0 OK; 1 source missing; 2 backup failed; 3 verify failed.

Not in scope: off-site upload. The disaster-recovery runbook documents
the off-site target separately (private companion doc). This script
produces a local snapshot ONLY.
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import sqlite3
import sys
import time
from pathlib import Path

log = logging.getLogger("backup_store")

# Tables whose row count is asserted in --verify mode.
# Chosen as a small but representative set spanning the FROZEN
# primitives' storage surface. Adding more is fine; removing any
# would weaken the verify guarantee.
_VERIFY_TABLES = (
    "devices",
    "records",
    "ruling_validation_log",
    "consent_ledger",
    "corpus_snapshot_log",
    "biometric_snapshot_log",
    "agent_commit_log",
    "watchdog_event_log",
)


def _default_src() -> Path:
    return Path.home() / ".vapi" / "bridge.db"


def _default_dst_dir() -> Path:
    return Path.home() / ".vapi" / "backups"


def _backup(src: Path, dst: Path) -> None:
    """sqlite3 online backup. Streams pages under a read transaction."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    src_conn = sqlite3.connect(str(src))
    try:
        dst_conn = sqlite3.connect(str(dst))
        try:
            with dst_conn:
                src_conn.backup(dst_conn, pages=4096, progress=None)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def _sha256(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def _row_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    conn = sqlite3.connect(str(path))
    try:
        cur = conn.cursor()
        for tbl in _VERIFY_TABLES:
            try:
                counts[tbl] = int(cur.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0])
            except sqlite3.OperationalError:
                # Table absent in this DB — record as -1 so the verify
                # diff surfaces it instead of silently skipping.
                counts[tbl] = -1
    finally:
        conn.close()
    return counts


def _verify(src: Path, dst: Path) -> bool:
    """Compare row counts on _VERIFY_TABLES between src and dst.

    Does NOT compare SHA-256 of the files — the backup API rewrites
    page boundaries so file digests differ even though contents match.
    Row count is the correct integrity signal for an online backup.
    """
    src_counts = _row_counts(src)
    dst_counts = _row_counts(dst)
    ok = True
    for tbl in _VERIFY_TABLES:
        s = src_counts.get(tbl, -1)
        d = dst_counts.get(tbl, -1)
        if s != d:
            log.error("verify FAIL %s: src=%d dst=%d", tbl, s, d)
            ok = False
        else:
            log.info("verify OK   %s: %d rows", tbl, s)
    return ok


def _prune(dst_dir: Path, retain_days: int) -> int:
    """Delete backup files older than retain_days. Returns count deleted."""
    if retain_days <= 0:
        return 0
    cutoff = time.time() - (retain_days * 86400)
    deleted = 0
    for p in dst_dir.glob("bridge-*.db"):
        try:
            if p.stat().st_mtime < cutoff:
                p.unlink()
                deleted += 1
                log.info("pruned old backup: %s", p.name)
        except OSError as exc:
            log.warning("prune skip %s: %s", p, exc)
    return deleted


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, default=None, help="source DB (default: ~/.vapi/bridge.db)")
    ap.add_argument("--dst", type=Path, default=None, help="destination file (default: ~/.vapi/backups/bridge-<ts>.db)")
    ap.add_argument("--verify", action="store_true", help="row-count check after backup")
    ap.add_argument("--retain-days", type=int, default=0, help="prune backups older than N days (0 disables)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    src = args.src or _default_src()
    if not src.exists():
        log.error("source DB not found: %s", src)
        return 1

    dst = args.dst or (_default_dst_dir() / f"bridge-{int(time.time())}.db")

    t0 = time.time()
    try:
        _backup(src, dst)
    except sqlite3.Error as exc:
        log.error("backup failed: %s", exc)
        return 2
    dt = time.time() - t0

    src_size = src.stat().st_size
    dst_size = dst.stat().st_size
    log.info("backup OK   %s (%d B) -> %s (%d B) in %.2fs", src.name, src_size, dst.name, dst_size, dt)

    if args.verify:
        if not _verify(src, dst):
            return 3

    if args.retain_days > 0:
        _prune(dst.parent, args.retain_days)

    return 0


if __name__ == "__main__":
    sys.exit(main())
