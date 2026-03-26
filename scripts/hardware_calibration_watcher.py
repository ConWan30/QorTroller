#!/usr/bin/env python3
"""
Hardware Calibration Watcher — Phase 108 Support Tool
======================================================
Monitors the VAPI bridge SQLite database while the operator plays NCAA CFB 26
on DualShock Edge and auto-exports calibration progress to:

  calibration_sessions/hardware_calibration_progress.json

Run from the repo root:
  python scripts/hardware_calibration_watcher.py

Key metric tracked: touch_position_variance (BiometricFeatureFrame index 10)
  - Currently ZERO across all N=78 sessions (touchpad not captured during gameplay)
  - Must become NONZERO to unlock inter-person separation ratio improvement
  - separation_ratio_current > 1.0 required for tournament deployment (currently 0.362)

After collecting ≥50 sessions across ≥3 players with nonzero touch variance, run:
  python scripts/interperson_separation_analyzer.py
Then set SEPARATION_RATIO_CURRENT=<new_value> env var and re-run this watcher.

Environment:
  DB_PATH                  — override bridge.db path (default: ~/.vapi/bridge.db)
  POLL_S                   — poll interval seconds (default: 30)
  SEPARATION_RATIO_CURRENT — current empirical separation ratio (default: 0.362)
"""

import json
import os
import pathlib
import sqlite3
import sys
import time

_REPO_ROOT = pathlib.Path(__file__).parents[1]
_DEFAULT_DB = pathlib.Path.home() / ".vapi" / "bridge.db"
_OUTPUT_FILE = _REPO_ROOT / "calibration_sessions" / "hardware_calibration_progress.json"
_POLL_INTERVAL = int(os.environ.get("POLL_S", "30"))


def _find_db() -> pathlib.Path:
    db_env = os.environ.get("DB_PATH", "")
    if db_env:
        return pathlib.Path(db_env)
    if _DEFAULT_DB.exists():
        return _DEFAULT_DB
    # Dev fallback: find any non-test .db in bridge/
    for candidate in sorted(_REPO_ROOT.glob("bridge/**/*.db")):
        if "test" not in candidate.name:
            return candidate
    return _DEFAULT_DB


def _read_sessions(db_path: pathlib.Path) -> list:
    """Read records.pitl_l4_features, grouped into sessions by 5-min time gaps per device."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    raw_rows = []
    try:
        conn.execute("PRAGMA journal_mode=WAL")
        raw_rows = conn.execute(
            "SELECT device_id, pitl_l4_features, created_at "
            "FROM records "
            "WHERE pitl_l4_features IS NOT NULL "
            "ORDER BY device_id, created_at ASC"
        ).fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()

    # Group consecutive frames from the same device into sessions.
    # A gap > 300s between consecutive frames marks a new session.
    # Only count sessions with >= 30 records — idle bursts are excluded.
    _GAP = 300.0
    _MIN_RECORDS = 30
    sessions = []
    current_device = ""
    best_feat = {}
    last_ts = 0.0
    session_end_ts = 0.0
    record_count = 0

    def _flush(device_id, feat, end_ts, n):
        if not device_id or n < _MIN_RECORDS:
            return
        sessions.append({
            "device_id": device_id,
            "touch_position_variance": float(feat.get("touch_position_variance", 0.0)),
            "trigger_onset_velocity_l2": float(feat.get("trigger_onset_velocity_l2", 0.0)),
            "micro_tremor_accel_variance": float(feat.get("micro_tremor_accel_variance", 0.0)),
            "press_timing_jitter_variance": float(feat.get("press_timing_jitter_variance", 0.0)),
            "tremor_peak_hz": float(feat.get("tremor_peak_hz", 0.0)),
            "accel_magnitude_spectral_entropy": float(feat.get("accel_magnitude_spectral_entropy", 0.0)),
            "created_at": end_ts,
        })

    for row in raw_rows:
        dev = row["device_id"] or ""
        ts = float(row["created_at"] or 0)
        feat = {}
        raw = row["pitl_l4_features"]
        if raw:
            try:
                feat = json.loads(raw)
            except Exception:
                pass

        if dev != current_device or (ts - last_ts) > _GAP:
            _flush(current_device, best_feat, session_end_ts, record_count)
            current_device = dev
            best_feat = feat
            record_count = 1
        else:
            if float(feat.get("touch_position_variance", 0.0)) > float(best_feat.get("touch_position_variance", 0.0)):
                best_feat = feat
            record_count += 1

        last_ts = ts
        session_end_ts = ts

    _flush(current_device, best_feat, session_end_ts, record_count)
    return sessions


def _read_rulings(db_path: pathlib.Path) -> list:
    """Read agent_rulings for false positive tracking."""
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path), timeout=5)
    conn.row_factory = sqlite3.Row
    rulings = []
    try:
        rows = conn.execute(
            "SELECT device_id, verdict, dry_run, created_at FROM agent_rulings"
        ).fetchall()
        for r in rows:
            rulings.append({
                "device_id": r["device_id"] or "",
                "verdict": r["verdict"] or "",
                "dry_run": bool(r["dry_run"]),
                "created_at": r["created_at"] or 0,
            })
    except sqlite3.OperationalError:
        pass
    finally:
        conn.close()
    return rulings


def _compute_progress(sessions: list, rulings: list) -> dict:
    """Compute calibration progress statistics."""
    sep_ratio = float(os.environ.get("SEPARATION_RATIO_CURRENT", "0.362"))

    if not sessions:
        return {
            "n_sessions": 0,
            "n_players": 0,
            "sessions_with_touch_variance": 0,
            "touch_variance_mean": 0.0,
            "touch_variance_max": 0.0,
            "touch_variance_nonzero_fraction": 0.0,
            "false_positive_count": 0,
            "false_positive_rate": 0.0,
            "separation_ratio_current": sep_ratio,
            "separation_ratio_required": 1.0,
            "players": {},
            "recent_sessions": [],
        }

    # Group by player (device_id)
    player_map = {}
    for s in sessions:
        player_map.setdefault(s["device_id"], []).append(s)

    tvars = [s["touch_position_variance"] for s in sessions]
    nonzero_count = sum(1 for v in tvars if v > 0.0)
    n = len(tvars)

    # Per-player stats
    players = {}
    for device_id, player_sessions in player_map.items():
        ptvars = [s["touch_position_variance"] for s in player_sessions]
        key = device_id[:16] + "..." if len(device_id) > 16 else device_id
        players[key] = {
            "n_sessions": len(player_sessions),
            "touch_variance_mean": sum(ptvars) / len(ptvars),
            "touch_variance_nonzero_count": sum(1 for v in ptvars if v > 0),
            "touch_variance_max": max(ptvars),
        }

    # False positives: BLOCK verdict in live (non-dry-run) sessions
    live_blocks = [r for r in rulings if r["verdict"] == "BLOCK" and not r["dry_run"]]
    live_total = [r for r in rulings if not r["dry_run"]]
    fp_rate = len(live_blocks) / len(live_total) if live_total else 0.0

    # Recent sessions (last 10)
    recent = sorted(sessions, key=lambda s: s["created_at"], reverse=True)[:10]

    return {
        "n_sessions": n,
        "n_players": len(player_map),
        "sessions_with_touch_variance": nonzero_count,
        "touch_variance_mean": sum(tvars) / n,
        "touch_variance_max": max(tvars),
        "touch_variance_nonzero_fraction": nonzero_count / n,
        "false_positive_count": len(live_blocks),
        "false_positive_rate": fp_rate,
        "separation_ratio_current": sep_ratio,
        "separation_ratio_required": 1.0,
        "players": players,
        "recent_sessions": recent,
    }


def _write_progress(progress: dict, db_path: pathlib.Path) -> None:
    """Write progress JSON atomically (tmp + rename)."""
    _OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _OUTPUT_FILE.with_suffix(".tmp")
    data = {
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": str(db_path),
        **progress,
        "_note": (
            "touch_position_variance MUST be nonzero to unlock inter-person separation ratio "
            "improvement. After n_sessions>=50 across n_players>=3 with nonzero touch variance, "
            "run: python scripts/interperson_separation_analyzer.py. "
            "Then set SEPARATION_RATIO_CURRENT=<new_value> and re-run this watcher. "
            "Tournament gate: separation_ratio_current > 1.0 (currently 0.362 — BLOCKER)."
        ),
    }
    tmp.write_text(json.dumps(data, indent=2))
    try:
        tmp.replace(_OUTPUT_FILE)
    except OSError:
        try:
            _OUTPUT_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        tmp.rename(_OUTPUT_FILE)


def _poll_once(db_path: pathlib.Path) -> dict:
    sessions = _read_sessions(db_path)
    rulings = _read_rulings(db_path)
    progress = _compute_progress(sessions, rulings)
    _write_progress(progress, db_path)
    return progress


def main() -> None:
    db_path = _find_db()
    print("[VAPI Hardware Calibration Watcher]")
    print(f"  DB:     {db_path}")
    print(f"  Output: {_OUTPUT_FILE}")
    print(f"  Poll:   every {_POLL_INTERVAL}s")
    print()
    print("  Goal 1: touch_position_variance > 0 in calibration sessions")
    print("  Goal 2: n_sessions >= 50 across n_players >= 3")
    print("  Goal 3: separation_ratio_current > 1.0 (currently 0.362 — TOURNAMENT BLOCKER)")
    print()
    if not db_path.exists():
        print(f"  [WARN] DB not found at {db_path}. Start bridge first. Polling anyway...")
    print("  Press Ctrl+C to stop.\n")

    while True:
        try:
            progress = _poll_once(db_path)
            n = progress["n_sessions"]
            tv_frac = progress["touch_variance_nonzero_fraction"]
            ratio = progress["separation_ratio_current"]
            status = (
                f"n={n} sessions | "
                f"touch_var_nonzero={progress['sessions_with_touch_variance']} ({tv_frac:.0%}) | "
                f"players={progress['n_players']} | "
                f"sep_ratio={ratio:.3f} | "
                f"fp={progress['false_positive_count']}"
            )
            print(f"\r  [{time.strftime('%H:%M:%S')}] {status}", end="", flush=True)
        except Exception as exc:
            print(f"\n  [ERROR] {exc}", file=sys.stderr)
        time.sleep(_POLL_INTERVAL)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n  Watcher stopped.")
        sys.exit(0)
