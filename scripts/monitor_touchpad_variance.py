"""
monitor_touchpad_variance.py — Live touchpad variance monitor for calibration.

Polls the bridge SQLite database for the latest session's touch_position_variance
(L4 feature index 10) and emits a line each time a nonzero value is detected.

Run while playing NCAA College Football 26:

    python scripts/monitor_touchpad_variance.py

Output format:
    [HH:MM:SS] TOUCHPAD CONTACT DETECTED  variance=0.003821  session=<session_id>
    [HH:MM:SS] idle (touch_position_variance=0.0)

Stop with Ctrl-C.
"""

import sys
import time
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

# Default DB path — override via CLI arg
_DEFAULT_DB = Path(__file__).parents[1] / "bridge" / "vapi_bridge.db"

POLL_INTERVAL_S = 2.0
NONZERO_THRESHOLD = 1e-9  # anything above floating-point noise counts


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def _query_latest_variance(conn: sqlite3.Connection) -> tuple:
    """Return (touch_position_variance, session_id) from the most recent proof row.

    touch_position_variance is stored in l4_features_json as index 10 of the
    feature vector.  Falls back to 0.0 if missing or unparseable.
    """
    import json

    row = conn.execute(
        "SELECT l4_features_json, session_id "
        "FROM pitl_session_proofs "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()

    if row is None:
        return 0.0, None

    features_json, session_id = row
    try:
        features = json.loads(features_json or "[]")
        if isinstance(features, list) and len(features) > 10:
            return float(features[10]), session_id
    except Exception:
        pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
    return 0.0, session_id


def main():
    db_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_DB

    if not db_path.exists():
        print(f"[{_ts()}] ERROR: database not found at {db_path}")
        print("         Start the bridge first, then re-run this script.")
        sys.exit(1)

    print(f"[{_ts()}] Monitoring touchpad variance in: {db_path}")
    print(f"[{_ts()}] Play NCAA CFB 26 and touch the DualShock Edge touchpad.")
    print(f"[{_ts()}] Ctrl-C to stop.\n")

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
    last_session = None
    contact_count = 0

    try:
        while True:
            variance, session_id = _query_latest_variance(conn)

            if variance > NONZERO_THRESHOLD:
                contact_count += 1
                marker = "TOUCHPAD CONTACT DETECTED"
                print(
                    f"[{_ts()}] {marker}  variance={variance:.6f}"
                    f"  session={str(session_id)[:16] if session_id else '?'}"
                    f"  (total_contacts={contact_count})"
                )
            else:
                # Print idle status at reduced frequency to avoid log spam
                if session_id != last_session:
                    print(
                        f"[{_ts()}] idle (touch_position_variance=0.0)"
                        f"  session={str(session_id)[:16] if session_id else 'no data yet'}"
                    )
                    last_session = session_id

            time.sleep(POLL_INTERVAL_S)

    except KeyboardInterrupt:
        print(f"\n[{_ts()}] Stopped.  Total touchpad contact detections: {contact_count}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
