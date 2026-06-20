"""
l6b_probe_diagnostic_report.py — F-L6B-CAL-005 latency instrumentation summary.

USAGE
-----
  python scripts/l6b_probe_diagnostic_report.py
  python scripts/l6b_probe_diagnostic_report.py --limit 10
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.config import Config


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", "-n", type=int, default=15, help="Rows to show")
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    args = parser.parse_args()

    db_path = Path(args.db or Config().db_path)
    if not db_path.exists():
        print(f"ERROR: DB not found: {db_path}")
        return 1

    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                """
                SELECT d.id, d.probe_log_id, d.created_at,
                       d.legacy_latency_ms, d.true_latency_ms,
                       d.precursor_gap_ms, d.reflex_gap_ms,
                       p.classification, p.accel_delta_peak, p.trigger_r2_at_probe
                FROM l6b_probe_diagnostic d
                LEFT JOIN l6b_probe_log p ON p.id = d.probe_log_id
                ORDER BY d.id DESC
                LIMIT ?
                """,
                (args.limit,),
            ).fetchall()
        except sqlite3.OperationalError as exc:
            print(f"No diagnostic table yet (restart bridge after instrumentation): {exc}")
            return 1

        if not rows:
            print(f"DB: {db_path}")
            print("No l6b_probe_diagnostic rows yet — run an instrumented desk session.")
            return 0

        print(f"DB: {db_path}")
        print(f"Showing last {len(rows)} diagnostic row(s):\n")
        print(
            "diag_id  probe#  legacy_ms  true_ms  precursor_ms  reflex_ms  "
            "class          peak   r2   created_at"
        )
        for r in rows:
            print(
                f"{r['id']:<8} {r['probe_log_id'] or '-':<6} "
                f"{_fmt(r['legacy_latency_ms']):>9} "
                f"{_fmt(r['true_latency_ms']):>8} "
                f"{_fmt(r['precursor_gap_ms']):>12} "
                f"{_fmt(r['reflex_gap_ms']):>9} "
                f"{(r['classification'] or '-'):<14} "
                f"{_fmt(r['accel_delta_peak'], 0):>6} "
                f"{r['trigger_r2_at_probe']!s:>3}  "
                f"{r['created_at']}"
            )
    finally:
        conn.close()
    return 0


def _fmt(val, places: int = 1) -> str:
    if val is None:
        return "-"
    return f"{float(val):.{places}f}"


if __name__ == "__main__":
    raise SystemExit(main())
