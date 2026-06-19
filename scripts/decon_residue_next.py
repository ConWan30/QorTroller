#!/usr/bin/env python3
"""Print the next pending DECON-1 residue item from decon_residue_queue.json."""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
QUEUE = REPO_ROOT / "docs" / "_daemon_proposals" / "decon_residue_queue.json"


def main() -> int:
    if not QUEUE.is_file():
        print(f"Missing {QUEUE}", file=sys.stderr)
        return 1
    data = json.loads(QUEUE.read_text(encoding="utf-8"))
    pending = [i for i in data.get("items", []) if i.get("status") == "pending"]
    pending.sort(key=lambda x: x.get("order", 999))
    if not pending:
        print("No pending residue items.")
        return 0
    nxt = pending[0]
    print(f"Next: {nxt['id']}")
    print(f"  domain: {nxt.get('domain')}")
    print(f"  target: {nxt.get('target_file')}")
    print(f"  order:  {nxt.get('order')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
