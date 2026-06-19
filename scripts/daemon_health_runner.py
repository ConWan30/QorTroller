#!/usr/bin/env python3
"""On-demand daemon health monitor runner (D-DAEMON-2).

Fetches live values at the network/subprocess boundary and invokes the
pure-function monitor in bridge/vapi_bridge/daemon_health_monitor.py.

Usage:
  python scripts/daemon_health_runner.py
  python scripts/daemon_health_runner.py --write-audit
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "bridge"))

from vapi_bridge.daemon_health_monitor import (  # noqa: E402
    HealthMonitorInput,
    format_findings_markdown,
    run_health_monitor,
)


def _grep_device_id_conflict(repo: Path) -> bool:
    """F-FW-2 class: conflicting device_id formulas in docs vs artifacts."""
    sha_pat = re.compile(r"SHA-256\s*\(\s*pubkey\s*\|\|\s*serial", re.I)
    keccak_pat = re.compile(r"keccak256\s*\(\s*pubkey", re.I)
    hits_sha, hits_keccak = 0, 0
    for root, dirs, files in os.walk(repo):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__")]
        for fn in files:
            if not fn.endswith((".md", ".py", ".sol")):
                continue
            try:
                text = (Path(root) / fn).read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue
            if sha_pat.search(text):
                hits_sha += 1
            if keccak_pat.search(text):
                hits_keccak += 1
    return hits_sha > 0 and hits_keccak > 0


def build_input() -> HealthMonitorInput:
    device_conflict = _grep_device_id_conflict(REPO_ROOT)
    inv_live = None
    gate_script = REPO_ROOT / "scripts" / "vapi_invariant_gate.py"
    if gate_script.is_file():
        try:
            import subprocess
            r = subprocess.run(
                [sys.executable, str(gate_script), "--report"],
                cwd=str(REPO_ROOT),
                capture_output=True,
                text=True,
                timeout=120,
            )
            m = re.search(r"(\d+)\s+invariants?", r.stdout + r.stderr, re.I)
            if m:
                inv_live = int(m.group(1))
        except Exception:
            pass
    return HealthMonitorInput(
        gic_hours_since_last_link=None,
        claude_md_drift_count=0,
        frozen_ref_violation_count=0,
        invariant_count_live=inv_live,
        invariant_count_baseline=176,
        device_id_formula_conflict=device_conflict,
        ca_backup_disclosure_missing=False,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Daemon health monitor runner")
    parser.add_argument(
        "--write-audit", action="store_true",
        help="Write findings to audits/daemon-health-<date>.md",
    )
    args = parser.parse_args()
    inp = build_input()
    findings = run_health_monitor(inp)
    md = format_findings_markdown(findings)
    print(md)
    if args.write_audit:
        audits = REPO_ROOT / "audits"
        audits.mkdir(exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        out = audits / f"daemon-health-{ts}.md"
        out.write_text(md, encoding="utf-8")
        print(f"\nWrote {out}")
    print(json.dumps({"finding_count": len(findings)}, indent=2))
    return 1 if any(f.severity.value in ("HIGH", "CRITICAL") for f in findings) else 0


if __name__ == "__main__":
    raise SystemExit(main())
