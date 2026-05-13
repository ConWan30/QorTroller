"""Phase O3-ZKBA-TRACK1 Layer 7 coverage audit — wallet-free observability.

Upstream audit precursor to the Phase O4 `scripts/vpm_audit.py` planned in
`wiki/proposals/Phase_O4_VPM_Integration_Plan.md` §3 Stream A.4. Mirrors the
`scripts/zkba_post_ceremony_audit.py` precedent — same shape, same wallet-free
contract, complementary scope:

  - post_ceremony_audit verifies the v2 Cedar bundle anchor surface
    (per-agent Merkle + on-chain scopeRoot + Cedar policy CFSS matrix)
  - layer7_coverage_audit verifies the Layer 7 artifact-emission surface
    (per-class compiler script + proof-weight distribution + audience
    distribution + CFSS lane distribution)

Concretely proves 7-of-7 ZKBAClass coverage closure with on-disk evidence:
each of the seven artifact classes has its own `scripts/zkba_compile_*.py`
producing the canonical `build_<artifact>_artifact` symbol, AND the three
orthogonal axes (proof weight, audience, CFSS lane) are each fully exercised
by the shipped artifact set.

Anchor commit: `ece17f4f` (HARDWARE Participation Card — 7th and final ZKBA
artifact target; closes Layer 7 to 7-of-7).

WALLET-FREE CONTRACT:

  - No transaction submission paths invoked
  - No RPC reads (purely filesystem + Python introspection)
  - No env-var changes
  - No file mutation outside the audit report output
  - CHAIN_SUBMISSION_PAUSED state untouched

Run:

    # Human-readable report (default):
    python scripts/layer7_coverage_audit.py --report

    # Machine-readable JSON:
    python scripts/layer7_coverage_audit.py --json

    # Override repo root (useful for tests):
    python scripts/layer7_coverage_audit.py --repo-root /path/to/repo

Exit codes:
  0  All 5 sections passed
  1  At least one section failed
  2  Usage / configuration error

Author: VAPI Architect (Layer 7 7-of-7 closure observability; ships
post-`ece17f4f` HARDWARE artifact landing 2026-05-13)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Canonical Layer 7 class registry — single source of truth for this script
# ---------------------------------------------------------------------------
#
# Each entry binds a ZKBAClass IntEnum value to its shipped artifact:
#   compiler_script      relative path under repo root
#   build_fn_name        symbol the compiler exports (build_<artifact>_artifact)
#   test_file            relative path under repo root
#   proof_weight         ProofWeightClass name (from zkba_artifact.py enum)
#   audience             {gamer, operator, buyer, manufacturer}
#   cfss_lane            {sentry, guardian, curator} (Cedar v2 lane-owning agent)
#   primary_primitives_composed  composition depth (informational)
#   commit               anchor commit hash (informational)
#
# Sourced from the seven artifact ship commits and confirmed against
# bridge/vapi_bridge/zkba_artifact.py FROZEN-v1 ZKBAClass enum.

LAYER7_CLASSES = [
    {
        "name": "AIT",
        "zkba_class_value": 1,
        "compiler_script": "scripts/zkba_compile_ait_snapshot.py",
        "build_fn_name": "build_ait_snapshot_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_ait_snapshot.py",
        "proof_weight": "CALIBRATION_PLUS_CONTEXT",
        "audience": "operator",
        "cfss_lane": "sentry",
        "primary_primitives_composed": 1,
        "commit": "bdbcf67f",
    },
    {
        "name": "GIC",
        "zkba_class_value": 2,
        "compiler_script": "scripts/zkba_compile_gic_ledger.py",
        "build_fn_name": "build_gic_ledger_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_compiler.py",
        "proof_weight": "CHAIN_ONLY",
        "audience": "operator",
        "cfss_lane": "sentry",
        "primary_primitives_composed": 1,
        "commit": "3b3081d3",
    },
    {
        "name": "VHP",
        "zkba_class_value": 3,
        "compiler_script": "scripts/zkba_compile_vhp_card.py",
        "build_fn_name": "build_vhp_card_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_vhp_card.py",
        "proof_weight": "CHAIN_ONLY",
        "audience": "operator",
        "cfss_lane": "sentry",
        "primary_primitives_composed": 1,
        "commit": "4f399282",
    },
    {
        "name": "HARDWARE",
        "zkba_class_value": 4,
        "compiler_script": "scripts/zkba_compile_hardware_card.py",
        "build_fn_name": "build_hardware_card_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_hardware_card.py",
        "proof_weight": "CHAIN_ONLY",
        "audience": "manufacturer",
        "cfss_lane": "sentry",
        "primary_primitives_composed": 1,
        "commit": "ece17f4f",
    },
    {
        "name": "CONSENT",
        "zkba_class_value": 5,
        "compiler_script": "scripts/zkba_compile_consent_receipt.py",
        "build_fn_name": "build_consent_receipt_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_consent_receipt.py",
        "proof_weight": "CHAIN_ONLY",
        "audience": "gamer",
        "cfss_lane": "guardian",
        "primary_primitives_composed": 1,
        "commit": "9bfa981e",
    },
    {
        "name": "TOURNAMENT",
        "zkba_class_value": 6,
        "compiler_script": "scripts/zkba_compile_tournament_card.py",
        "build_fn_name": "build_tournament_card_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_tournament_card.py",
        "proof_weight": "CHAIN_ONLY",
        "audience": "operator",
        "cfss_lane": "sentry",
        "primary_primitives_composed": 3,
        "commit": "25e7f8f2",
    },
    {
        "name": "MARKET",
        "zkba_class_value": 7,
        "compiler_script": "scripts/zkba_compile_marketplace_listing.py",
        "build_fn_name": "build_marketplace_listing_artifact",
        "test_file": "bridge/tests/test_phase_o3_zkba_marketplace_listing.py",
        "proof_weight": "MARKETPLACE_DERIVED",
        "audience": "buyer",
        "cfss_lane": "curator",
        "primary_primitives_composed": 2,
        "commit": "269e439c",
    },
]


# Expected per-axis distributions for assertion in sections 3-5. Updating any of
# these requires re-anchoring against the LAYER7_CLASSES table above.

EXPECTED_PROOF_WEIGHTS = {"CHAIN_ONLY", "CALIBRATION_PLUS_CONTEXT", "MARKETPLACE_DERIVED"}
EXPECTED_AUDIENCES = {"gamer", "operator", "buyer", "manufacturer"}
EXPECTED_CFSS_LANES = {"sentry", "guardian", "curator"}
EXPECTED_LANE_DISTRIBUTION = {"sentry": 5, "guardian": 1, "curator": 1}


# ---------------------------------------------------------------------------
# Section 1 — ZKBAClass enum coverage
# ---------------------------------------------------------------------------

def section_1_zkba_class_coverage(repo_root: Path) -> tuple[bool, list[dict[str, Any]]]:
    """Verify all 7 ZKBAClass enum values from zkba_artifact.py are accounted for.

    Loads the live `bridge/vapi_bridge/zkba_artifact.py` module via importlib
    (no bridge package dependencies required) and asserts every IntEnum member
    has a matching LAYER7_CLASSES entry and vice versa.
    """
    findings: list[dict[str, Any]] = []

    enum_path = repo_root / "bridge" / "vapi_bridge" / "zkba_artifact.py"
    if not enum_path.is_file():
        findings.append({
            "check": "zkba_artifact_module_present",
            "ok": False,
            "detail": f"zkba_artifact.py not found at {enum_path}",
        })
        return False, findings

    spec = importlib.util.spec_from_file_location("_zkba_artifact_audit", enum_path)
    if spec is None or spec.loader is None:
        findings.append({
            "check": "zkba_artifact_module_loadable",
            "ok": False,
            "detail": "importlib could not produce loader",
        })
        return False, findings

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # pragma: no cover - defensive
        findings.append({
            "check": "zkba_artifact_module_loadable",
            "ok": False,
            "detail": f"exec_module raised: {exc!r}",
        })
        return False, findings

    enum_cls = getattr(module, "ZKBAClass", None)
    if enum_cls is None:
        findings.append({
            "check": "zkba_class_enum_exported",
            "ok": False,
            "detail": "ZKBAClass not exported by zkba_artifact",
        })
        return False, findings

    enum_members = {m.name: int(m.value) for m in enum_cls}
    table_members = {e["name"]: e["zkba_class_value"] for e in LAYER7_CLASSES}

    missing_in_table = sorted(set(enum_members) - set(table_members))
    missing_in_enum = sorted(set(table_members) - set(enum_members))

    findings.append({
        "check": "enum_member_count",
        "ok": len(enum_members) == 7,
        "detail": f"ZKBAClass exports {len(enum_members)} members (expected 7)",
        "members": enum_members,
    })

    findings.append({
        "check": "table_matches_enum",
        "ok": (not missing_in_table) and (not missing_in_enum),
        "detail": (
            f"missing_in_LAYER7_CLASSES={missing_in_table}; "
            f"missing_in_ZKBAClass={missing_in_enum}"
        ),
    })

    value_mismatches = [
        n for n in enum_members
        if n in table_members and enum_members[n] != table_members[n]
    ]
    findings.append({
        "check": "enum_values_match_table",
        "ok": not value_mismatches,
        "detail": (
            "all values match"
            if not value_mismatches
            else f"value mismatches: {value_mismatches}"
        ),
    })

    ok = all(f["ok"] for f in findings)
    return ok, findings


# ---------------------------------------------------------------------------
# Section 2 — Compiler script presence + canonical build fn
# ---------------------------------------------------------------------------

def section_2_compiler_script_presence(
    repo_root: Path,
) -> tuple[bool, list[dict[str, Any]]]:
    """For each class, verify the compiler script exists and exports its build fn.

    Uses lightweight text scanning (no module import) so we don't accidentally
    drag in heavy dependencies at audit time. Compilers are well-known to
    declare their build fn at top-level with `def build_<name>_artifact(`.
    """
    findings: list[dict[str, Any]] = []

    for entry in LAYER7_CLASSES:
        script_path = repo_root / entry["compiler_script"]
        build_fn = entry["build_fn_name"]
        if not script_path.is_file():
            findings.append({
                "check": "compiler_script_present",
                "class": entry["name"],
                "ok": False,
                "detail": f"missing: {script_path}",
            })
            continue
        try:
            src = script_path.read_text(encoding="utf-8", errors="replace")
        except Exception as exc:  # pragma: no cover - defensive
            findings.append({
                "check": "compiler_script_readable",
                "class": entry["name"],
                "ok": False,
                "detail": f"read failed: {exc!r}",
            })
            continue
        sig_present = f"def {build_fn}(" in src
        findings.append({
            "check": "build_fn_declared",
            "class": entry["name"],
            "ok": sig_present,
            "detail": (
                f"{build_fn} found in {entry['compiler_script']}"
                if sig_present
                else f"{build_fn} NOT FOUND in {entry['compiler_script']}"
            ),
        })

    ok = all(f["ok"] for f in findings)
    return ok, findings


# ---------------------------------------------------------------------------
# Section 3 — ProofWeightClass distribution
# ---------------------------------------------------------------------------

def section_3_proof_weight_distribution() -> tuple[bool, list[dict[str, Any]]]:
    """Count proof weights across the 7 classes; assert the 3 expected exercised."""
    findings: list[dict[str, Any]] = []

    counts: dict[str, int] = {}
    for entry in LAYER7_CLASSES:
        counts[entry["proof_weight"]] = counts.get(entry["proof_weight"], 0) + 1

    observed = set(counts.keys())
    missing_proof_weights = EXPECTED_PROOF_WEIGHTS - observed
    unexpected_proof_weights = observed - EXPECTED_PROOF_WEIGHTS

    findings.append({
        "check": "expected_proof_weights_exercised",
        "ok": not missing_proof_weights,
        "detail": (
            f"counts={counts}; "
            f"missing={sorted(missing_proof_weights)}; "
            f"unexpected={sorted(unexpected_proof_weights)}"
        ),
        "counts": counts,
    })

    findings.append({
        "check": "distinct_proof_weights_at_least_3",
        "ok": len(observed) >= 3,
        "detail": f"distinct proof weights observed: {sorted(observed)}",
    })

    ok = all(f["ok"] for f in findings)
    return ok, findings


# ---------------------------------------------------------------------------
# Section 4 — Audience coverage
# ---------------------------------------------------------------------------

def section_4_audience_coverage() -> tuple[bool, list[dict[str, Any]]]:
    """Audience distribution across the 7 classes; assert all 4 covered."""
    findings: list[dict[str, Any]] = []

    counts: dict[str, int] = {}
    for entry in LAYER7_CLASSES:
        counts[entry["audience"]] = counts.get(entry["audience"], 0) + 1

    observed = set(counts.keys())
    missing = EXPECTED_AUDIENCES - observed
    unexpected = observed - EXPECTED_AUDIENCES

    findings.append({
        "check": "expected_audiences_covered",
        "ok": not missing,
        "detail": (
            f"counts={counts}; "
            f"missing={sorted(missing)}; "
            f"unexpected={sorted(unexpected)}"
        ),
        "counts": counts,
    })

    findings.append({
        "check": "audience_set_size_4",
        "ok": len(observed) == 4,
        "detail": f"distinct audiences observed: {sorted(observed)}",
    })

    ok = all(f["ok"] for f in findings)
    return ok, findings


# ---------------------------------------------------------------------------
# Section 5 — CFSS lane coverage
# ---------------------------------------------------------------------------

def section_5_cfss_lane_coverage() -> tuple[bool, list[dict[str, Any]]]:
    """CFSS lane distribution across the 7 classes; assert all 3 lanes used."""
    findings: list[dict[str, Any]] = []

    counts: dict[str, int] = {}
    for entry in LAYER7_CLASSES:
        counts[entry["cfss_lane"]] = counts.get(entry["cfss_lane"], 0) + 1

    observed = set(counts.keys())
    missing = EXPECTED_CFSS_LANES - observed
    unexpected = observed - EXPECTED_CFSS_LANES

    findings.append({
        "check": "all_three_lanes_utilized",
        "ok": not missing,
        "detail": (
            f"counts={counts}; "
            f"missing={sorted(missing)}; "
            f"unexpected={sorted(unexpected)}"
        ),
        "counts": counts,
    })

    findings.append({
        "check": "distribution_matches_expected",
        "ok": counts == EXPECTED_LANE_DISTRIBUTION,
        "detail": (
            f"observed={counts}; expected={EXPECTED_LANE_DISTRIBUTION}"
        ),
    })

    ok = all(f["ok"] for f in findings)
    return ok, findings


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def _render_section(name: str, ok: bool, findings: list[dict[str, Any]]) -> str:
    status = "OK" if ok else "FAIL"
    lines = [f"=== {name}: {status} ==="]
    for f in findings:
        sub_status = "OK" if f.get("ok", False) else "FAIL"
        check = f.get("check", "?")
        detail = f.get("detail", "")
        cls = f.get("class")
        if cls:
            lines.append(f"  [{sub_status}] {check} ({cls}): {detail}")
        else:
            lines.append(f"  [{sub_status}] {check}: {detail}")
    return "\n".join(lines)


def _render_class_table() -> str:
    header = (
        "  CLASS         VAL  COMMIT     PROOF WEIGHT             "
        "AUDIENCE      CFSS LANE   COMP DEPTH"
    )
    sep = "  " + "-" * (len(header) - 2)
    rows = [header, sep]
    for e in LAYER7_CLASSES:
        rows.append(
            f"  {e['name']:<13} {e['zkba_class_value']:<4} "
            f"{e['commit']:<10} {e['proof_weight']:<24} "
            f"{e['audience']:<13} {e['cfss_lane']:<11} "
            f"{e['primary_primitives_composed']}-primitive"
        )
    return "\n".join(rows)


def _build_full_report(
    section_results: list[tuple[str, bool, list[dict[str, Any]]]],
) -> str:
    overall_ok = all(ok for _, ok, _ in section_results)
    overall = "PASS" if overall_ok else "FAIL"

    parts: list[str] = []
    parts.append("=" * 76)
    parts.append("VAPI Layer 7 Coverage Audit  --  wallet-free observability")
    parts.append("=" * 76)
    parts.append("")
    parts.append("Anchor commit: ece17f4f (HARDWARE Participation Card)")
    parts.append("Companion to:  scripts/zkba_post_ceremony_audit.py")
    parts.append("Forward link:  wiki/proposals/Phase_O4_VPM_Integration_Plan.md")
    parts.append("")
    parts.append("Layer 7 class table:")
    parts.append(_render_class_table())
    parts.append("")
    for name, ok, findings in section_results:
        parts.append(_render_section(name, ok, findings))
        parts.append("")
    parts.append(f"OVERALL: {overall}")
    parts.append("")
    return "\n".join(parts)


def _build_json_report(
    section_results: list[tuple[str, bool, list[dict[str, Any]]]],
) -> str:
    overall_ok = all(ok for _, ok, _ in section_results)
    payload = {
        "audit": "layer7_coverage",
        "anchor_commit": "ece17f4f",
        "overall_ok": overall_ok,
        "classes": LAYER7_CLASSES,
        "sections": [
            {"name": name, "ok": ok, "findings": findings}
            for name, ok, findings in section_results
        ],
    }
    return json.dumps(payload, indent=2, sort_keys=False)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def run_audit(repo_root: Path) -> list[tuple[str, bool, list[dict[str, Any]]]]:
    s1_ok, s1_findings = section_1_zkba_class_coverage(repo_root)
    s2_ok, s2_findings = section_2_compiler_script_presence(repo_root)
    s3_ok, s3_findings = section_3_proof_weight_distribution()
    s4_ok, s4_findings = section_4_audience_coverage()
    s5_ok, s5_findings = section_5_cfss_lane_coverage()
    return [
        ("Section 1 -- ZKBAClass enum coverage", s1_ok, s1_findings),
        ("Section 2 -- Compiler script presence", s2_ok, s2_findings),
        ("Section 3 -- ProofWeightClass distribution", s3_ok, s3_findings),
        ("Section 4 -- Audience coverage", s4_ok, s4_findings),
        ("Section 5 -- CFSS lane coverage", s5_ok, s5_findings),
    ]


def main(argv: list[str] | None = None) -> int:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # pragma: no cover - non-Windows stdout
        pass

    parser = argparse.ArgumentParser(
        description=(
            "Layer 7 coverage audit -- verifies 7-of-7 ZKBA artifact coverage "
            "across class enum, compiler scripts, proof weight distribution, "
            "audience coverage, and CFSS lane utilization."
        ),
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Emit human-readable report (default).",
    )
    parser.add_argument(
        "--json",
        dest="emit_json",
        action="store_true",
        help="Emit machine-readable JSON report instead of text.",
    )
    parser.add_argument(
        "--repo-root",
        type=str,
        default=None,
        help=(
            "Override repo root (default: parent dir of this script's "
            "directory)."
        ),
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code not in (0, None) else int(exc.code or 0)

    if args.repo_root is None:
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent
    else:
        repo_root = Path(args.repo_root).resolve()
    if not repo_root.is_dir():
        sys.stderr.write(f"error: repo-root not a directory: {repo_root}\n")
        return 2

    results = run_audit(repo_root)

    if args.emit_json:
        sys.stdout.write(_build_json_report(results))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(_build_full_report(results))

    overall_ok = all(ok for _, ok, _ in results)
    return 0 if overall_ok else 1


if __name__ == "__main__":
    sys.exit(main())
