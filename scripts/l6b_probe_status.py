"""
l6b_probe_status.py — Report L6B calibration corpus progress (N toward 50).

Reads l6b_probe_log from the bridge SQLite store (default ~/.vapi/bridge.db).

USAGE
-----
  python scripts/l6b_probe_status.py
  python scripts/l6b_probe_status.py --device-id <hex>
  python scripts/l6b_probe_status.py --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.store import Store

TARGET_N = 50


def _print_progress(progress: dict) -> None:
    valid = progress.get("valid_reflex_count", progress["probe_count"])
    indep = progress.get("independent_reflex_count", valid)
    raw = progress["probe_count"]
    target = progress.get("target_n", TARGET_N)
    # B1+B2 + independence (grok DQ-6): the gate is INDEPENDENT usable reflexes (policy-allowlist AND
    # IMU-corroborated AND in-band, then burst-deduped >=5s). Show all three so the gap between probes
    # fired, usable, and independent-usable is never hidden.
    print(f"L6B calibration corpus: N={indep} / {target} INDEPENDENT usable reflexes  "
          f"({valid} usable, {raw} raw probes fired)")
    dist = progress.get("reflex_verdict_distribution") or {}
    if dist:
        print("  reflex_verdict distribution:")
        for key in sorted(dist.keys()):
            print(f"    {key}: {dist[key]}")
    latest = progress.get("latest_probe")
    if latest:
        print(
            "  latest probe:"
            f" device={str(latest.get('device_id', ''))[:16]}..."
            f" class={latest.get('classification')}"
            f" reflex_verdict={latest.get('reflex_verdict')}"
            f" latency_ms={latest.get('latency_ms')}"
        )
    if progress.get("gate_reached"):
        print()
        print("  GATE: N>=50 reached — run operator checklist before production L6B_ENABLED.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--device-id", default=None, help="Filter to one device_id hex")
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    cfg = Config()
    db_path = args.db or cfg.db_path
    store = Store(db_path)
    progress = store.get_l6b_calibration_progress(device_id=args.device_id)

    if args.json:
        print(json.dumps(progress, indent=2))
    else:
        print(f"DB: {db_path}")
        if args.device_id:
            print(f"Device filter: {args.device_id[:16]}...")
        _print_progress(progress)

    return 0 if progress.get("independent_reflex_count",
                             progress.get("valid_reflex_count", progress["probe_count"])) < TARGET_N else 2


if __name__ == "__main__":
    raise SystemExit(main())
