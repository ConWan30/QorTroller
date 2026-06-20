"""Read-only L6B probe watcher — prints each new row with peak scale hint."""

from __future__ import annotations

import sqlite3
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.config import Config

INTERVAL_S = 5.0


def _era_label(peak: float | None) -> str:
    if peak is None:
        return "?"
    if peak >= 100:
        return "LSB-OK"
    if peak < 1.0:
        return "g-era/OLD"
    return "mid"


def main() -> int:
    db = Path(Config().db_path)
    print(f"L6B live monitor — {db}")
    print("accel_delta_peak >= 100 => fix active | < 1 => restart bridge on old code")
    print("Ctrl-C to stop.\n")

    last_id = 0
    while True:
        try:
            conn = sqlite3.connect(f"file:{db.resolve()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA busy_timeout = 5000")
            total = int(conn.execute("SELECT COUNT(*) FROM l6b_probe_log").fetchone()[0])
            rows = conn.execute(
                "SELECT id, accel_delta_peak, latency_ms, classification, "
                "reflex_verdict, created_at FROM l6b_probe_log "
                "WHERE id > ? ORDER BY id",
                (last_id,),
            ).fetchall()
            conn.close()

            for row in rows:
                peak = float(row["accel_delta_peak"] or 0.0)
                lat = row["latency_ms"]
                lat_s = f"{lat:.1f}" if lat is not None else "-"
                print(
                    f"[{row['created_at']}] #{row['id']} "
                    f"peak={peak:.2f} ({_era_label(peak)}) "
                    f"class={row['classification']} latency={lat_s} "
                    f"reflex={row['reflex_verdict']}"
                )
                last_id = int(row["id"])

            if not rows:
                print(f"... N={total} waiting for new probes", flush=True)
            time.sleep(INTERVAL_S)
        except KeyboardInterrupt:
            print("\nStopped.")
            return 0
        except Exception as exc:
            print(f"poll error: {exc}", flush=True)
            time.sleep(INTERVAL_S)


if __name__ == "__main__":
    raise SystemExit(main())
