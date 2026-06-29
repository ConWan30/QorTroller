"""Auto-detect Remote Play and gate the capture daemon — so the operator just plays; capture follows.

Watches for the PS Remote Play process: when it appears (you start a session) -> auto-start the capture
daemon; when it exits (you close it) -> stop + harvest + (optionally) calibrate against a genuine corpus.
RemotePlay.exe running is a clean play/idle signal (you only open it to play). Run in the background so a
single session (open -> spectate/play -> close) self-completes with no coordination.

Advisory presence calibration only; no chain / IOTX / FROZEN-v1 / PoAC.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

_DAEMON = Path(__file__).resolve().parent / "retina_capture_daemon.py"
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0   # CREATE_NO_WINDOW — never pop a console window


def decide(running: bool, capturing: bool, idle_elapsed_s: float, idle_grace_s: float) -> str:
    """Pure transition decision (testable): 'start' when Remote Play appears and we're not capturing;
    'stop' when it has been gone past the idle grace while capturing; else 'none'."""
    if running and not capturing:
        return "start"
    if (not running) and capturing and idle_elapsed_s >= idle_grace_s:
        return "stop"
    return "none"


def remoteplay_running() -> bool:
    """True iff PS Remote Play (RemotePlay.exe) is running. Windows tasklist; fail-safe to False."""
    try:
        out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq RemotePlay.exe", "/NH"],
                             capture_output=True, text=True, timeout=10, creationflags=_NO_WINDOW).stdout
        return "RemotePlay" in out
    except Exception:
        return False


def _run_daemon(*daemon_args) -> str:
    r = subprocess.run([sys.executable, str(_DAEMON), *daemon_args], capture_output=True, text=True,
                       creationflags=_NO_WINDOW)
    return (r.stdout or "") + (("\n" + r.stderr) if r.stderr else "")


def _corpus_from_summary(stop_out: str):
    """Parse the corpus filename from the daemon stop SUMMARY JSON (best-effort)."""
    i = stop_out.find("{")
    if i < 0:
        return None
    try:
        return json.loads(stop_out[i:]).get("corpus")
    except Exception:
        return None


def main() -> int:
    ap = argparse.ArgumentParser(description="auto-detect Remote Play and gate the capture daemon")
    ap.add_argument("--label", default="genuine")
    ap.add_argument("--monitor", type=int, default=1)
    ap.add_argument("--diag-every", type=int, default=4)
    ap.add_argument("--genuine", default=None, help="genuine corpus to calibrate against at session end")
    ap.add_argument("--poll", type=float, default=5.0, help="poll seconds")
    ap.add_argument("--idle-grace", type=float, default=30.0, help="s Remote Play must be gone before stopping")
    ap.add_argument("--once", action="store_true", help="exit after the first session completes")
    a = ap.parse_args()

    capturing = False
    idle_since = None
    print(f"[auto] watching for Remote Play (label={a.label}) — open PS Remote Play to begin capture.",
          flush=True)
    while True:
        running = remoteplay_running()
        if running:
            idle_since = None
        elif capturing and idle_since is None:
            idle_since = time.time()
        idle_elapsed = (time.time() - idle_since) if idle_since else 0.0
        action = decide(running, capturing, idle_elapsed, a.idle_grace)

        if action == "start":
            print("[auto] Remote Play DETECTED -> starting capture", flush=True)
            out = _run_daemon("start", "--label", a.label, "--monitor", str(a.monitor),
                              "--diag-every", str(a.diag_every))
            print(out.strip(), flush=True)
            capturing = "CAPTURE LIVE" in out   # only mark capturing on a confirmed start (no re-spawn loop)
        elif action == "stop":
            print("[auto] Remote Play CLOSED -> stopping + harvesting", flush=True)
            stop_out = _run_daemon("stop", "--label", a.label)
            print(stop_out.strip(), flush=True)
            capturing = False
            idle_since = None
            if a.genuine:
                forged = _corpus_from_summary(stop_out)
                if forged and Path(forged).exists() and Path(a.genuine).exists():
                    print(f"[auto] calibrating {a.genuine} (genuine) vs {forged} (forged) ...", flush=True)
                    print(_run_daemon("calibrate", "--genuine", a.genuine, "--forged", forged).strip(),
                          flush=True)
                else:
                    print(f"[auto] calibration skipped (genuine={a.genuine} forged={forged})", flush=True)
            if a.once:
                print("[auto] --once: session complete, exiting watcher.", flush=True)
                return 0
        time.sleep(a.poll)


if __name__ == "__main__":
    raise SystemExit(main())
