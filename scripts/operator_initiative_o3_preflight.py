"""Operator Initiative O3 Graduation — comprehensive preflight checklist.

Extends scripts/operator_initiative_o3_readiness_status.py (Priority 4)
with the full O3-gate surface visible in one query:

  Calendar gate (FROZEN — cannot expedite):
    shadow_age >= 504h (~21 days) per agent

  Operator-clearable gates (can be cleared TODAY in parallel with the
  shadow_age countdown — that's the expedite path):
    draft_payload_count >= 50 per agent (Phase O2-DRAFT-GENERATION
        primitives can populate this; see seed_drafts.py)
    disagreement_rate < 5% per agent (operator review pipeline)
    false_positive_rate = 0 (Curator-only; ZERO TOLERANCE)
    operator_dual_key_present (all 3 agents)
    kms_hsm_production_ready (Sentry + Guardian)
    github_app_oauth_tokens_valid (Guardian-only)
    marketplace_curator_role_assigned (Curator-only)

Wallet-free; READ-ONLY; never writes to DB; no chain RPC.

Output: human report (default) or --json. Exit codes mirror the
Priority 4 readiness audit (0=READY/1=BLOCKED/2=PARTIAL/3=ERROR) +
adds an additional --strict mode that returns 1 unless ALL gates clear
(including cfg flags — useful for ceremony preflight just before firing
parallel_o3_act_anchor.py).

Operator usage:
    python scripts/operator_initiative_o3_preflight.py
    python scripts/operator_initiative_o3_preflight.py --json
    python scripts/operator_initiative_o3_preflight.py --db PATH
    python scripts/operator_initiative_o3_preflight.py --strict

This is the operator's daily-check surface for the calendar window
(~9-16 days from 2026-05-15 to shadow_age=504h clearance).
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

# Windows cp1252 stdout encoding fix (Phase 237.5 Path C+ precedent) —
# the human-readable report uses ✓/✗/⚡ Unicode characters; force UTF-8
# encoding so the report renders cleanly on Windows PowerShell.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001 — non-Windows platforms ignore
    pass


def _projected_clear(hours_remaining: float, now_unix: float) -> Dict[str, Any]:
    if hours_remaining <= 0:
        return {"cleared": True, "days_remaining": 0.0,
                "projected_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                               time.gmtime(now_unix))}
    proj_unix = now_unix + (hours_remaining * 3600.0)
    return {
        "cleared": False,
        "days_remaining": hours_remaining / 24.0,
        "projected_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                       time.gmtime(proj_unix)),
    }


def _resolve_cfg_flag_blockers(*, agent: str, cfg) -> List[str]:
    """Return the list of cfg-flag-blocker names that apply to one agent.
    Mirrors the agent-specific gate matrix in operator_initiative_advancement.
    """
    blockers: List[str] = []
    if not getattr(cfg, "operator_dual_key_present", False):
        blockers.append("operator_dual_key_not_present")
    if agent in ("anchor_sentry", "guardian"):
        if not getattr(cfg, "kms_hsm_production_ready", False):
            blockers.append("kms_hsm_production_not_provisioned")
    if agent == "guardian":
        if not getattr(cfg, "github_app_oauth_tokens_valid", False):
            blockers.append("github_app_oauth_tokens_not_valid")
    if agent == "curator":
        if not getattr(cfg, "marketplace_curator_role_assigned", False):
            blockers.append("marketplace_setCurator_role_not_assigned")
    return blockers


def run_preflight(db_path: str, *, strict: bool) -> Dict[str, Any]:
    now_unix = time.time()
    result: Dict[str, Any] = {
        "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                       time.gmtime(now_unix)),
        "db_path": db_path,
        "strict": strict,
        "calendar_gate": {
            "shadow_age_min_hours": 504,
            "note": "FROZEN per PHASE_O2_SHADOW_MIN_HOURS / PHASE_O3_SUGGEST_"
                    "MIN_HOURS — non-negotiable; cannot expedite without "
                    "governance ceremony breaking the protocol safety property",
        },
        "per_agent": [],
        "cfg_flag_summary": {},
        "rollup": {},
        "expedite_path_status": {},
        "error": None,
    }
    try:
        from vapi_bridge.config import Config
        from vapi_bridge.store import Store
        from vapi_bridge.operator_initiative_advancement import (
            evaluate_fleet_advancement_sync,
            INITIATIVE_AGENTS,
        )

        cfg = Config()
        store = Store(db_path=db_path)
        summary = evaluate_fleet_advancement_sync(cfg=cfg, store=store)
        if summary.error:
            result["error"] = f"watcher_error: {summary.error}"
            return result

        # Capture cfg flag state once for the whole fleet.
        result["cfg_flag_summary"] = {
            "operator_dual_key_present": bool(
                getattr(cfg, "operator_dual_key_present", False)),
            "kms_hsm_production_ready": bool(
                getattr(cfg, "kms_hsm_production_ready", False)),
            "github_app_oauth_tokens_valid": bool(
                getattr(cfg, "github_app_oauth_tokens_valid", False)),
            "marketplace_curator_role_assigned": bool(
                getattr(cfg, "marketplace_curator_role_assigned", False)),
        }

        per_agent_dicts: List[Dict[str, Any]] = []
        for a in summary.per_agent:
            # Calendar projection
            shadow_proj = _projected_clear(
                max(0.0, 504.0 - a.shadow_age_hours), now_unix
            )
            # Operator-clearable cfg-flag blockers for this agent
            cfg_blockers = _resolve_cfg_flag_blockers(
                agent=a.agent_id, cfg=cfg
            )
            # Separate the operator-clearable blockers from the calendar gate
            # by parsing the o3_blockers list shape (watcher emits text keys
            # like "draft_payload_count_X_under_min_50" / "o2_age_Xh_under_504h"
            # / "operator_dual_key_not_present" / etc.)
            calendar_o3 = []
            draft_o3 = []
            rate_o3 = []
            cfg_o3 = []
            other_o3 = []
            for b in a.o3_blockers:
                if "o2_age" in b or "shadow_age" in b:
                    calendar_o3.append(b)
                elif "draft_payload_count" in b:
                    draft_o3.append(b)
                elif "disagreement_rate" in b or "false_positive_rate" in b:
                    rate_o3.append(b)
                elif b in cfg_blockers:
                    cfg_o3.append(b)
                else:
                    other_o3.append(b)

            per_agent_dicts.append({
                "agent_id": a.agent_id,
                "current_phase": a.current_phase,
                "shadow_age_hours": round(a.shadow_age_hours, 1),
                "shadow_age_days": round(a.shadow_age_hours / 24.0, 2),
                "shadow_age_projection": shadow_proj,
                "cedar_eval_count": a.cedar_eval_count,
                "o2_ready": a.o2_ready,
                "o2_blockers": list(a.o2_blockers),
                "o3_ready": a.o3_ready,
                "o3_blockers_calendar": calendar_o3,
                "o3_blockers_draft": draft_o3,
                "o3_blockers_rate": rate_o3,
                "o3_blockers_cfg": cfg_o3,
                "o3_blockers_other": other_o3,
                "cfg_blockers_required": cfg_blockers,
                "error": a.error,
            })
        result["per_agent"] = per_agent_dicts

        # Earliest fleet-wide projection
        proj_unix_max = now_unix
        for d in per_agent_dicts:
            if not d["shadow_age_projection"]["cleared"]:
                hours = (504.0 - d["shadow_age_hours"])
                proj_unix_max = max(proj_unix_max, now_unix + hours * 3600.0)

        # Categorize blockers across the fleet
        total_calendar_remaining = max(
            (504.0 - d["shadow_age_hours"]) / 24.0
            for d in per_agent_dicts
            if d["current_phase"] in ("O0", "O1_SHADOW", "O2_SUGGEST")
        ) if per_agent_dicts else 0.0
        any_draft_blocked = any(d["o3_blockers_draft"] for d in per_agent_dicts)
        any_rate_blocked = any(d["o3_blockers_rate"] for d in per_agent_dicts)
        any_cfg_blocked = any(d["o3_blockers_cfg"] for d in per_agent_dicts)
        all_o3_ready = all(d["o3_ready"] for d in per_agent_dicts) and \
                       len(per_agent_dicts) == 3

        # Expedite path status: distinguish what's calendar-gated (cannot
        # accelerate) from what's operator-clearable (can clear today).
        expedite: Dict[str, Any] = {
            "calendar_gate": {
                "status": "BLOCKED" if total_calendar_remaining > 0
                                    else "CLEARED",
                "days_remaining_max": round(total_calendar_remaining, 2),
                "earliest_fleet_o3_ready_iso": time.strftime(
                    "%Y-%m-%dT%H:%M:%SZ", time.gmtime(proj_unix_max)
                ),
                "expedite_possible": False,
                "note": "FROZEN 504h shadow_age gate; calendar-bound",
            },
            "draft_count_gate": {
                "status": "BLOCKED" if any_draft_blocked else "CLEARED",
                "expedite_possible": any_draft_blocked,
                "expedite_action": (
                    "Operator can pre-populate via "
                    "scripts/operator_initiative_seed_drafts.py "
                    "(triple-gate authorized; uses existing Phase O2-DRAFT-"
                    "GENERATION primitives)."
                ) if any_draft_blocked else "n/a",
            },
            "rate_gate": {
                "status": "BLOCKED" if any_rate_blocked else "CLEARED",
                "expedite_possible": any_rate_blocked,
                "expedite_action": (
                    "Operator reviews drafts via "
                    "POST /operator/operator-agent-draft-review or the "
                    "DraftReviewDrawer in DeveloperView; accept decisions "
                    "drive disagreement_rate to 0%."
                ) if any_rate_blocked else "n/a",
            },
            "cfg_flag_gate": {
                "status": "BLOCKED" if any_cfg_blocked else "CLEARED",
                "expedite_possible": any_cfg_blocked,
                "expedite_action": (
                    "Operator sets the 4 cfg flags in bridge/.env: "
                    "OPERATOR_DUAL_KEY_PRESENT=true (all agents), "
                    "KMS_HSM_PRODUCTION_READY=true (Sentry+Guardian), "
                    "GITHUB_APP_OAUTH_TOKENS_VALID=true (Guardian), "
                    "MARKETPLACE_CURATOR_ROLE_ASSIGNED=true (Curator). "
                    "Each represents real operator-runtime infrastructure "
                    "work that must complete BEFORE the flag is flipped."
                ) if any_cfg_blocked else "n/a",
            },
        }
        result["expedite_path_status"] = expedite

        # CFG flags fully set means all 4 cfg-clearable gates ready. The
        # watcher only consults cfg flags AFTER an agent reaches O2_SUGGEST
        # (early-returns with agent_not_anchored at O0), so the watcher's
        # cfg_blockers list doesn't reflect cfg-flag-False state when agents
        # are pre-O2. Cross-check the flag summary directly.
        flags = result["cfg_flag_summary"]
        cfg_flags_fully_set = (
            flags["operator_dual_key_present"]
            and flags["kms_hsm_production_ready"]
            and flags["github_app_oauth_tokens_valid"]
            and flags["marketplace_curator_role_assigned"]
        )
        # Override the cfg_flag_gate status when watcher hasn't yet
        # evaluated cfg flags (agents pre-O2) but flags are still False.
        if not cfg_flags_fully_set and not any_cfg_blocked:
            expedite["cfg_flag_gate"]["status"] = "BLOCKED"
            expedite["cfg_flag_gate"]["expedite_possible"] = True
            expedite["cfg_flag_gate"]["expedite_action"] = (
                "Operator sets the 4 cfg flags in bridge/.env: "
                "OPERATOR_DUAL_KEY_PRESENT=true (all agents), "
                "KMS_HSM_PRODUCTION_READY=true (Sentry+Guardian), "
                "GITHUB_APP_OAUTH_TOKENS_VALID=true (Guardian), "
                "MARKETPLACE_CURATOR_ROLE_ASSIGNED=true (Curator). "
                "Each represents real operator-runtime infrastructure "
                "work that must complete BEFORE the flag is flipped."
            )

        result["rollup"] = {
            "fleet_size": summary.fleet_size,
            "fleet_phase_aligned": summary.fleet_phase_aligned,
            "next_alignment_target": summary.next_alignment_target,
            "fleet_at_o3_ready_count": summary.fleet_at_o3_ready_count,
            "earliest_fleet_o3_ready_iso":
                expedite["calendar_gate"]["earliest_fleet_o3_ready_iso"],
            "all_o3_ready": all_o3_ready,
            "cfg_flags_fully_set": cfg_flags_fully_set,
            "all_non_calendar_gates_clear": (
                not any_draft_blocked
                and not any_rate_blocked
                and not any_cfg_blocked
                and cfg_flags_fully_set
            ),
            "ceremony_ready_to_fire": all_o3_ready,
            "ceremony_ready_when_calendar_clears": (
                not any_draft_blocked
                and not any_rate_blocked
                and not any_cfg_blocked
                and cfg_flags_fully_set
            ),
        }
        return result

    except Exception as exc:  # noqa: BLE001 — fail-open
        result["error"] = f"{type(exc).__name__}: {exc}"
        return result


def _format_human(audit: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("Operator Initiative O3 Graduation — Comprehensive Preflight")
    lines.append(f"  Audit time: {audit['timestamp_iso']}")
    lines.append(f"  DB path:    {audit['db_path']}")
    lines.append(f"  Strict:     {audit['strict']}")
    lines.append("=" * 72)
    if audit.get("error"):
        lines.append(f"ERROR: {audit['error']}")
        return "\n".join(lines)

    cg = audit["calendar_gate"]
    lines.append(f"Calendar gate (FROZEN): shadow_age >= {cg['shadow_age_min_hours']}h")
    lines.append(f"  {cg['note']}")
    lines.append("")

    lines.append("CFG flag state (operator-clearable in bridge/.env):")
    for k, v in audit["cfg_flag_summary"].items():
        mark = "✓" if v else "✗"
        lines.append(f"  {mark} {k:<42s} = {v}")
    lines.append("")

    lines.append("Per-agent gate breakdown:")
    for a in audit["per_agent"]:
        lines.append(f"  Agent: {a['agent_id']}")
        lines.append(f"    phase            = {a['current_phase']}")
        lines.append(
            f"    shadow_age       = {a['shadow_age_hours']:.1f} h "
            f"({a['shadow_age_days']:.2f} d)"
        )
        sp = a["shadow_age_projection"]
        if sp["cleared"]:
            lines.append("    shadow_age gate  = CLEARED")
        else:
            lines.append(
                f"    shadow_age gate  = {sp['days_remaining']:.2f} d remaining "
                f"(projected: {sp['projected_iso']})"
            )
        lines.append(f"    o2_ready         = {a['o2_ready']}")
        if a["o2_blockers"]:
            for b in a["o2_blockers"]:
                lines.append(f"      O2 blocker: {b}")
        lines.append(f"    o3_ready         = {a['o3_ready']}")
        for cat in ("calendar", "draft", "rate", "cfg", "other"):
            blist = a.get(f"o3_blockers_{cat}", [])
            for b in blist:
                lines.append(f"      O3-{cat.upper():<6s} blocker: {b}")
        lines.append("")

    expedite = audit["expedite_path_status"]
    lines.append("Expedite path status (where can operator move TODAY):")
    for gate_name, gate_info in expedite.items():
        status = gate_info["status"]
        possible = gate_info.get("expedite_possible", False)
        mark = "✓" if status == "CLEARED" else ("⚡" if possible else "□")
        lines.append(f"  {mark} {gate_name:<22s} {status}")
        if possible and gate_info.get("expedite_action") != "n/a":
            for action_line in gate_info["expedite_action"].split(". "):
                if action_line.strip():
                    lines.append(f"      → {action_line.strip()}")
    lines.append("")

    r = audit["rollup"]
    lines.append("Fleet rollup:")
    lines.append(f"  fleet_size                          = {r['fleet_size']}")
    lines.append(f"  fleet_phase_aligned                 = {r['fleet_phase_aligned']}")
    lines.append(f"  next_alignment_target               = {r['next_alignment_target']}")
    lines.append(f"  fleet_at_o3_ready_count             = {r['fleet_at_o3_ready_count']}")
    lines.append(f"  all_o3_ready                        = {r['all_o3_ready']}")
    lines.append(f"  all_non_calendar_gates_clear        = {r['all_non_calendar_gates_clear']}")
    lines.append(f"  ceremony_ready_to_fire              = {r['ceremony_ready_to_fire']}")
    lines.append(f"  ceremony_ready_when_calendar_clears = {r['ceremony_ready_when_calendar_clears']}")
    lines.append(f"  earliest_fleet_o3_ready_iso         = {r['earliest_fleet_o3_ready_iso']}")
    lines.append("")

    # Verdict
    if r["ceremony_ready_to_fire"]:
        lines.append("VERDICT: READY-TO-FIRE — calendar + all gates cleared.")
        lines.append("         Operator may invoke parallel_o3_act_anchor.py.")
    elif r["ceremony_ready_when_calendar_clears"]:
        lines.append("VERDICT: CALENDAR-WAITING — every operator-clearable gate")
        lines.append("         is cleared; only the FROZEN 504h shadow_age gate")
        lines.append("         remains. Re-run this preflight at the projected")
        lines.append("         earliest_fleet_o3_ready_iso above.")
    else:
        lines.append("VERDICT: EXPEDITE-WORK-AVAILABLE — operator can clear")
        lines.append("         gates flagged ⚡ above in parallel with the")
        lines.append("         calendar countdown. See expedite_path_status.")
    return "\n".join(lines)


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Operator Initiative O3 graduation comprehensive preflight."
    )
    parser.add_argument(
        "--db",
        default=str(PROJECT_ROOT / "bridge" / "vapi_store.db"),
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict", action="store_true",
        help="Return exit 1 unless ALL gates (including cfg flags) clear. "
             "Useful as the final preflight just before parallel_o3_act_"
             "anchor.py --confirm."
    )
    args = parser.parse_args(argv)

    audit = run_preflight(args.db, strict=args.strict)
    if args.json:
        print(json.dumps(audit, indent=2, default=str))
    else:
        print(_format_human(audit))

    if audit.get("error"):
        return 3
    r = audit.get("rollup", {})
    if r.get("ceremony_ready_to_fire"):
        return 0
    if args.strict:
        return 1
    if r.get("ceremony_ready_when_calendar_clears"):
        return 2  # calendar-waiting (informational)
    return 1


if __name__ == "__main__":
    sys.exit(main())
