"""Curator O2_SUGGEST -> O3_ACT graduation readiness consolidated audit.

Closes the orchestration gap between G7 observability (the harness
shipped at commit 2c243f26) and the existing parallel_o3_act_anchor.py
ceremony script. Today the operator must run multiple commands to know
whether Curator is graduation-ready:

  - g7_curator_review_readiness_audit.py  -> G7 PASS / BLOCKED / FAIL
  - GET /operator/operator-initiative-advancement  -> watcher gates
  - cfss_lane_drift_sweep.py  -> Cedar v2 lane authority intact?
  - zkba_post_ceremony_audit.py  -> on-chain anchor state intact?

This script consolidates all four into one report + computes a single
"Curator graduation cleared" verdict the operator can act on. When this
script exits 0 with verdict=READY, the operator may fire:

    $env:CHAIN_SUBMISSION_PAUSED = "false"
    $env:OPERATOR_INITIATIVE_O3_AUTHORIZED = "true"
    python scripts/parallel_o3_act_anchor.py --confirm

WALLET-FREE CONTRACT:
  - Pure read-only sqlite + JSON bundle reads
  - No bridge HTTP calls (resilient when bridge is offline)
  - No transaction submission paths invoked
  - CHAIN_SUBMISSION_PAUSED state untouched

Five sections (consolidates 4 underlying audits + watcher state):

  Section 1 — G7 acceptance gate
              Invokes g7_curator_review_readiness_audit.run_audit
              against the live bridge DB. Surfaces verdict +
              acceptance counts.

  Section 2 — Operator Initiative watcher
              Invokes evaluate_fleet_advancement_sync. Surfaces
              Curator's current_phase + o3_ready + o3_blockers.

  Section 3 — CFSS Cedar v2 lane authority
              Invokes cfss_lane_drift_sweep.sweep_once. Verifies
              Curator's lane authority bundle matches
              EXPECTED_LANE_MATRIX (4 rows).

  Section 4 — On-chain anchor state
              Invokes zkba_post_ceremony_audit.section_1_local_merkles
              for the Curator bundle. Verifies the local v2 bundle
              file matches the EXPECTED_MERKLES lock.

  Section 5 — Consolidated verdict
              READY if all 4 sections PASS.
              BLOCKED if any section reports BLOCKED (insufficient
                signal but not a failure — e.g. G7 n_reviewed < 10).
              FAIL if any section reports FAIL or VIOLATION.

Run:

    # Default audit:
    python scripts/curator_graduation_readiness_audit.py

    # Machine-readable JSON:
    python scripts/curator_graduation_readiness_audit.py --json

    # Custom DB / bundle path (testing):
    python scripts/curator_graduation_readiness_audit.py \\
        --db bridge/vapi_store.db \\
        --bundle-dir bridge/vapi_bridge/cedar_bundles

Exit codes:
  0  READY — operator may fire parallel_o3_act_anchor.py --confirm
  1  BLOCKED — gate insufficient signal (continue observation)
  2  FAIL — at least one hard-block detected; do NOT fire ceremony
  3  Configuration / dependency error
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
if str(PROJECT_ROOT / "bridge") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "bridge"))

# Import the underlying audit modules
import importlib.util  # noqa: E402

def _load_script(name: str):
    path = PROJECT_ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)  # type: ignore
    sys.modules[name] = module
    spec.loader.exec_module(module)  # type: ignore
    return module


def section_1_g7(db_path: Path) -> dict:
    """G7 Curator Review Readiness acceptance gate."""
    try:
        g7_audit = _load_script("g7_curator_review_readiness_audit")
        report, exit_code = g7_audit.run_audit(db_path)
        verdict = report.get("final_verdict") or report.get("verdict") or "UNKNOWN"
        return {
            "section": "1_g7_acceptance_gate",
            "verdict": verdict,
            "g7_exit_code": exit_code,
            "verdict_class": _g7_verdict_class(verdict),
            "details": {
                "section_2_window_counts": report.get(
                    "section_2_window_counts", {}
                ),
                "section_3_last_n_breakdown": report.get(
                    "section_3_last_n_breakdown", {}
                ),
                "section_5_zero_tolerance": report.get(
                    "section_5_zero_tolerance_invariant", {}
                ),
            } if exit_code != 3 else None,
        }
    except Exception as exc:
        return {
            "section": "1_g7_acceptance_gate",
            "verdict": "ERROR",
            "verdict_class": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }


def _g7_verdict_class(g7_verdict: str) -> str:
    """Map G7's verbose verdicts to PASS/BLOCKED/FAIL/ERROR."""
    if g7_verdict == "PASS":
        return "PASS"
    if g7_verdict == "BLOCKED":
        return "BLOCKED"
    if g7_verdict in (
        "FAIL", "FAIL_ZERO_TOLERANCE_VIOLATION",
        "NO_CURATOR_DRAFTS",
    ):
        return "FAIL"
    return "ERROR"


def section_2_watcher(db_path: Path) -> dict:
    """Operator Initiative watcher's view of Curator readiness."""
    try:
        # Import the watcher entry-point. Use the bridge's Config + Store
        # constructed against the same DB path.
        from vapi_bridge.config import Config  # type: ignore
        from vapi_bridge.store import Store  # type: ignore
        from vapi_bridge.operator_initiative_advancement import (  # type: ignore
            evaluate_fleet_advancement_sync,
        )
        import dataclasses

        cfg = dataclasses.replace(Config(), db_path=str(db_path))
        store = Store(str(db_path))
        summary = evaluate_fleet_advancement_sync(cfg=cfg, store=store)

        if summary.error:
            return {
                "section": "2_operator_initiative_watcher",
                "verdict_class": "ERROR",
                "error": summary.error,
            }

        # Find Curator in per_agent
        curator_state = None
        for a in summary.per_agent:
            if a.agent_id == "curator":
                curator_state = a
                break

        if curator_state is None:
            return {
                "section": "2_operator_initiative_watcher",
                "verdict_class": "ERROR",
                "error": "Curator not found in per_agent rollup",
            }

        if curator_state.error:
            return {
                "section": "2_operator_initiative_watcher",
                "verdict_class": "ERROR",
                "error": curator_state.error,
            }

        # Classify by current_phase + o3_ready
        if curator_state.current_phase == "O3_ACT":
            verdict_class = "PASS"
            reason = "Curator already at O3_ACT — graduation complete"
        elif curator_state.current_phase != "O2_SUGGEST":
            verdict_class = "FAIL"
            reason = (
                f"Curator at {curator_state.current_phase}, not O2_SUGGEST; "
                f"O2 advancement must complete before O3 graduation"
            )
        elif curator_state.o3_ready:
            verdict_class = "PASS"
            reason = "Curator at O2_SUGGEST with o3_ready=True"
        else:
            verdict_class = "BLOCKED"
            reason = (
                f"Curator at O2_SUGGEST but o3_ready=False; "
                f"blockers: {curator_state.o3_blockers}"
            )

        return {
            "section": "2_operator_initiative_watcher",
            "verdict_class": verdict_class,
            "reason": reason,
            "current_phase": curator_state.current_phase,
            "o2_ready": curator_state.o2_ready,
            "o3_ready": curator_state.o3_ready,
            "o3_blockers": list(curator_state.o3_blockers or ()),
            "shadow_age_hours": curator_state.shadow_age_hours,
            "cedar_eval_count": curator_state.cedar_eval_count,
        }
    except Exception as exc:
        return {
            "section": "2_operator_initiative_watcher",
            "verdict_class": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }


def section_3_cfss(bundle_dir: Path) -> dict:
    """CFSS Cedar v2 lane authority for Curator's 4 rows."""
    try:
        cfss_drift = _load_script("cfss_lane_drift_sweep")
        report = cfss_drift.sweep_once(bundle_dir)

        # Filter to Curator's 4 rows.
        curator_rows = [
            r for r in report.get("rows", [])
            if r.get("agent_id") == "curator"
        ]
        curator_violations = [
            r for r in curator_rows
            if r.get("status") == "CFSS_VIOLATION"
        ]

        if report["verdict"] == "PASS":
            verdict_class = "PASS"
            reason = "All 4 Curator lane authority rows match EXPECTED_LANE_MATRIX"
        elif curator_violations:
            verdict_class = "FAIL"
            reason = (
                f"Curator CFSS violation count: {len(curator_violations)}. "
                f"Lane authority drift detected — investigate before "
                f"firing O3 ceremony."
            )
        else:
            # Bundle load error or other-agent violation; Curator-specific
            # state may still be clean but cross-fleet integrity is broken.
            verdict_class = "FAIL"
            reason = (
                f"CFSS overall verdict: {report['verdict']}. Cross-fleet "
                f"integrity broken even if Curator rows match."
            )

        return {
            "section": "3_cfss_lane_authority",
            "verdict_class": verdict_class,
            "reason": reason,
            "cfss_overall_verdict": report["verdict"],
            "curator_rows_checked": len(curator_rows),
            "curator_violations": len(curator_violations),
        }
    except Exception as exc:
        return {
            "section": "3_cfss_lane_authority",
            "verdict_class": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }


def section_4_on_chain(bundle_dir: Path) -> dict:
    """Local v2 bundle Merkle matches EXPECTED_MERKLES lock (Curator only)."""
    try:
        post_ceremony = _load_script("zkba_post_ceremony_audit")
        ok, findings, computed = post_ceremony.section_1_local_merkles(
            bundle_dir,
        )

        # Find Curator's finding.
        curator_finding = None
        for f in findings:
            if f.get("agent") == "curator":
                curator_finding = f
                break

        if curator_finding is None:
            return {
                "section": "4_on_chain_anchor_state",
                "verdict_class": "ERROR",
                "error": "Curator not found in local Merkle findings",
            }

        if curator_finding["status"] == "MATCH":
            verdict_class = "PASS"
            reason = (
                f"Curator local v2 bundle Merkle "
                f"{curator_finding['computed'][:18]}... matches "
                f"EXPECTED_MERKLES lock"
            )
        else:
            verdict_class = "FAIL"
            reason = (
                f"Curator local Merkle status: "
                f"{curator_finding['status']}. "
                f"Expected: {curator_finding.get('expected', '')[:18]}... "
                f"Computed: {curator_finding.get('computed', '')[:18]}..."
            )

        return {
            "section": "4_on_chain_anchor_state",
            "verdict_class": verdict_class,
            "reason": reason,
            "curator_finding": curator_finding,
        }
    except Exception as exc:
        return {
            "section": "4_on_chain_anchor_state",
            "verdict_class": "ERROR",
            "error": f"{type(exc).__name__}: {exc}",
        }


def section_5_consolidated(s1: dict, s2: dict, s3: dict, s4: dict) -> dict:
    """Reduce 4 sub-verdicts to one of READY / BLOCKED / FAIL."""
    classes = [
        s1.get("verdict_class"),
        s2.get("verdict_class"),
        s3.get("verdict_class"),
        s4.get("verdict_class"),
    ]

    if "ERROR" in classes:
        return {
            "section": "5_consolidated_verdict",
            "verdict": "ERROR",
            "exit_code": 3,
            "reason": "One or more sections failed to evaluate; "
                      "see section error fields",
        }
    if "FAIL" in classes:
        failed = [
            ("g7" if i == 0 else "watcher" if i == 1
             else "cfss" if i == 2 else "on_chain")
            for i, c in enumerate(classes) if c == "FAIL"
        ]
        return {
            "section": "5_consolidated_verdict",
            "verdict": "FAIL",
            "exit_code": 2,
            "reason": f"Sections failing hard: {failed}. "
                      f"DO NOT fire parallel_o3_act_anchor.py.",
        }
    if "BLOCKED" in classes:
        blocked = [
            ("g7" if i == 0 else "watcher" if i == 1
             else "cfss" if i == 2 else "on_chain")
            for i, c in enumerate(classes) if c == "BLOCKED"
        ]
        return {
            "section": "5_consolidated_verdict",
            "verdict": "BLOCKED",
            "exit_code": 1,
            "reason": f"Sections blocked (insufficient signal): "
                      f"{blocked}. Continue observation.",
        }
    return {
        "section": "5_consolidated_verdict",
        "verdict": "READY",
        "exit_code": 0,
        "reason": (
            "All 4 sections PASS. Curator graduation cleared. Operator "
            "may fire parallel_o3_act_anchor.py with three-factor auth."
        ),
    }


def run_audit(db_path: Path, bundle_dir: Path) -> tuple[dict, int]:
    started = time.time()

    s1 = section_1_g7(db_path)
    s2 = section_2_watcher(db_path)
    s3 = section_3_cfss(bundle_dir)
    s4 = section_4_on_chain(bundle_dir)
    s5 = section_5_consolidated(s1, s2, s3, s4)

    return (
        {
            "audit": "curator_graduation_readiness",
            "timestamp_unix": started,
            "section_1_g7_acceptance_gate": s1,
            "section_2_operator_initiative_watcher": s2,
            "section_3_cfss_lane_authority": s3,
            "section_4_on_chain_anchor_state": s4,
            "section_5_consolidated_verdict": s5,
        },
        s5["exit_code"],
    )


def render_human(report: dict) -> str:
    lines = []
    lines.append("=" * 70)
    lines.append("Curator O2_SUGGEST -> O3_ACT Graduation Readiness Audit")
    lines.append("=" * 70)
    lines.append(f"Audit time (unix): {report['timestamp_unix']:.0f}")
    lines.append("")

    for key, label in [
        ("section_1_g7_acceptance_gate",          "Section 1 — G7 acceptance gate"),
        ("section_2_operator_initiative_watcher", "Section 2 — Operator Initiative watcher"),
        ("section_3_cfss_lane_authority",         "Section 3 — CFSS Cedar v2 lane authority"),
        ("section_4_on_chain_anchor_state",       "Section 4 — On-chain anchor state"),
    ]:
        s = report[key]
        lines.append(label)
        lines.append(f"  verdict_class: {s.get('verdict_class', 'UNKNOWN')}")
        if "reason" in s:
            lines.append(f"  reason:        {s['reason']}")
        if "error" in s:
            lines.append(f"  error:         {s['error']}")
        lines.append("")

    s5 = report["section_5_consolidated_verdict"]
    lines.append("=" * 70)
    lines.append(f"FINAL VERDICT: {s5['verdict']}")
    lines.append(f"Reason: {s5['reason']}")
    lines.append(f"Exit code: {s5['exit_code']}")
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Curator O2 -> O3 graduation readiness consolidated audit"
        ),
    )
    parser.add_argument(
        "--db", type=Path,
        default=PROJECT_ROOT / "bridge" / "vapi_store.db",
        help="Path to vapi_store.db",
    )
    parser.add_argument(
        "--bundle-dir", type=Path,
        default=PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles",
        help="Cedar bundle directory",
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Emit machine-readable JSON instead of human report",
    )
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

    report, exit_code = run_audit(args.db, args.bundle_dir)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True, default=str))
    else:
        print(render_human(report))

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
