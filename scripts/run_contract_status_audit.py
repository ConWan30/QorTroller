"""HWFL-1 contract-status audit runner — F-CYCLE10-1 Option (b)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from bridge.vapi_bridge.contract_status_audit import audit_contracts  # noqa: E402

DEPLOYED = ROOT / "contracts" / "deployed-addresses.json"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="HWFL-1 contract-status audit")
    p.add_argument("--cycle", type=int, default=None)
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args(argv)

    data = json.loads(DEPLOYED.read_text(encoding="utf-8"))
    report = audit_contracts(data)

    if args.out is not None:
        out_path = args.out
    else:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if args.cycle is not None:
            out_path = ROOT / "audits" / f"contract-status-cycle-{args.cycle}-{today}.md"
        else:
            out_path = ROOT / "audits" / f"contract-status-{today}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.to_markdown(), encoding="utf-8")
    print(report.to_markdown())
    print(f"\n[wrote] {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
