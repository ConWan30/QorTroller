"""
cco_phase_g_measurement_status.py — CCO Phase G per-tier L6B corpus progress.

Reads l6b_probe_log grouped by cco_profile_id and maps profiles to the three
controller-class research tiers (MINIMAL_PAD / MID_TIER / PREMIUM_EDGE).

USAGE
-----
  python scripts/cco_phase_g_measurement_status.py
  python scripts/cco_phase_g_measurement_status.py --json
  python scripts/cco_phase_g_measurement_status.py --target-n 50
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.cco_controller_class_research import (
    enrich_phase_g_progress,
    parse_phase_g_deferred_tiers,
    parse_phase_g_validated_tiers,
)
from bridge.vapi_bridge.config import Config
from bridge.vapi_bridge.store import Store

_TIER_ORDER = ("MINIMAL_PAD", "MID_TIER", "PREMIUM_EDGE")

_TIER_HARDWARE = {
    "MINIMAL_PAD": "HORI Fighting Commander or other minimal-pad reference",
    "MID_TIER": "DualSense, SCUF Reflex Pro, or Xbox Elite S2",
    "PREMIUM_EDGE": "DualShock Edge (CFI-ZCP1) or Battle Beaver Edge override",
}

_TIER_CAPTURE = {
    "MINIMAL_PAD": (
        "Tag desk probes: python scripts/l6b_desk_reaction_session.py "
        "--cco-profile-id hori_fighting_commander_ps5_v1 ..."
    ),
    "MID_TIER": (
        "Tag desk probes with mid-tier profile_id, e.g. sony_dualsense_v1 "
        "or scuf_reflex_pro_v1"
    ),
    "PREMIUM_EDGE": (
        "Default Edge desk path: python scripts/l6b_desk_reaction_session.py "
        "--cco-profile-id sony_dualshock_edge_v1 ..."
    ),
}


def _next_action(tier: str, block: dict) -> str:
    if block.get("measurement_status") == "deferred":
        return block.get("deferred_reason") or (
            "Operator-deferred — no reference hardware for this tier."
        )
    n = block["probe_count"]
    target = block["target_n"]
    if block["gate_reached"]:
        return (
            f"N>={target} reached for tier — review FAR/FRR; grade may be PARTIAL "
            "(never auto VALIDATED). Operator attestation required for VALIDATED."
        )
    remaining = max(0, target - n)
    return (
        f"Need {remaining} more structured L6B probes for this tier. "
        f"Hardware: {_TIER_HARDWARE[tier]}. {_TIER_CAPTURE[tier]}"
    )


def _print_human(progress: dict) -> None:
    target = progress["target_n"]
    total = progress["total_probe_count"]
    print(f"CCO Phase G measurement corpus (target N={target} per tier)")
    print(f"  Total l6b_probe_log rows: {total}")
    untagged = progress.get("untagged_probe_count", 0)
    if untagged:
        print(
            f"  Untagged rows (excluded from tier gates): {untagged}"
            " — legacy probes; tag future captures with --cco-profile-id"
        )
    print()

    for tier in _TIER_ORDER:
        block = progress["by_tier"][tier]
        n = block["probe_count"]
        if block.get("measurement_status") == "deferred":
            gate = "DEFERRED"
        else:
            gate = "REACHED" if block["gate_reached"] else "pending"
        grade = block.get("measurement_grade", "?")
        validated = block.get("operator_validated", False)
        attestation = " operator_validated" if validated else ""
        print(f"  [{tier}] N={n}/{target} gate={gate} grade={grade}{attestation}")
        profiles = block.get("profiles") or {}
        if profiles:
            for pid in sorted(profiles.keys()):
                print(f"      {pid}: {profiles[pid]}")
        else:
            print("      (no probes)")
        print(f"    next: {_next_action(tier, block)}")
        print()

    by_profile = progress.get("by_profile_id") or {}
    if by_profile:
        print("  Totals by profile_id:")
        for pid in sorted(by_profile.keys()):
            print(f"    {pid}: {by_profile[pid]}")
        print()

    print("  Session-status: set CCO_RESEARCH_SURFACE_ENABLED=true to surface")
    print("  controller_class_research on GET /player/session-status")
    print("  Runbook: docs/cco-phase-g-measurement-runbook.md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=None, help="Override bridge DB path")
    parser.add_argument(
        "--target-n",
        type=int,
        default=50,
        help="Per-tier gate threshold (default 50)",
    )
    parser.add_argument("--json", action="store_true", help="Emit JSON only")
    args = parser.parse_args()

    cfg = Config()
    db_path = args.db or cfg.db_path
    store = Store(db_path)
    progress = store.get_cco_phase_g_corpus_progress(target_n=args.target_n)
    deferred = parse_phase_g_deferred_tiers(cfg.cco_phase_g_deferred_tiers)
    validated = parse_phase_g_validated_tiers(cfg.cco_phase_g_validated_tiers)
    if deferred or validated:
        progress = enrich_phase_g_progress(
            progress,
            deferred_tiers=deferred,
            validated_tiers=validated,
        )

    if args.json:
        print(json.dumps(progress, indent=2))
    else:
        print(f"DB: {db_path}")
        print()
        _print_human(progress)

    def _tier_satisfied(block: dict) -> bool:
        return bool(block["gate_reached"] or block.get("measurement_status") == "deferred")

    all_gates = all(_tier_satisfied(progress["by_tier"][t]) for t in _TIER_ORDER)
    return 0 if not all_gates else 2


if __name__ == "__main__":
    raise SystemExit(main())
