#!/usr/bin/env python3
"""
QorTroller rig health battery
=============================
One command for the AGENTS.md baseline health checks, with a
machine-readable summary the Buzz bot can digest-post later.

  python scripts/rig_health.py                 # full battery (incl. pytest collection)
  python scripts/rig_health.py --quick         # fast checks only (no collection)
  python scripts/rig_health.py --with-devices  # also verify config/rig_devices.json

Writes logs/health.json (gitignored runtime dir). Exit 1 on any failure.

Checks (AGENTS.md 'Baseline health commands' + split-budget guard):
  invariant_gate   scripts/vapi_invariant_gate.py must PASS at 188
  smoke_imports    qortroller / qortroller_daemon / qortroller_memory import
  oracle           retina VisualOracleConfig loads, reports nim_model
  shell_false      shell=False hardening still present in qortroller source
  monolith_budget  qortroller.py line count within budget (prevents the
                   extracted modules from quietly re-accumulating there)
  hygiene          scripts/repo_hygiene.py --check
  collect          (full only) bridge/tests collection vs baseline tolerances
  devices          (opt-in) rig map names verified via ffmpeg listing

Tolerances (deliberately explicit, fail-closed on regressions):
  collected >= 6400  (~6748 baseline minus 5% growth headroom)
  import errors <= 4 (quantcrypt / llm_routing.local_client are known env debt)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HEALTH_JSON = REPO_ROOT / "logs" / "health.json"

INVARIANT_EXPECTED = 188
COLLECTED_MIN = 6400
IMPORT_ERRORS_MAX = 4
MONOLITH_BUDGET = 2550  # qortroller.py after the qortroller_memory extraction (2513)


def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run(
        cmd, cwd=REPO_ROOT, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


def check_invariant_gate(results: list[dict]) -> None:
    p = _run([sys.executable, "scripts/vapi_invariant_gate.py"], timeout=300)
    m = re.search(r"(\d+) invariants verified", p.stdout)
    ok = p.returncode == 0 and m and int(m.group(1)) == INVARIANT_EXPECTED
    results.append({"name": "invariant_gate", "status": "pass" if ok else "fail",
                    "detail": (m.group(0) if m else p.stdout.strip()[-200:]) or p.stderr.strip()[-200:]})


def check_smoke_imports(results: list[dict]) -> None:
    code = "import qortroller, qortroller_daemon, qortroller_memory; print('ok')"
    p = _run([sys.executable, "-c", code])
    results.append({"name": "smoke_imports", "status": "pass" if p.returncode == 0 else "fail",
                    "detail": p.stdout.strip() or p.stderr.strip()[-300:]})


def check_oracle(results: list[dict]) -> None:
    code = ("import sys; sys.path.insert(0, 'bridge'); "
            "from vapi_bridge.retina_visual_oracle import VisualOracleConfig; "
            "print('oracle', VisualOracleConfig().nim_model)")
    p = _run([sys.executable, "-c", code])
    results.append({"name": "oracle", "status": "pass" if p.returncode == 0 else "fail",
                    "detail": p.stdout.strip() or p.stderr.strip()[-300:]})


def check_shell_false(results: list[dict]) -> None:
    code = ("import inspect, qortroller; s = inspect.getsource(qortroller); "
            "assert 'shell=False' in s; print('shell-False OK')")
    p = _run([sys.executable, "-c", code])
    results.append({"name": "shell_false", "status": "pass" if p.returncode == 0 else "fail",
                    "detail": p.stdout.strip() or p.stderr.strip()[-300:]})


def check_monolith_budget(results: list[dict]) -> None:
    n = len((REPO_ROOT / "qortroller.py").read_text(encoding="utf-8").splitlines())
    results.append({"name": "monolith_budget",
                    "status": "pass" if n <= MONOLITH_BUDGET else "fail",
                    "detail": f"qortroller.py {n} lines (budget {MONOLITH_BUDGET})"})


def check_hygiene(results: list[dict]) -> None:
    p = _run([sys.executable, "scripts/repo_hygiene.py", "--check"])
    results.append({"name": "hygiene", "status": "pass" if p.returncode == 0 else "fail",
                    "detail": p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()[-200:]})


def check_collect(results: list[dict]) -> None:
    p = _run([sys.executable, "-m", "pytest", "bridge/tests", "--collect-only", "-q"],
             timeout=600)
    m = re.search(r"(\d+) tests? collected(?:, (\d+) errors?)?", p.stdout)
    if not m:
        results.append({"name": "collect", "status": "fail",
                        "detail": (p.stdout.strip()[-200:] or p.stderr.strip()[-200:])})
        return
    collected, errors = int(m.group(1)), int(m.group(2) or 0)
    ok = collected >= COLLECTED_MIN and errors <= IMPORT_ERRORS_MAX
    results.append({"name": "collect", "status": "pass" if ok else "fail",
                    "detail": f"{collected} collected, {errors} import errors "
                              f"(tolerance >={COLLECTED_MIN}, <={IMPORT_ERRORS_MAX})"})


def check_devices(results: list[dict]) -> None:
    p = _run([sys.executable, "scripts/verify_rig_devices.py"], timeout=60)
    results.append({"name": "devices", "status": "pass" if p.returncode == 0 else "fail",
                    "detail": p.stdout.strip().splitlines()[-1] if p.stdout.strip() else p.stderr.strip()[-200:]})


def main() -> int:
    ap = argparse.ArgumentParser(description="QorTroller rig health battery")
    ap.add_argument("--quick", action="store_true", help="skip pytest collection")
    ap.add_argument("--with-devices", action="store_true",
                    help="verify rig device map via ffmpeg listing")
    args = ap.parse_args()

    results: list[dict] = []
    check_invariant_gate(results)
    check_smoke_imports(results)
    check_oracle(results)
    check_shell_false(results)
    check_monolith_budget(results)
    check_hygiene(results)
    if args.with_devices:
        check_devices(results)
    if not args.quick:
        check_collect(results)

    failed = [r for r in results if r["status"] == "fail"]
    report = {
        "generated": int(time.time()),
        "mode": "quick" if args.quick else "full",
        "overall": "fail" if failed else "pass",
        "checks": results,
    }
    HEALTH_JSON.parent.mkdir(parents=True, exist_ok=True)
    HEALTH_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    for r in results:
        mark = {"pass": "ok  ", "fail": "FAIL", "skip": "skip"}[r["status"]]
        print(f"[{mark}] {r['name']}: {r['detail']}")
    print(f"\noverall: {report['overall']}  ({len(results) - len(failed)}/{len(results)} passed)")
    print(f"json: {HEALTH_JSON.relative_to(REPO_ROOT)}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
