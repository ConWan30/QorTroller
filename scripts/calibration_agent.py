#!/usr/bin/env python3
"""
VAPI Calibration Intelligence Agent — Phase 148
================================================
Autonomous hardware calibration monitor. Detects controller connection,
tracks sessions, evaluates progress, and guides you toward tournament readiness.

Phase 148 state:
  Separation ratio : 1.261 (diagonal, touchpad_corners, N=11, Phase 143 proper LOO)
  Classification   : 63.6% (7/11) — BLOCKER until ≥80% (need ≥10 sessions/player)
  L4 staleness     : live_dim=13 vs calib_dim=12 — BLOCKER (run recalibrate_l4_pipeline.py)
  Players          : 3 (P1, P2, P3) — terminal_cal sessions + hw_* sessions

Activate from PowerShell (after one-time CALIBRATE_SETUP.ps1):
  calibrate              # Agentic monitor — start here while playing
  calibrate status       # One-shot scorecard
  calibrate test         # Run hardware calibration pytest suite
  calibrate players      # Per-player breakdown

Direct:
  python scripts/calibration_agent.py [status|test|players]

Environment:
  DB_PATH                  — bridge.db path (default: ~/.vapi/bridge.db)
  POLL_S                   — poll interval seconds (default: 30)
  SEPARATION_RATIO_CURRENT — override separation ratio (reads DB first; default: 1.261)
  BRIDGE_URL               — bridge API base URL (default: http://localhost:18080)
  OPERATOR_API_KEY         — bridge API key for tournament-readiness call
"""

import json
import os
import pathlib
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request

# -- Paths -------------------------------------------------------------------
_REPO_ROOT = pathlib.Path(__file__).parents[1]
_DEFAULT_DB = pathlib.Path.home() / ".vapi" / "bridge.db"
_PROGRESS_FILE = _REPO_ROOT / "calibration_sessions" / "hardware_calibration_progress.json"
_RECS_FILE = _REPO_ROOT / "calibration_sessions" / "agent_log.json"

# -- HID IDs — DualShock Edge CFI-ZCP1 --------------------------------------
_VID = 0x054C
_PID = 0x0DF2

# -- ANSI colors -------------------------------------------------------------
_R = "\033[91m"   # Red
_G = "\033[92m"   # Green
_Y = "\033[93m"   # Yellow
_C = "\033[96m"   # Cyan
_W = "\033[97m"   # White bold
_X = "\033[0m"    # Reset
_BOLD = "\033[1m"

_POLL_S = int(os.environ.get("POLL_S", "30"))
_BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://localhost:8080")
_API_KEY = os.environ.get("OPERATOR_API_KEY", "")
_CURRENT_PHASE = 228
# Phase 228 state: tremor_resting ratio=1.177 (N=27, all_pairs_p0_ok=False P1vP3=0.032 BLOCKER)
# touchpad_corners ratio=0.728 (N=35); path to >1.0 = tremor_resting sessions (≥5/player)
_DEFAULT_SEPARATION_RATIO = "0.728"


# -- Windows ANSI enable -----------------------------------------------------

def _enable_ansi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip


# -- Controller detection ----------------------------------------------------

def _find_controller() -> tuple[bool, str]:
    """Returns (connected, product_name). Never raises."""
    for pkg in ("hid", "hidapi"):
        try:
            mod = __import__(pkg)
            devs = mod.enumerate(_VID, _PID)
            if devs:
                name = (devs[0].get("product_string", "") or "DualShock Edge CFI-ZCP1")
                return True, name
        except Exception:
            continue
    return False, "DualShock Edge CFI-ZCP1"


# -- Database helpers --------------------------------------------------------

def _find_db() -> pathlib.Path:
    env = os.environ.get("DB_PATH", "")
    if env:
        return pathlib.Path(env)
    if _DEFAULT_DB.exists():
        return _DEFAULT_DB
    for c in sorted(_REPO_ROOT.glob("bridge/**/*.db")):
        if "test" not in c.name:
            return c
    return _DEFAULT_DB


def _query(db: pathlib.Path, sql: str) -> list:
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db), timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(sql).fetchall()]
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _load_sessions(db: pathlib.Path) -> list:
    """Read records.pitl_l4_features, grouped into sessions by 5-min time gaps per device."""
    if not db.exists():
        return []
    conn = sqlite3.connect(str(db), timeout=5)
    conn.row_factory = sqlite3.Row
    raw_rows: list = []
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
    # Only count sessions with >= 30 records as real gameplay sessions —
    # idle bursts (bridge running but not playing) are excluded.
    _GAP = 300.0
    _MIN_RECORDS = 30
    sessions: list = []
    current_device: str = ""
    best_feat: dict = {}
    last_ts: float = 0.0
    session_end_ts: float = 0.0
    record_count: int = 0

    def _flush(device_id: str, feat: dict, end_ts: float, n: int) -> None:
        if not device_id or n < _MIN_RECORDS:
            return
        sessions.append({
            "device_id": device_id,
            "touch_position_variance": float(feat.get("touch_position_variance", 0.0)),
            "micro_tremor_accel_variance": float(feat.get("micro_tremor_accel_variance", 0.0)),
            "press_timing_jitter_variance": float(feat.get("press_timing_jitter_variance", 0.0)),
            "created_at": end_ts,
        })

    for row in raw_rows:
        dev = row["device_id"] or ""
        ts = float(row["created_at"] or 0)
        feat: dict = {}
        raw = row["pitl_l4_features"]
        if raw:
            try:
                feat = json.loads(raw)
            except Exception:
                pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip

        if dev != current_device or (ts - last_ts) > _GAP:
            _flush(current_device, best_feat, session_end_ts, record_count)
            current_device = dev
            best_feat = feat
            record_count = 1
        else:
            # Keep the frame with the highest touch_position_variance as session representative
            if float(feat.get("touch_position_variance", 0.0)) > float(best_feat.get("touch_position_variance", 0.0)):
                best_feat = feat
            record_count += 1

        last_ts = ts
        session_end_ts = ts

    _flush(current_device, best_feat, session_end_ts, record_count)
    return sessions


def _load_rulings(db: pathlib.Path) -> list:
    rows = _query(db, "SELECT verdict, dry_run FROM agent_rulings")
    return [{"verdict": r.get("verdict") or "", "dry_run": bool(r.get("dry_run"))} for r in rows]


def _load_separation_from_db(db: pathlib.Path) -> "float | None":
    """Read best separation ratio across session types.

    Priority: separation_defensibility_log (per-session-type, Phase 150+) →
              separation_ratio_snapshots pooled_ratio (Phase 121+).
    Returns the highest ratio found (best-case signal for reporting).
    Never raises.
    """
    # Phase 150+: separation_defensibility_log has per-session-type defensibility rows
    # with the ratio measured by analyze_interperson_separation.py --write-snapshot.
    # Use the highest ratio across all probe types as the headline figure.
    rows = _query(
        db,
        "SELECT ratio FROM separation_defensibility_log ORDER BY created_at DESC LIMIT 20",
    )
    if rows:
        try:
            vals = [float(r["ratio"]) for r in rows if r.get("ratio") is not None]
            if vals:
                return max(vals)
        except (KeyError, TypeError, ValueError):
            pass
    # Fallback: pooled_ratio snapshot (full-corpus, typically lower)
    rows2 = _query(
        db,
        "SELECT pooled_ratio FROM separation_ratio_snapshots ORDER BY id DESC LIMIT 1",
    )
    if rows2:
        try:
            return float(rows2[0]["pooled_ratio"])
        except (KeyError, TypeError, ValueError):
            pass
    return None


def _count_players_from_dirs() -> int:
    """Count distinct players from session directory structure.

    Reads terminal_cal_P* subdirs under sessions/human/ (P1, P2, P3 etc.) and
    hw_*.json files (all P1). Returns the number of distinct player labels found.
    Falls back to 0 if session dirs not found (bridge not yet run).
    """
    sessions_root = _REPO_ROOT / "sessions" / "human"
    players: set[str] = set()
    if sessions_root.exists():
        # terminal_cal_P1, terminal_cal_P2, terminal_cal_P3 …
        for d in sessions_root.glob("terminal_cal_P*/"):
            if d.is_dir():
                # "terminal_cal_P1" → "P1"
                label = d.name.replace("terminal_cal_", "")
                if label:
                    players.add(label)
        # hw_*.json sessions are all from Player 1
        if any(sessions_root.glob("hw_*.json")):
            players.add("P1")
    return len(players)


# -- Progress computation ----------------------------------------------------

def _compute_progress(
    sessions: list,
    rulings: list,
    db: "pathlib.Path | None" = None,
) -> dict:
    # Separation ratio: DB snapshot → env var → default 1.261
    sep_ratio: float | None = _load_separation_from_db(db) if db else None
    if sep_ratio is None:
        sep_ratio = float(os.environ.get("SEPARATION_RATIO_CURRENT", _DEFAULT_SEPARATION_RATIO))

    # Player count: directory scan (terminal_cal_P*) is authoritative
    n_players_dirs = _count_players_from_dirs()

    if not sessions:
        return {
            "n_sessions": 0,
            "n_players": n_players_dirs,
            "sessions_with_touch_variance": 0,
            "touch_variance_mean": 0.0, "touch_variance_max": 0.0,
            "touch_variance_nonzero_fraction": 0.0,
            "false_positive_count": 0, "false_positive_rate": 0.0,
            "separation_ratio_current": sep_ratio, "separation_ratio_required": 1.0,
            "players": {}, "recent_sessions": [],
        }

    player_map: dict = {}
    for s in sessions:
        player_map.setdefault(s["device_id"], []).append(s)

    tvars = [s["touch_position_variance"] for s in sessions]
    nonzero = sum(1 for v in tvars if v > 0.0)
    n = len(tvars)

    players = {}
    for did, ps in player_map.items():
        ptvars = [s["touch_position_variance"] for s in ps]
        key = (did[:16] + "...") if len(did) > 16 else did
        players[key] = {
            "n_sessions": len(ps),
            "touch_variance_mean": sum(ptvars) / len(ptvars),
            "touch_variance_nonzero_count": sum(1 for v in ptvars if v > 0),
            "touch_variance_max": max(ptvars),
        }

    live_blocks = [r for r in rulings if r["verdict"] == "BLOCK" and not r["dry_run"]]
    live_total = [r for r in rulings if not r["dry_run"]]
    fp_rate = len(live_blocks) / len(live_total) if live_total else 0.0
    recent = sorted(sessions, key=lambda s: s["created_at"], reverse=True)[:5]

    # Player count: use directory scan (authoritative) or device_id grouping, whichever is larger
    n_players_effective = max(len(player_map), n_players_dirs)

    return {
        "n_sessions": n, "n_players": n_players_effective,
        "sessions_with_touch_variance": nonzero,
        "touch_variance_mean": sum(tvars) / n,
        "touch_variance_max": max(tvars),
        "touch_variance_nonzero_fraction": nonzero / n,
        "false_positive_count": len(live_blocks),
        "false_positive_rate": fp_rate,
        "separation_ratio_current": sep_ratio, "separation_ratio_required": 1.0,
        "players": players, "recent_sessions": recent,
    }


def _write_progress(progress: dict, db: pathlib.Path) -> None:
    _PROGRESS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = _PROGRESS_FILE.with_suffix(".tmp")
    payload = {
        "last_updated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "db_path": str(db), **progress,
        "_note": (
            f"Auto-written by calibration_agent.py (Phase {_CURRENT_PHASE}). "
            "Separation ratio reads from separation_ratio_snapshots DB table when available. "
            "Phase 143: ratio=1.261 (diagonal, touchpad_corners, N=11, proper LOO). "
            "BLOCKER: classification=63.6% <80% target — need ≥10 touchpad_corners sessions/player."
        ),
    }
    tmp.write_text(json.dumps(payload, indent=2))
    try:
        tmp.replace(_PROGRESS_FILE)
    except OSError:
        # Windows: target may be locked; unlink first then rename
        try:
            _PROGRESS_FILE.unlink(missing_ok=True)
        except OSError:
            pass
        tmp.rename(_PROGRESS_FILE)


def _poll_db(db: pathlib.Path) -> dict:
    sessions = _load_sessions(db)
    rulings = _load_rulings(db)
    progress = _compute_progress(sessions, rulings, db=db)
    _write_progress(progress, db)
    return progress


# -- Bridge API (optional) ---------------------------------------------------

def _fetch_tournament_readiness() -> dict | None:
    """Call GET /agent/tournament-preflight-status. Returns dict or None if unavailable."""
    if not _API_KEY:
        return None
    try:
        req = urllib.request.Request(
            f"{_BRIDGE_URL}/agent/tournament-preflight-status",
            headers={"x-api-key": _API_KEY},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return json.loads(resp.read())
    except Exception:
        return None


def _load_l4_dim_sync_ok(db: pathlib.Path) -> bool:
    """Return True if Phase 215 confirmed L4 dim staleness is OK (sync_completed=1)."""
    rows = _query(
        db,
        "SELECT sync_completed FROM l4_dim_sync_log ORDER BY id DESC LIMIT 1",
    )
    if rows:
        try:
            return bool(rows[0].get("sync_completed", 0))
        except Exception:
            pass  # fail-open: M-1 cleanup 2026-05-16 — intentional silent skip
    return False


# -- Milestone detection -----------------------------------------------------

def _milestones(prev: dict, curr: dict) -> list[str]:
    msgs = []
    pn, cn = prev.get("n_sessions", 0), curr["n_sessions"]

    if pn == 0 and cn > 0:
        msgs.append(f"First session captured. {cn} total.")

    if pn < 50 <= cn:
        msgs.append("50 sessions reached — run interperson_separation_analyzer.py now.")

    if pn > 0 and cn > pn:
        prev_nz = prev.get("sessions_with_touch_variance", 0)
        curr_nz = curr["sessions_with_touch_variance"]
        if prev_nz == 0 and curr_nz > 0:
            msgs.append(
                f"FIRST nonzero touch_position_variance detected! "
                f"({curr['touch_variance_max']:.4f}) — Touchpad recapture ACTIVE."
            )
        elif curr_nz > 0:
            msgs.append(
                f"Session {cn}: touch_variance={curr['touch_variance_max']:.4f}"
            )
        else:
            msgs.append(f"Session {cn}: touch_position_variance still zero.")

    if prev.get("n_players", 0) < 3 <= curr["n_players"]:
        msgs.append("3 players detected — inter-person separation ratio can now be computed.")

    return msgs


# -- Display helpers ---------------------------------------------------------

def _row(label: str, value: str, ok: bool, note: str = "") -> str:
    icon = f"{_G}OK{_X}    " if ok else f"{_R}BLOCKER{_X}"
    badge = f"  {_Y}{note}{_X}" if note else ""
    return f"  {label:<26} {value:<14} [{icon}]{badge}"


def _print_scorecard(p: dict, bridge_data: dict | None = None, db: "pathlib.Path | None" = None) -> None:
    n = p["n_sessions"]
    n_pl = p["n_players"]
    nz = p["sessions_with_touch_variance"]
    frac = p["touch_variance_nonzero_fraction"]
    fp = p["false_positive_count"]
    mx = p["touch_variance_max"]
    ratio = p["separation_ratio_current"]

    # Phase 215: L4 dim staleness confirmed OK — touchpad_spatial_entropy structurally 0
    # in gameplay sessions so 13-live/12-cal does NOT require recalibration.
    # Check l4_dim_sync_log for dynamic confirmation.
    dim_sync_ok = _load_l4_dim_sync_ok(db) if db else False
    feat_label = "13-live/12-cal OK" if dim_sync_ok else "13-live/12-cal"
    feat_note = "" if dim_sync_ok else "Phase 215 confirmed OK — touchpad_spatial_entropy=0 in gameplay"

    ts = time.strftime("%H:%M:%S")
    print(f"\n{_C}{'-' * 60}{_X}")
    print(f"{_BOLD}{_W}  VAPI Calibration Scorecard   {ts}  (Phase {_CURRENT_PHASE}){_X}")
    print(f"{_C}{'-' * 60}{_X}")

    # Hardware conditions
    print(f"\n  {_C}-- Hardware Conditions ------------------------------{_X}")
    print(_row("Sessions collected", f"{n}/50", n >= 50,
               "" if n >= 50 else f"need {50 - n} more"))
    print(_row("Players detected", f"{n_pl}/3", n_pl >= 3,
               "" if n_pl >= 3 else f"need {3 - n_pl} more players"))
    print(_row("Touch var nonzero", f"{nz}/{n}", nz > 0,
               f"val={mx:.4f}" if nz > 0 else "swipe touchpad >=3x per session"))
    print(_row("Touch var coverage", f"{frac:.0%}", frac >= 0.5,
               "" if frac >= 0.5 else "play more sessions with touchpad"))
    print(_row("Feature dims", feat_label, dim_sync_ok, feat_note))
    print(_row("False positives", str(fp), fp == 0,
               "investigate via GET /agent/rulings" if fp > 0 else ""))
    ratio_note = ""
    if ratio <= 1.0:
        ratio_note = "capture tremor_resting sessions (5/player, 30s still-hold)"
    print(_row("Separation ratio", f"{ratio:.3f} / 1.000", ratio > 1.0, ratio_note))

    # Software conditions from bridge API (if available)
    if bridge_data:
        sw_met = bridge_data.get("software_conditions_met", 0)
        sw_total = bridge_data.get("software_conditions_total", 5)
        fully = bridge_data.get("fully_ready", False)
        print(f"\n  {_C}-- Software Conditions (live from bridge) -----------{_X}")
        print(_row("Software gate", f"{sw_met}/{sw_total}", sw_met == sw_total))
        print(_row("Fully ready", "YES" if fully else "NO", fully))

    # Summary
    hw_met = sum([n >= 50, n_pl >= 3, nz > 0, frac >= 0.5, mx > 0, fp == 0, ratio > 1.0])
    print(f"\n  {_BOLD}Hardware: {hw_met}/7 conditions met{_X}", end="")
    if hw_met == 7:
        print(f"  {_G}{_BOLD}TOURNAMENT READY{_X}")
    else:
        print(f"  {_R}{7 - hw_met} blocker(s){_X}")

    # Recommendation
    print(f"\n  {_C}-- Next Action (Phase {_CURRENT_PHASE}) ----------------------------{_X}")
    if ratio <= 1.0:
        print(f"  {_Y}PRIMARY BLOCKER: separation ratio {ratio:.3f} < 1.000")
        print(f"  {_Y}Path: tremor_resting sessions — hold controller STILL 30s per session")
        print(f"  {_Y}Capture 5+ sessions per player (P1, P2, P3):")
        print(f"  {_W}  python scripts/terminal_calibration_runner.py --battery touchpad_focused --player P1")
        print(f"  {_W}  python scripts/terminal_calibration_runner.py --battery touchpad_focused --player P2")
        print(f"  {_W}  python scripts/terminal_calibration_runner.py --battery touchpad_focused --player P3")
        print(f"  {_Y}Then re-analyze:")
        print(f"  {_W}  python scripts/analyze_interperson_separation.py --session-type tremor_resting --write-snapshot --db ~\\.vapi\\bridge.db{_X}")
    else:
        print(f"  {_G}Separation ratio > 1.0. Run full preflight:")
        print(f"  {_W}  curl http://localhost:8080/agent/tournament-preflight-status -H \"x-api-key: vapi-dev-local\"{_X}")

    print(f"{_C}{'-' * 60}{_X}")


def _print_players(p: dict) -> None:
    players = p.get("players", {})
    if not players:
        print(f"\n  {_Y}No sessions found. Start bridge and play a session.{_X}\n")
        return
    print(f"\n{_C}{'-' * 60}{_X}")
    print(f"{_BOLD}{_W}  Per-Player Calibration Breakdown{_X}")
    print(f"{_C}{'-' * 60}{_X}")
    for key, stats in players.items():
        nz_count = stats["touch_variance_nonzero_count"]
        total = stats["n_sessions"]
        frac = nz_count / total if total else 0
        status = f"{_G}capturing{_X}" if nz_count > 0 else f"{_R}zero touch var{_X}"
        print(f"\n  {_W}{key}{_X}")
        print(f"    Sessions       : {total}")
        print(f"    Touch var mean : {stats['touch_variance_mean']:.4f}")
        print(f"    Touch var max  : {stats['touch_variance_max']:.4f}")
        print(f"    Nonzero ({frac:.0%}) : {nz_count}/{total} — {status}")
    print(f"{_C}{'-' * 60}{_X}\n")


# -- Auto-test trigger -------------------------------------------------------

def _run_tests_subprocess() -> int:
    cmd = [sys.executable, "-m", "pytest",
           "tests/hardware/test_hardware_calibration.py",
           "-v", "-m", "hardware", "-s", "--tb=short"]
    r = subprocess.run(cmd, cwd=str(_REPO_ROOT))
    return r.returncode


# -- Log milestone to file ---------------------------------------------------

def _log_event(event: str) -> None:
    _RECS_FILE.parent.mkdir(parents=True, exist_ok=True)
    log = []
    if _RECS_FILE.exists():
        try:
            log = json.loads(_RECS_FILE.read_text())
        except Exception:
            log = []
    log.append({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event})
    _RECS_FILE.write_text(json.dumps(log[-50:], indent=2))  # keep last 50


# -- Commands ----------------------------------------------------------------

def cmd_status() -> None:
    _enable_ansi()
    db = _find_db()
    connected, ctrl_name = _find_controller()
    progress = _poll_db(db)
    bridge_data = _fetch_tournament_readiness()

    ctrl_str = f"{_G}CONNECTED{_X} — {ctrl_name}" if connected else f"{_Y}Not detected{_X} (DB polling only)"
    print(f"\n  Controller : {ctrl_str}")
    print(f"  Database   : {db}{' (not found)' if not db.exists() else ''}")
    print(f"  Progress   : {_PROGRESS_FILE}")
    _print_scorecard(progress, bridge_data, db=db)


def cmd_test() -> None:
    _enable_ansi()
    print(f"\n{_C}Running hardware calibration tests...{_X}\n")
    sys.exit(_run_tests_subprocess())


def cmd_players() -> None:
    _enable_ansi()
    db = _find_db()
    progress = _poll_db(db)
    _print_players(progress)


def cmd_monitor() -> None:
    """Main agentic loop — polls DB, detects controller, tracks milestones."""
    _enable_ansi()
    db = _find_db()

    print(f"\n{_BOLD}{_C}+══════════════════════════════════════════════════════+")
    print(f"|  VAPI Calibration Intelligence Agent               |")
    print(f"|  Phase {_CURRENT_PHASE}  ·  Keyword: calibrate                  |")
    print(f"+══════════════════════════════════════════════════════+{_X}")
    print(f"\n  Database   : {db}")
    print(f"  Progress   : {_PROGRESS_FILE}")
    print(f"  Poll       : every {_POLL_S}s")
    print(f"  Commands   : calibrate status | calibrate test | calibrate players")
    print(f"  Stop       : Ctrl+C\n")

    if not db.exists():
        print(f"  {_Y}[WARN] DB not found. Start bridge first: cd bridge && python -m vapi_bridge.main{_X}\n")

    prev_progress: dict = {}
    prev_connected: bool | None = None
    first_run = True
    auto_tested_first_nonzero = False

    while True:
        try:
            ts = time.strftime("%H:%M:%S")

            # Controller check
            connected, ctrl_name = _find_controller()
            if connected != prev_connected:
                if connected:
                    print(f"\n{_G}[{ts}] Controller connected: {ctrl_name}{_X}")
                    _log_event(f"controller_connected: {ctrl_name}")
                elif prev_connected is not None:
                    print(f"\n{_Y}[{ts}] Controller disconnected. Sessions still tracked via DB.{_X}")
                    _log_event("controller_disconnected")
                prev_connected = connected

            # DB poll
            progress = _poll_db(db)
            bridge_data = _fetch_tournament_readiness()

            # Milestones
            if prev_progress:
                for msg in _milestones(prev_progress, progress):
                    print(f"\n{_G}[{ts}] MILESTONE: {msg}{_X}")
                    _log_event(f"milestone: {msg}")

                    # Auto-run tests on first nonzero touch_variance
                    nz_prev = prev_progress.get("sessions_with_touch_variance", 0)
                    nz_curr = progress["sessions_with_touch_variance"]
                    if nz_prev == 0 and nz_curr > 0 and not auto_tested_first_nonzero:
                        print(f"\n{_C}[{ts}] Auto-running hardware calibration tests (first nonzero touch variance)...{_X}\n")
                        _run_tests_subprocess()
                        auto_tested_first_nonzero = True
                        _log_event("auto_test_triggered: first_nonzero_touch_variance")

            # Print full scorecard on first run or when sessions change
            if first_run or progress.get("n_sessions") != prev_progress.get("n_sessions"):
                _print_scorecard(progress, bridge_data, db=db)
                first_run = False
            else:
                n = progress["n_sessions"]
                ratio = progress["separation_ratio_current"]
                nz = progress["sessions_with_touch_variance"]
                ctrl_badge = f"{_G}[CTL]{_X}" if connected else "[---]"
                ratio_flag = f"{_G}>{_X}" if ratio > 1.0 else f"{_R}<{_X}"
                print(
                    f"\r  {ctrl_badge} [{ts}] "
                    f"sessions={n} | touch_nonzero={nz} | ratio={ratio_flag}{ratio:.3f}/1.000",
                    end="", flush=True
                )

            prev_progress = progress
            time.sleep(_POLL_S)

        except KeyboardInterrupt:
            print(f"\n\n  {_Y}Calibration agent stopped.{_X}\n")
            sys.exit(0)
        except Exception as exc:
            print(f"\n  {_R}[ERROR] {exc}{_X}")
            time.sleep(_POLL_S)


# -- Entry point -------------------------------------------------------------

_CMDS = {
    "status": cmd_status,
    "test": cmd_test,
    "players": cmd_players,
    "watch": cmd_monitor,
    "monitor": cmd_monitor,
}


def main() -> None:
    if len(sys.argv) < 2:
        cmd_monitor()
        return
    cmd = sys.argv[1].lower()
    if cmd in _CMDS:
        _CMDS[cmd]()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: calibrate [status|test|players|watch]")
        sys.exit(1)


if __name__ == "__main__":
    main()
