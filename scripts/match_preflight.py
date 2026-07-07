#!/usr/bin/env python3
"""Match preflight runner — RP-CLOSE-1 gate RP-5.

Run BEFORE every live-match `retina_capture_daemon.py start`. Gathers the evidence the
pure module (l9_presence/match_preflight.py) evaluates:
  - python process list (PowerShell CIM — catches the M11 zombie-audit-lane class)
  - CPU baseline (M12: 94.9% at failure)
  - bridge DB size (cycle-49: 5.4GB = lag)
  - capture-dir freshness (pre-M8: ring persists across sessions)
  - launch env sanity (RETINA_KILLFEED_CAPTURE_MAX)

Exit codes: 0 = GO, 1 = GO_WITH_WARNINGS, 2 = NO_GO.

Usage:
    python scripts/match_preflight.py --capture-dir retina_kf_crops_match14
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from l9_presence.match_preflight import (
    PreflightEvidence, ProcessInfo, evaluate_preflight,
)

_PS = ["powershell", "-NoProfile", "-NonInteractive", "-Command"]


def _gather_processes(ev: PreflightEvidence) -> None:
    try:
        out = subprocess.run(
            _PS + ["Get-CimInstance Win32_Process -Filter \"Name like 'python%'\" | "
                   "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"],
            capture_output=True, text=True, timeout=30)
        raw = (out.stdout or "").strip()
        if not raw:
            ev.python_processes = []
            return
        data = json.loads(raw)
        if isinstance(data, dict):
            data = [data]
        ev.python_processes = [
            ProcessInfo(pid=int(p.get("ProcessId", -1)),
                        command_line=str(p.get("CommandLine") or ""))
            for p in data
        ]
    except Exception as exc:                       # any gather failure -> UNVERIFIABLE
        ev.errors["processes"] = repr(exc)


def _gather_cpu(ev: PreflightEvidence) -> None:
    try:
        out = subprocess.run(
            _PS + ["(Get-CimInstance Win32_Processor | "
                   "Measure-Object -Property LoadPercentage -Average).Average"],
            capture_output=True, text=True, timeout=30)
        ev.cpu_percent = float((out.stdout or "").strip())
    except Exception as exc:
        ev.errors["cpu"] = repr(exc)


def _gather_db(ev: PreflightEvidence) -> None:
    db_path = os.environ.get("DB_PATH") or os.path.join(
        os.path.expanduser("~"), ".vapi", "bridge.db")
    try:
        ev.bridge_db_bytes = os.path.getsize(db_path) if os.path.isfile(db_path) else None
    except OSError as exc:
        ev.errors["db"] = repr(exc)


def _gather_capture_dir(ev: PreflightEvidence, capture_dir: str | None) -> None:
    if not capture_dir:
        ev.capture_dir_entries = None      # not specified -> treated as fresh
        return
    try:
        ev.capture_dir_entries = (os.listdir(capture_dir)
                                  if os.path.isdir(capture_dir) else None)
    except OSError as exc:
        ev.errors["capture_dir"] = repr(exc)


def main() -> int:
    ap = argparse.ArgumentParser(description="Live-match preflight gate (RP-5)")
    ap.add_argument("--capture-dir", default=None,
                    help="The --capture-dir the match will use (freshness check)")
    args = ap.parse_args()

    ev = PreflightEvidence(env=dict(os.environ))
    _gather_processes(ev)
    _gather_cpu(ev)
    _gather_db(ev)
    _gather_capture_dir(ev, args.capture_dir)

    report = evaluate_preflight(ev, self_pid=os.getpid())

    sep = "-" * 64
    print(f"\n{sep}\n  Match preflight -- verdict: {report.verdict.value}\n{sep}")
    for c in report.checks:
        print(f"  [{c.state.value:^12}] {c.name}: {c.note}")
    print(f"{sep}\n")

    return {"GO": 0, "GO_WITH_WARNINGS": 1, "NO_GO": 2}[report.verdict.value]


if __name__ == "__main__":
    sys.exit(main())
