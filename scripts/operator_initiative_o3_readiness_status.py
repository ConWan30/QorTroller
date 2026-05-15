"""Phase O5 Priority 4 — Operator Initiative O2→O3 graduation readiness status.

Wallet-free, READ-ONLY observability CLI for the calendar-bound O3 ACTING
graduation. The plan (.claude/plans/rustling-soaring-rossum.md) says
Priority 4 is "calendar-bound observation work running concurrently" — this
script is the operator-facing surface that makes the calendar-gated state
re-queryable without launching the bridge.

What it computes:
  • Per agent (anchor_sentry / guardian / curator):
      - current phase + shadow_age_hours
      - days until shadow_age >= 504h (PHASE_O2_SHADOW_MIN_HOURS or
        PHASE_O3_SUGGEST_MIN_HOURS — both 504h, mapped per agent's
        current phase)
      - O2 SUGGEST ready? (gate set per *_o2_suggest_v1.json bundles)
      - O3 ACTING ready? (gate set per *_o3_acting_v1.json bundles —
        draft count, disagreement rate, false-positive rate Curator-only,
        operator flag presence: dual_key / KMS-HSM / GitHub-App OAuth /
        marketplace setCurator role)
      - calendar projection of NEXT gate clearance per agent
  • Cross-agent rollup:
      - fleet_phase_aligned (all 3 at same phase?)
      - next_alignment_target (what phase the fleet is converging on)
      - earliest_fleet_o3_ready_date (latest projected clear across the 3)
      - parallel_o3_act_anchor.py Gate 4 (watcher veto): currently
        BLOCKED / READY-TO-FIRE / PARTIAL (some agents ready, others not)

WALLET-FREE CONTRACT (matches scripts/zkba_post_ceremony_audit.py):
  • No transaction submission paths invoked.
  • No chain RPC calls (Watcher state lives entirely in local SQLite).
  • No env-var changes.
  • No file mutation outside the optional --json output.
  • CHAIN_SUBMISSION_PAUSED state untouched.

Operator usage:
    python scripts/operator_initiative_o3_readiness_status.py
    python scripts/operator_initiative_o3_readiness_status.py --json
    python scripts/operator_initiative_o3_readiness_status.py --db PATH

Exit codes:
  0  Fleet READY-TO-FIRE  — parallel_o3_act_anchor.py --confirm is
                            authorized per Gate 4 (watcher veto)
  1  Fleet BLOCKED        — at least one agent has an O2 or O3 blocker
                            that has not yet cleared (calendar OR
                            engineering OR operator-flag gated)
  2  PARTIAL              — split phase (agents not on the same rung
                            of the ladder); parallel-fleet invariant
                            says all three must advance together
  3  ERROR                — Config/Store init failure or watcher raised
                            (preserves Verification-First Discipline:
                            operator inspects the error message rather
                            than acting on a partial signal)

Author: VAPI Architect — ships under the Priority 4 envelope of the
plan dated 2026-05-14 (rustling-soaring-rossum). Mirrors the
scripts/zkba_post_ceremony_audit.py shape (D-TRACK2-G6 audit pattern).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))


# ---------------------------------------------------------------------------
# Constants — mirrored from operator_initiative_advancement.py FROZEN values.
# Re-defined here so the audit CLI surfaces the gate values inline in its
# own output without round-tripping through the watcher module's import.
# Any drift in these constants between this file and the watcher module is
# itself a finding (Mythos-Frozen-class drift; tracked by INV-OPERATOR-AGENT-*
# under Stream 4 PV-CI ceremony).
# ---------------------------------------------------------------------------
PHASE_O2_SHADOW_MIN_HOURS = 504
PHASE_O3_SUGGEST_MIN_HOURS = 504
PHASE_O2_EVAL_MIN_COUNT = 100
PHASE_O3_DRAFT_PAYLOAD_MIN = 50
PHASE_O3_DISAGREEMENT_RATE_MAX = 0.05
PHASE_O3_FALSE_POSITIVE_RATE_MAX = 0.0


# ---------------------------------------------------------------------------
# Calendar-projection helpers
# ---------------------------------------------------------------------------

def _projected_gate_clear_date(
    *,
    shadow_age_hours: float,
    target_hours: int,
    now_unix: float,
) -> Dict[str, Any]:
    """Project when shadow_age will reach the target threshold.

    Returns a dict with hours_remaining, days_remaining, and the projected
    Unix timestamp + ISO string. If already cleared, hours_remaining=0
    and projected_unix=now.
    """
    if shadow_age_hours >= target_hours:
        return {
            "cleared":            True,
            "hours_remaining":    0.0,
            "days_remaining":     0.0,
            "projected_unix":     float(now_unix),
            "projected_iso":      time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_unix)
            ),
        }
    hours_remaining = float(target_hours) - shadow_age_hours
    projected_unix = float(now_unix) + (hours_remaining * 3600.0)
    return {
        "cleared":            False,
        "hours_remaining":    hours_remaining,
        "days_remaining":     hours_remaining / 24.0,
        "projected_unix":     projected_unix,
        "projected_iso":      time.strftime(
            "%Y-%m-%dT%H:%M:%SZ", time.gmtime(projected_unix)
        ),
    }


def _agent_to_dict(agent_readiness: Any, now_unix: float) -> Dict[str, Any]:
    """Render one agent's readiness as a JSON-serializable dict + calendar
    projection. Reaches into the AgentAdvancementReadiness slotted dataclass."""
    target_hours = (
        PHASE_O2_SHADOW_MIN_HOURS
        if agent_readiness.current_phase == "O1_SHADOW"
        else PHASE_O3_SUGGEST_MIN_HOURS
    )
    projection = _projected_gate_clear_date(
        shadow_age_hours=agent_readiness.shadow_age_hours,
        target_hours=target_hours,
        now_unix=now_unix,
    )
    return {
        "agent_id":                              agent_readiness.agent_id,
        "current_phase":                         agent_readiness.current_phase,
        "shadow_age_hours":                      round(agent_readiness.shadow_age_hours, 1),
        "shadow_age_days":                       round(agent_readiness.shadow_age_hours / 24.0, 2),
        "cedar_eval_count":                      agent_readiness.cedar_eval_count,
        "bundle_hash_drift_count_30d":           agent_readiness.bundle_hash_drift_count_30d,
        "scope_hash_governance_drift_count_30d": agent_readiness.scope_hash_governance_drift_count_30d,
        "o2_ready":                              agent_readiness.o2_ready,
        "o2_blockers":                           list(agent_readiness.o2_blockers),
        "o3_ready":                              agent_readiness.o3_ready,
        "o3_blockers":                           list(agent_readiness.o3_blockers),
        "next_gate_target_hours":                target_hours,
        "next_gate_projection":                  projection,
        "error":                                 agent_readiness.error,
    }


# ---------------------------------------------------------------------------
# Audit orchestration
# ---------------------------------------------------------------------------

def run_audit(db_path: str) -> Dict[str, Any]:
    """Run the readiness audit. Returns a dict with per_agent + rollup.

    NEVER raises — wraps Store + Config construction in try/except. Caller
    inspects result['error'] to detect partial failure (matches the
    operator_initiative_advancement watcher's INV-INITIATIVE-ADVANCEMENT-002
    fail-open contract).
    """
    now_unix = time.time()
    result: Dict[str, Any] = {
        "timestamp_iso":          time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_unix)),
        "timestamp_unix":         now_unix,
        "db_path":                str(db_path),
        "gate_thresholds": {
            "shadow_age_min_hours":           PHASE_O2_SHADOW_MIN_HOURS,
            "o2_suggest_min_hours":           PHASE_O3_SUGGEST_MIN_HOURS,
            "draft_payload_min":              PHASE_O3_DRAFT_PAYLOAD_MIN,
            "disagreement_rate_max":          PHASE_O3_DISAGREEMENT_RATE_MAX,
            "false_positive_rate_max":        PHASE_O3_FALSE_POSITIVE_RATE_MAX,
        },
        "per_agent":              [],
        "rollup":                 {},
        "error":                  None,
    }
    try:
        # Defer heavy imports until inside the try so a Store import failure
        # surfaces as result.error rather than a CLI traceback.
        from vapi_bridge.config import Config
        from vapi_bridge.store import Store
        from vapi_bridge.operator_initiative_advancement import (
            evaluate_fleet_advancement_sync,
            INITIATIVE_AGENTS,
        )

        # Read-only Store construction; Config from env (operator flags
        # like operator_dual_key_present / kms_hsm_production_ready are
        # read from env on init).
        store = Store(db_path=db_path)
        cfg = Config()

        summary = evaluate_fleet_advancement_sync(cfg=cfg, store=store)
        if summary.error:
            result["error"] = f"watcher_error: {summary.error}"
            return result

        result["per_agent"] = [
            _agent_to_dict(a, now_unix) for a in summary.per_agent
        ]
        # Compute the latest projected gate clearance — this is when the
        # FLEET (parallel-alignment invariant) is earliest possibly ready.
        earliest_fleet_o3_ready_unix = max(
            (
                a["next_gate_projection"]["projected_unix"]
                for a in result["per_agent"]
                if a["next_gate_projection"] is not None
            ),
            default=now_unix,
        )
        # Gate 4 (parallel_o3_act_anchor.py watcher veto): fires only when
        # ALL three agents are o3_ready=True simultaneously.
        all_o3_ready = (
            len(result["per_agent"]) == 3
            and all(a["o3_ready"] for a in result["per_agent"])
        )
        any_blocked = any(
            (not a["o2_ready"]) and (not a["o3_ready"])
            for a in result["per_agent"]
        )
        result["rollup"] = {
            "fleet_size":                       summary.fleet_size,
            "fleet_at_o1_count":                summary.fleet_at_o1_count,
            "fleet_at_o2_ready_count":          summary.fleet_at_o2_ready_count,
            "fleet_at_o3_ready_count":          summary.fleet_at_o3_ready_count,
            "fleet_phase_aligned":              summary.fleet_phase_aligned,
            "next_alignment_target":            summary.next_alignment_target,
            "earliest_fleet_o3_ready_unix":     earliest_fleet_o3_ready_unix,
            "earliest_fleet_o3_ready_iso":      time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(earliest_fleet_o3_ready_unix)
            ),
            "parallel_o3_anchor_gate4":         (
                "READY_TO_FIRE" if all_o3_ready
                else "BLOCKED" if any_blocked
                else "PARTIAL_PROGRESS"
            ),
        }
        return result
    except Exception as exc:  # noqa: BLE001 — fail-open per design
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


# ---------------------------------------------------------------------------
# Pretty-print
# ---------------------------------------------------------------------------

def _format_human_report(audit: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("Operator Initiative O2 -> O3 Graduation Readiness Status")
    lines.append(f"  Audit time: {audit['timestamp_iso']}")
    lines.append(f"  DB path:    {audit['db_path']}")
    lines.append("=" * 72)
    if audit.get("error"):
        lines.append(f"ERROR: {audit['error']}")
        return "\n".join(lines)

    gt = audit["gate_thresholds"]
    lines.append("FROZEN gate thresholds:")
    lines.append(f"  shadow_age_min_hours   = {gt['shadow_age_min_hours']} h (~21 days)")
    lines.append(f"  o2_suggest_min_hours   = {gt['o2_suggest_min_hours']} h (~21 days)")
    lines.append(f"  draft_payload_min      = {gt['draft_payload_min']}")
    lines.append(f"  disagreement_rate_max  = {gt['disagreement_rate_max']}")
    lines.append(f"  false_positive_rate_max= {gt['false_positive_rate_max']} (Curator-only; ZERO TOLERANCE)")
    lines.append("")

    lines.append("Per-agent readiness:")
    for a in audit["per_agent"]:
        lines.append(f"  agent: {a['agent_id']}")
        lines.append(f"    phase                = {a['current_phase']}")
        lines.append(
            f"    shadow_age           = {a['shadow_age_hours']:.1f} h "
            f"({a['shadow_age_days']:.2f} d)"
        )
        lines.append(f"    cedar_eval_count     = {a['cedar_eval_count']}")
        lines.append(f"    bundle_hash_drift_30d= {a['bundle_hash_drift_count_30d']}")
        lines.append(
            f"    scope_drift_30d      = {a['scope_hash_governance_drift_count_30d']}"
        )
        proj = a["next_gate_projection"]
        if proj["cleared"]:
            lines.append(
                f"    next-gate shadow_age = CLEARED (>= {a['next_gate_target_hours']} h)"
            )
        else:
            lines.append(
                f"    next-gate shadow_age = NOT CLEARED — "
                f"{proj['days_remaining']:.2f} d remaining "
                f"(projected: {proj['projected_iso']})"
            )
        lines.append(f"    o2_ready             = {a['o2_ready']}")
        if a["o2_blockers"]:
            for b in a["o2_blockers"]:
                lines.append(f"      O2 blocker: {b}")
        lines.append(f"    o3_ready             = {a['o3_ready']}")
        if a["o3_blockers"]:
            for b in a["o3_blockers"]:
                lines.append(f"      O3 blocker: {b}")
        if a["error"]:
            lines.append(f"    ERROR: {a['error']}")
        lines.append("")

    r = audit["rollup"]
    lines.append("Fleet rollup:")
    lines.append(f"  fleet_size                  = {r['fleet_size']}")
    lines.append(f"  fleet_at_o1_count           = {r['fleet_at_o1_count']}")
    lines.append(f"  fleet_at_o2_ready_count     = {r['fleet_at_o2_ready_count']}")
    lines.append(f"  fleet_at_o3_ready_count     = {r['fleet_at_o3_ready_count']}")
    lines.append(f"  fleet_phase_aligned         = {r['fleet_phase_aligned']}")
    lines.append(f"  next_alignment_target       = {r['next_alignment_target']}")
    lines.append(f"  earliest_fleet_o3_ready_iso = {r['earliest_fleet_o3_ready_iso']}")
    lines.append(f"  parallel_o3_anchor_gate4    = {r['parallel_o3_anchor_gate4']}")
    lines.append("")

    g4 = r["parallel_o3_anchor_gate4"]
    if g4 == "READY_TO_FIRE":
        lines.append("VERDICT: READY-TO-FIRE — operator may invoke")
        lines.append("         scripts/parallel_o3_act_anchor.py --confirm")
        lines.append("         (triple-gate authorization still required:")
        lines.append("          CHAIN_SUBMISSION_PAUSED=false +")
        lines.append("          OPERATOR_INITIATIVE_O3_AUTHORIZED=true +")
        lines.append("          --confirm CLI flag)")
    elif g4 == "BLOCKED":
        lines.append("VERDICT: BLOCKED — at least one agent has an unresolved")
        lines.append("         O2 or O3 blocker. See per-agent details above.")
    else:
        lines.append("VERDICT: PARTIAL_PROGRESS — calendar-bound; recheck after")
        lines.append("         the earliest_fleet_o3_ready_iso timestamp above.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI entry
# ---------------------------------------------------------------------------

def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator Initiative O2 -> O3 graduation readiness audit (wallet-free, read-only)."
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "bridge" / "vapi_store.db"),
        help="Path to the bridge SQLite DB (defaults to bridge/vapi_store.db).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of the human report.",
    )
    args = parser.parse_args(argv)

    audit = run_audit(args.db)
    if args.json:
        print(json.dumps(audit, indent=2, default=str))
    else:
        print(_format_human_report(audit))

    if audit.get("error"):
        return 3
    g4 = (audit.get("rollup", {}) or {}).get("parallel_o3_anchor_gate4")
    if g4 == "READY_TO_FIRE":
        return 0
    if g4 == "BLOCKED":
        return 1
    return 2  # PARTIAL_PROGRESS


if __name__ == "__main__":
    sys.exit(main())
