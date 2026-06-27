"""Capture Cockpit — live terminal UX + monitoring for the Phase 2 consistency run.

A single read-only dashboard for the N=1 capture session: bridge health, live
retina/presence flow, presence-binding coverage, per-class window progress against
the FROZEN thresholds, and run-readiness — with hotkeys that drive the session
labeler (start/stop/relabel) so you never hand-edit JSON mid-match.

READ-ONLY against the bridge (HTTP) and the DB (sqlite mode=ro). The only thing it
writes is the local sessions manifest, via the labeler. No chain, no FROZEN, no PoAC.

    python scripts/capture_cockpit.py --device <device_id>

Hotkeys (Windows): h=start human-ranked(pending)  m=HUMAN_INPUT_MACRO  b=BOT_FULL
                   y=HUMAN_RELAY  x=stop  r=relabel  v=validate  q=quit
On non-Windows (no single-keypress), runs monitor-only; drive labels with
scripts/capture_session_labeler.py in a second terminal.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import capture_session_labeler as lab  # noqa: E402

try:
    import msvcrt  # Windows single-keypress
    _HOTKEYS = True
except ImportError:  # pragma: no cover
    _HOTKEYS = False

# FROZEN thresholds (protocol §2 — mirrored for display only; source of truth is the doc)
TPR_TARGET = 0.80
FPR_CEILING = 0.02
ELITE_WINDOWS_TARGET = 300

_C = {"g": "\033[32m", "r": "\033[31m", "y": "\033[33m", "c": "\033[36m",
      "b": "\033[1m", "d": "\033[2m", "0": "\033[0m"}


def _color(enabled: bool):
    return _C if enabled else {k: "" for k in _C}


def _get_json(url: str, headers=None, timeout=1.5):
    try:
        req = urllib.request.Request(url, headers=headers or {})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


# --- testable DB helpers (sqlite mode=ro) ----------------------------------

def _connect_ro(db_path: str) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)


def count_retina_windows(conn, device_id: str, t0: float, t1: float) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM retina_event_log WHERE device_id=? AND created_at BETWEEN ? AND ?",
        (device_id, t0, t1)).fetchone()
    return int(row[0]) if row else 0


def count_presence_probes(conn, device_id: str, t0: float, t1: float) -> int:
    row = conn.execute(
        "SELECT COUNT(*) FROM l6b_probe_log WHERE device_id=? AND probe_ts_ms BETWEEN ? AND ?",
        (device_id, int(t0 * 1000), int(t1 * 1000))).fetchone()
    return int(row[0]) if row else 0


def binding_coverage(conn, device_id: str, t0: float, t1: float, freshness_s: float):
    """Return (retina_windows, bound_windows, pct) — windows with a presence proof
    within `freshness_s` before them (the fraction that will actually fuse)."""
    rt = [float(r[0]) for r in conn.execute(
        "SELECT created_at FROM retina_event_log WHERE device_id=? AND created_at BETWEEN ? AND ? "
        "ORDER BY created_at", (device_id, t0, t1)).fetchall()]
    pt = sorted(float(r[0]) / 1000.0 for r in conn.execute(
        "SELECT probe_ts_ms FROM l6b_probe_log WHERE device_id=? AND probe_ts_ms BETWEEN ? AND ?",
        (device_id, int((t0 - freshness_s) * 1000), int(t1 * 1000))).fetchall())
    if not rt:
        return 0, 0, 0.0
    import bisect
    bound = 0
    for w in rt:
        i = bisect.bisect_right(pt, w) - 1   # most recent probe at/before w
        if i >= 0 and (w - pt[i]) <= freshness_s:
            bound += 1
    return len(rt), bound, round(100.0 * bound / len(rt), 1)


# --- rendering -------------------------------------------------------------

def _bar(n: int, target: int, width: int = 24) -> str:
    filled = min(width, int(width * n / target)) if target else 0
    return "[" + "#" * filled + "-" * (width - filled) + f"] {n}/{target}"


def render(args, C) -> str:
    mf = args.manifest
    out = []
    out.append(f"{C['b']}{C['c']}== QorTroller Capture Cockpit — Phase 2 (N=1) =={C['0']}   "
               f"{C['d']}device {args.device[:12]}..  {time.strftime('%H:%M:%S')}{C['0']}")
    out.append(f"{C['d']}FROZEN: catch>=%.2f  elite-FPR<=%.2f  elite-windows>=%d  (NCAA CFB 26 / Edge){C['0']}"
               % (TPR_TARGET, FPR_CEILING, ELITE_WINDOWS_TARGET))
    out.append("")

    # bridge
    health = _get_json(f"{args.bridge}/health")
    da = _get_json(f"{args.bridge}/operator/bridge/retina-da-status", {"x-api-key": args.api_key})
    up = health is not None
    out.append(f"BRIDGE  {(C['g']+'UP'+C['0']) if up else (C['r']+'DOWN'+C['0'])}   "
               f"retina_da_upload={da.get('retina_da_upload_enabled') if da else '?'}")

    # DB
    db_ok = os.path.exists(args.db)
    conn = None
    if db_ok:
        try:
            conn = _connect_ro(args.db)
        except Exception:
            db_ok = False
    out.append(f"DB      {(C['g']+'OK'+C['0']) if db_ok else (C['r']+'MISSING'+C['0'])}  {C['d']}{args.db}{C['0']}")
    out.append("")

    # current open session
    op = lab._open_path(mf)
    if os.path.exists(op):
        m = json.loads(open(op, encoding="utf-8").read())
        elapsed = time.time() - m["t_start"]
        out.append(f"SESSION {C['y']}{C['b']}RECORDING{C['0']} {m['class_label']}  "
                   f"elapsed {elapsed:5.0f}s")
        if conn is not None:
            rw = count_retina_windows(conn, args.device, m["t_start"], time.time())
            pp = count_presence_probes(conn, args.device, m["t_start"], time.time())
            _, bound, pct = binding_coverage(conn, args.device, m["t_start"], time.time(),
                                             m.get("presence_freshness_s", 30.0))
            cov_c = C['g'] if pct >= 60 else (C['y'] if pct >= 30 else C['r'])
            out.append(f"  live  retina_windows={rw}  presence_probes={pp}  "
                       f"binding={cov_c}{pct}%{C['0']} ({bound}/{rw} fuse)")
            if pct < 60:
                out.append(f"  {C['y']}WARN low presence coverage — fire a challenge; "
                           f"unbound windows count as UNKNOWN, not as evidence.{C['0']}")
    else:
        out.append(f"SESSION {C['d']}idle — press a class hotkey to start{C['0']}")
    out.append("")

    # per-class progress (finalized manifest entries)
    entries = lab._load(mf)
    per_class = {}
    if conn is not None:
        for e in entries:
            wn = count_retina_windows(conn, e["device_id"], e["t_start"], e["t_end"])
            per_class[e["class_label"]] = per_class.get(e["class_label"], 0) + wn
    out.append(f"{C['b']}captured windows by class:{C['0']}")
    for cl in ("HUMAN_CLEAN", "PRO_SKILL", "HUMAN_INPUT_MACRO", "HUMAN_RELAY", "BOT_FULL", "PENDING"):
        n = per_class.get(cl, 0)
        if cl == "PRO_SKILL":
            out.append(f"  {cl:<18} {_bar(n, ELITE_WINDOWS_TARGET)}")
        elif cl == "PENDING" and n == 0 and not any(e['class_label'] == 'PENDING' for e in entries):
            continue
        else:
            out.append(f"  {cl:<18} {n}")
    out.append("")

    # run readiness
    issues = lab.validate(mf)
    if not issues:
        out.append(f"READY   {C['g']}manifest run-ready ({len(entries)} sessions){C['0']}")
    else:
        out.append(f"READY   {C['y']}{len(issues)} issue(s) — relabel PENDING before running{C['0']}")
    out.append("")

    if _HOTKEYS:
        out.append(f"{C['d']}[h]uman-ranked [m]acro [b]ot [y]relay  [x]stop  [r]elabel  [v]alidate  [q]uit{C['0']}")
    else:
        out.append(f"{C['d']}monitor-only (no hotkeys on this OS); use capture_session_labeler.py to control{C['0']}")
    if conn is not None:
        conn.close()
    return "\n".join(out)


# --- interactive loop ------------------------------------------------------

def _handle_key(ch: str, args) -> bool:
    """Return False to quit."""
    mf = args.manifest
    starts = {"m": "HUMAN_INPUT_MACRO", "b": "BOT_FULL", "y": "HUMAN_RELAY"}
    try:
        if ch == "q":
            return False
        if ch == "h":
            lab.start_session(mf, args.device, "PENDING", args.freshness)
        elif ch in starts:
            lab.start_session(mf, args.device, starts[ch], args.freshness)
        elif ch == "x":
            lab.stop_session(mf)
        elif ch == "v":
            issues = lab.validate(mf)
            print("\n" + ("OK — run-ready" if not issues else "\n".join(issues)))
            time.sleep(1.5)
        elif ch == "r":
            sys.stdout.write("\n relabel index: ")
            sys.stdout.flush()
            idx = int(sys.stdin.readline().strip())
            sys.stdout.write(" class [PRO_SKILL/HUMAN_CLEAN]: ")
            sys.stdout.flush()
            cl = sys.stdin.readline().strip()
            lab.relabel(mf, idx, cl)
    except Exception as exc:
        print(f"\n  ! {exc}")
        time.sleep(1.5)
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Phase 2 capture cockpit")
    ap.add_argument("--device", required=True)
    ap.add_argument("--db", default=os.path.expanduser("~/.vapi/bridge.db"))
    ap.add_argument("--manifest", default=lab.DEFAULT_MANIFEST)
    ap.add_argument("--bridge", default="http://127.0.0.1:8000")
    ap.add_argument("--api-key", default="vapi-dev-local")
    ap.add_argument("--freshness", type=float, default=lab.DEFAULT_FRESHNESS_S)
    ap.add_argument("--refresh", type=float, default=2.0)
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--once", action="store_true", help="render one frame and exit (smoke/test)")
    args = ap.parse_args(argv)
    C = _color(not args.no_color and sys.stdout.isatty())

    if args.once:
        print(render(args, C))
        return 0

    try:
        while True:
            sys.stdout.write("\033[2J\033[H")  # clear + home
            sys.stdout.write(render(args, C) + "\n")
            sys.stdout.flush()
            deadline = time.time() + args.refresh
            while time.time() < deadline:
                if _HOTKEYS and msvcrt.kbhit():
                    ch = msvcrt.getch().decode(errors="ignore").lower()
                    if not _handle_key(ch, args):
                        return 0
                    break
                time.sleep(0.05)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
