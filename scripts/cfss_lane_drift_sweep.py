"""CFSS Cedar-policy lane authority drift sweeper.

Wallet-free continuous-detection surface for the Cross-Fleet Skill
Separation (CFSS) invariant. Closes the asymmetry between the protocol's
two enforcement layers:

  - DATA layer: FSCA's 26 contradiction rules already detect data-layer
    drift (table rows showing one agent acting in another agent's lane).
  - POLICY layer: until now, the 12-row Cedar lane authority matrix
    (EXPECTED_LANE_MATRIX in scripts/zkba_post_ceremony_audit.py) was
    only verified by the operator-runtime post-ceremony audit, never by
    a continuous-detection surface. A silent mutation to a Cedar bundle
    file post-anchor would not be detected until the next operator
    triggers the audit.

This sweeper closes that gap. It evaluates the 12-row matrix against
the live JSON bundle files on every invocation and surfaces drift
immediately. Designed to be:

  - Single-shot: invocable from cron / CI / orchestrator
  - Wallet-free + read-only: pure file reads + canonical-Cedar evaluation
  - Aligned with the existing FSCA cadence pattern (INV-OPERATOR-AGENT-008
    dual-cadence: bundle 60s / scope 600s). Run at the same 60s interval
    as the existing cedar_drift_sweeper to inherit the same cadence
    contract.
  - Architecturally bound to EXPECTED_LANE_MATRIX as the single source
    of truth. The matrix is pinned in source; mutations require a
    governance ceremony.

Run:

    # One-shot evaluation (default):
    python scripts/cfss_lane_drift_sweep.py

    # Emit machine-readable JSON:
    python scripts/cfss_lane_drift_sweep.py --json

    # Custom bundle directory (testing / multi-instance deployments):
    python scripts/cfss_lane_drift_sweep.py \\
        --bundle-dir /path/to/cedar_bundles/

Exit codes:
  0  All 12 rows match EXPECTED_LANE_MATRIX (CFSS invariant holds)
  1  One or more CFSS_VIOLATION findings (lane authority drift)
  2  Bundle file(s) missing or unparseable
  3  Configuration error

Author: VAPI Architect — CFSS Cedar-policy drift sweeper ships 2026-05-13
per operator authorization. Extends the existing data-layer FSCA
detection pattern into the policy layer.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BUNDLE_DIR = (
    PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
)

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

# Single source of truth: import the matrix + helpers from the
# post-ceremony audit. Avoids drift between the two scripts.
from zkba_post_ceremony_audit import (  # type: ignore  # noqa: E402
    AGENT_ANCHOR_ORDER,
    AGENT_BUNDLE_FILES,
    EXPECTED_LANE_MATRIX,
    _bundle_policy_effect,
)


def sweep_once(bundle_dir: Path) -> dict:
    """Run a single CFSS matrix evaluation. Returns the report dict.

    Never raises; structural errors land in the report payload."""
    started_at = time.time()
    report = {
        "audit": "cfss_lane_drift_sweep",
        "timestamp_unix": started_at,
        "bundle_dir": str(bundle_dir),
        "expected_rows": len(EXPECTED_LANE_MATRIX),
        "rows": [],
        "bundle_load_errors": [],
        "violations": [],
        "verdict": "UNKNOWN",
        "exit_code": 3,
    }

    if not bundle_dir.exists():
        report["bundle_load_errors"].append({
            "agent": "(any)",
            "detail": f"bundle_dir does not exist: {bundle_dir}",
        })
        report["verdict"] = "CONFIG_ERROR"
        report["exit_code"] = 3
        return report

    # Pre-load all 3 bundles (one per agent in CFSS triangle).
    bundles: dict = {}
    for agent_id in AGENT_ANCHOR_ORDER:
        fname = AGENT_BUNDLE_FILES[agent_id]
        path = bundle_dir / fname
        if not path.exists():
            report["bundle_load_errors"].append({
                "agent": agent_id,
                "detail": f"bundle file not found: {path}",
            })
            continue
        try:
            with open(path, encoding="utf-8") as f:
                bundles[agent_id] = json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            report["bundle_load_errors"].append({
                "agent": agent_id,
                "detail": f"parse error: {exc}",
            })

    if report["bundle_load_errors"]:
        report["verdict"] = "BUNDLE_LOAD_ERROR"
        report["exit_code"] = 2
        return report

    # Evaluate every row of EXPECTED_LANE_MATRIX.
    for agent_id, action, resource, expected_effect in EXPECTED_LANE_MATRIX:
        actual = _bundle_policy_effect(bundles[agent_id], action, resource)
        match = actual == expected_effect
        row = {
            "agent_id": agent_id,
            "action": action,
            "resource": resource or "(any)",
            "expected_effect": expected_effect,
            "actual_effect": actual,
            "match": match,
            "status": "OK" if match else "CFSS_VIOLATION",
        }
        report["rows"].append(row)
        if not match:
            report["violations"].append(row)

    if report["violations"]:
        report["verdict"] = "CFSS_VIOLATION"
        report["exit_code"] = 1
    else:
        report["verdict"] = "PASS"
        report["exit_code"] = 0

    report["completed_at_unix"] = time.time()
    return report


def render_human(report: dict) -> str:
    """Human-readable report block."""
    lines = []
    lines.append("=" * 70)
    lines.append(
        "CFSS Cedar-Policy Lane Authority Drift Sweep"
    )
    lines.append("=" * 70)
    lines.append(f"Audit time (unix): {report['timestamp_unix']:.0f}")
    lines.append(f"Bundle dir:        {report['bundle_dir']}")
    lines.append(f"Expected rows:     {report['expected_rows']}")
    lines.append("")

    if report["bundle_load_errors"]:
        lines.append("Bundle load errors:")
        for err in report["bundle_load_errors"]:
            lines.append(f"  - agent={err['agent']}: {err['detail']}")
        lines.append("")

    if report["rows"]:
        lines.append("Per-row matrix evaluation:")
        for row in report["rows"]:
            marker = "  [OK]   " if row["match"] else "  [DRIFT]"
            lines.append(
                f"{marker} {row['agent_id']:<14s}  "
                f"{row['action']:<30s}  -> "
                f"{row['actual_effect']:<7s} "
                f"(expected {row['expected_effect']})"
            )
        lines.append("")

    if report["violations"]:
        lines.append(f"CFSS_VIOLATION count: {len(report['violations'])}")
        lines.append("")
        lines.append("Each violation indicates a Cedar bundle has drifted ")
        lines.append("from the FROZEN EXPECTED_LANE_MATRIX. Possible causes:")
        lines.append("  (a) bundle JSON file edited post-anchor without")
        lines.append("      governance ceremony (suspect tamper)")
        lines.append("  (b) bundle version mismatch (v1 in dir vs v2 expected)")
        lines.append("  (c) EXPECTED_LANE_MATRIX out of sync with anchored")
        lines.append("      v2 bundle (matrix update needed via ceremony)")
        lines.append("")
        lines.append("Investigate before next agent fleet operation. Run:")
        lines.append("  python scripts/zkba_post_ceremony_audit.py")
        lines.append("to cross-check against on-chain AgentScope state.")
    else:
        lines.append("All 12 matrix rows match EXPECTED_LANE_MATRIX.")
        lines.append("CFSS invariant holds across Sentry / Guardian / Curator.")

    lines.append("=" * 70)
    lines.append(f"VERDICT: {report['verdict']}")
    lines.append(f"Exit code: {report['exit_code']}")
    lines.append("=" * 70)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "CFSS Cedar-policy lane authority drift sweeper "
            "(continuous-detection surface for the policy-layer "
            "CFSS invariant)"
        ),
    )
    parser.add_argument(
        "--bundle-dir", type=Path, default=DEFAULT_BUNDLE_DIR,
        help=f"Cedar bundle directory (default: {DEFAULT_BUNDLE_DIR})",
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

    report = sweep_once(args.bundle_dir)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_human(report))

    return report["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
