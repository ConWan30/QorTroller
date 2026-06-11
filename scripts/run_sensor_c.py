"""HWFL-1 Sensor C one-shot runner.

Assembles a rung-gate readiness ledger and writes:
  - audits/rung-gate-ledger-cycle-<N>-<YYYY-MM-DD>.md
  - audits/rung-gate-ledger-latest.json  (rolling machine-readable snapshot)

Usage:
    python scripts/run_sensor_c.py                     # Cycle 2, today
    python scripts/run_sensor_c.py --cycle 3
    python scripts/run_sensor_c.py --stdout            # markdown -> stdout, no files
"""
from __future__ import annotations

import argparse
import datetime as _dt
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

from bridge.vapi_bridge.sensor_c_rung_ledger import assemble_ledger  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Run HWFL-1 Sensor C — rung-gate readiness ledger")
    p.add_argument("--cycle", type=int, default=2)
    p.add_argument("--date", default=_dt.date.today().isoformat())
    p.add_argument("--stdout", action="store_true")
    args = p.parse_args(argv)

    ledger = assemble_ledger(_REPO_ROOT, cycle=args.cycle, cycle_date=args.date)

    if args.stdout:
        print(ledger.to_markdown())
        return 0

    out_dir = _REPO_ROOT / "audits"
    out_dir.mkdir(exist_ok=True)
    md_path = out_dir / f"rung-gate-ledger-cycle-{args.cycle}-{args.date}.md"
    json_path = out_dir / "rung-gate-ledger-latest.json"

    md_path.write_text(ledger.to_markdown(), encoding="utf-8")
    json_path.write_text(ledger.to_json(), encoding="utf-8")

    counts = ledger.state_counts()
    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    print(f"Sensor C Cycle {args.cycle}: {len(ledger.results)} gates ({summary})")
    print(f"  markdown -> {md_path}")
    print(f"  json     -> {json_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
