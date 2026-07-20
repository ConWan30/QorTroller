#!/usr/bin/env python3
"""F-L6B-SEAL-1 reconciliation — migrate the Edge's l6b_probe_log reflex rows into the LIVE bridge DB.

The N>=50 L6B calibration gate is MET in bridge.db (the historical corpus) but the live bridge reads a
different db_path (presence_lean.db, lean mode) where the gate is NOT met. This copies the certified Edge's
l6b_probe_log rows from --src into --dst so the LIVE DB clears its own gate — keeping lean mode.

SAFE BY DESIGN: additive + IDEMPOTENT (dedups on record_hash, falling back to (device_id, probe_ts_ms) when
record_hash is null), NEVER copies the source `id` PK (dst autoincrements), backs up --dst before any write,
and re-verifies the gate after. Dry-run by default; --execute to migrate. Local DB only — no chain, no
flag flip (enabling L6B_ENABLED stays a separate operator seal), no commit of biometric data.

  python scripts/l6b_migrate_reflex_rows.py                 # dry-run (default)
  python scripts/l6b_migrate_reflex_rows.py --execute       # migrate + re-verify gate
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

EDGE = "581a836c98b3a1b6c0f598bfca88e6a3cc3bd7c34591b506692cb40ddf66a9f8"
_COLS = ["device_id", "probe_ts_ms", "latency_ms", "classification", "accel_delta_peak", "created_at",
         "reflex_verdict", "cco_profile_id", "policy_ref", "trigger_r2_at_probe", "record_hash", "player"]  # NOT id


def _natural_key(row: dict) -> str:
    """Idempotency key: record_hash if present, else device_id|probe_ts_ms."""
    rh = row.get("record_hash")
    if rh:
        return f"rh:{rh}"
    return f"dt:{row.get('device_id')}|{row.get('probe_ts_ms')}"


def _gate(db_path: str, device_id: str) -> dict:
    from bridge.vapi_bridge.store import Store  # noqa: E402
    st = Store(db_path)
    prog = st.get_l6b_calibration_progress(device_id=device_id)
    return prog


def main() -> int:
    from bridge.vapi_bridge.config import Config  # noqa: E402
    ap = argparse.ArgumentParser(description="F-L6B-SEAL-1: migrate Edge l6b_probe_log rows into the live DB")
    ap.add_argument("--src", default="C:/Users/Contr/.vapi/bridge.db", help="source DB (the corpus)")
    ap.add_argument("--dst", default=None, help="dest DB (default = the live bridge db_path)")
    ap.add_argument("--device-id", default=EDGE, help="Edge device_id hex")
    ap.add_argument("--execute", action="store_true", help="actually migrate (default: dry-run)")
    args = ap.parse_args()
    dst = args.dst or Config().db_path
    if os.path.abspath(args.src) == os.path.abspath(dst):
        print("src and dst are the same DB — nothing to migrate."); return 2

    print(f"=== F-L6B-SEAL-1 reflex-row migration ({'EXECUTE' if args.execute else 'DRY-RUN'}) ===")
    print(f"  src: {args.src}\n  dst: {dst}\n  device: {args.device_id[:16]}…")

    # read source rows for the Edge
    sc = sqlite3.connect(args.src); sc.row_factory = sqlite3.Row
    src_rows = [dict(r) for r in sc.execute(
        f"SELECT {','.join(_COLS)} FROM l6b_probe_log WHERE device_id=?", (args.device_id,)).fetchall()]
    sc.close()

    # existing dst natural keys
    dc = sqlite3.connect(dst); dc.row_factory = sqlite3.Row
    dst_rows = [dict(r) for r in dc.execute(
        "SELECT device_id, probe_ts_ms, record_hash FROM l6b_probe_log WHERE device_id=?",
        (args.device_id,)).fetchall()]
    dst_keys = {_natural_key(r) for r in dst_rows}
    to_insert = [r for r in src_rows if _natural_key(r) not in dst_keys]
    dupes = len(src_rows) - len(to_insert)
    print(f"  src Edge rows: {len(src_rows)} | dst Edge rows: {len(dst_rows)} | "
          f"NEW to insert: {len(to_insert)} | skipped as dup: {dupes}")

    g_before = _gate(dst, args.device_id)
    print(f"  gate BEFORE (dst): independent={g_before.get('independent_reflex_count')} "
          f"gate_reached={g_before.get('gate_reached')}")

    if not args.execute:
        # project the post-migrate independent count is non-trivial (dedup+independence window); report the
        # raw usable delta and defer the authoritative gate to the post-execute re-verify.
        new_usable = sum(1 for r in to_insert if r.get("reflex_verdict") == "REFLEX_OBSERVED")
        print(f"  DRY-RUN: would insert {len(to_insert)} rows ({new_usable} REFLEX_OBSERVED). "
              f"Re-run with --execute to migrate + get the authoritative post-gate.")
        dc.close(); return 0

    # EXECUTE: back up dst first, then insert
    bak = f"{dst}.pre-l6b-migrate.{int(time.time())}.bak"
    shutil.copy2(dst, bak)
    print(f"  backed up dst -> {bak}")
    ph = ",".join("?" * len(_COLS))
    dc.executemany(f"INSERT INTO l6b_probe_log ({','.join(_COLS)}) VALUES ({ph})",
                   [tuple(r[c] for c in _COLS) for r in to_insert])
    dc.commit(); dc.close()
    print(f"  inserted {len(to_insert)} rows.")

    g_after = _gate(dst, args.device_id)
    print(f"  gate AFTER (dst): independent={g_after.get('independent_reflex_count')} "
          f"gate_reached={g_after.get('gate_reached')}")
    if g_after.get("gate_reached"):
        print("  RESULT: gate MET on the live DB — L6B_ENABLED is now fireable (operator seal). "
              "Roll back by restoring the .bak if needed.")
    else:
        print("  RESULT: gate still NOT met — investigate (independence window / verdict distribution).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
