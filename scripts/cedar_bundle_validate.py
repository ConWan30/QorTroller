"""Phase O1 C1 — Cedar bundle CLI validator.

Pre-commit-friendly utility for validating Cedar bundle JSON files without
firing chain transactions. Loads bundle from path, runs through cedar_parser
schema validation, computes Merkle root, prints summary.

Usage:
    python scripts/cedar_bundle_validate.py <bundle_path>
    python scripts/cedar_bundle_validate.py bridge/vapi_bridge/cedar_bundles/anchor_sentry_o1_shadow_v1.json

Exit codes:
    0 — bundle is schema-valid and parsed cleanly
    1 — schema error, parse error, or file not found
"""

import json
import sys
from pathlib import Path

# Allow running from project root or scripts/ directory
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from bridge.vapi_bridge.cedar_parser import (
    CedarBundleError,
    bundle_merkle_root,
    parse_bundle,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(f"Usage: {Path(sys.argv[0]).name} <bundle_path>", file=sys.stderr)
        return 1

    bundle_path = Path(sys.argv[1])
    if not bundle_path.is_absolute():
        bundle_path = _PROJECT_ROOT / bundle_path
    if not bundle_path.exists():
        print(f"ERROR: bundle not found at {bundle_path}", file=sys.stderr)
        return 1

    try:
        with open(bundle_path, encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        print(f"ERROR: invalid JSON in {bundle_path}: {e}", file=sys.stderr)
        return 1

    try:
        parsed = parse_bundle(payload)
    except CedarBundleError as e:
        print(f"ERROR: schema validation failed: {e}", file=sys.stderr)
        return 1

    # Round-trip integrity check
    recompute = bundle_merkle_root(payload)
    if parsed.merkle_root != recompute:
        print(
            f"ERROR: Merkle root round-trip mismatch "
            f"(parser={parsed.merkle_root.hex()} recompute={recompute.hex()})",
            file=sys.stderr,
        )
        return 1

    n_permits = sum(1 for p in parsed.policies if p.effect == "permit")
    n_forbids = sum(1 for p in parsed.policies if p.effect == "forbid")
    print(f"VALID: {bundle_path.name}")
    print(f"  agent_id:      {parsed.agent_id}")
    print(f"  phase:         {parsed.phase}")
    print(f"  version:       {parsed.version}")
    print(f"  issued_at:     {parsed.issued_at_iso}")
    print(f"  lane_prefixes: {list(parsed.lane_prefixes)}")
    print(f"  policies:      {len(parsed.policies)} ({n_permits} permit + {n_forbids} forbid)")
    print(f"  Merkle root:   0x{parsed.merkle_root.hex()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
