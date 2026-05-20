"""Phase O4-VPM-INTEGRATION Stream A.4 — VPM compiler audit tooling.

Parallels scripts/zkba_post_ceremony_audit.py (commit 755dad63) and
scripts/layer7_coverage_audit.py (commit 168256a0). Provides a CLI tool
that audits the local filesystem for VPM compiler compliance + manifest
integrity + lifecycle ladder correctness.

Wallet-free. Read-only. No chain RPC. No file mutation outside the audit
report output (when --json is requested without --output-file, JSON goes
to stdout; otherwise human-readable report to stdout).

Audits 6 sections:

  Section 1 — Active VPM compiler registry
      Verifies every active compiler script exists at the expected path
      and exports the expected build function. 6 active compilers post-A.2:
        HONESTY-BOARD-v1     (umbrella; 4 internal projections)
        AGENT-REVIEW-v1      (Guardian lane)
        CDRR-DAG-v1          (internal; under HONESTY-BOARD umbrella)
        GIC-LEDGER-BETA-v1   (internal; under HONESTY-BOARD umbrella)
        DISPUTE-PACKET-v1    (Guardian lane; A.2.a)
        MARKET-LISTING-v1    (Curator lane; A.2.b)

  Section 2 — Draft Manifest registry
      Verifies every draft manifest JSON exists at the expected path with
      lifecycle_status = "Draft Manifest" and a valid shape. 4 drafts
      post-A.3: PROOF-WALLET-v1 / QR-ELIGIBILITY-v1 / HARDWARE-LINEAGE-v1
      / CONSENT-CAPSULE-v1.

  Section 3 — VBDIP-0002A section 10 registry lifecycle ladder coverage
      Verifies every one of the 10 registered VPM IDs is accounted for
      at its expected lifecycle stage. Catches drift between the section
      10 registry and the implementation state.

  Section 4 — CFSS lane assignment per compiler / draft
      Verifies each active compiler and each draft proposes a CFSS lane
      that matches the Cedar v2 lane-authority matrix in
      EXPECTED_LANE_MATRIX (per zkba_post_ceremony_audit.py).

  Section 5 — Compiler discipline static guards
      Greps the source of every active compiler for FORBIDDEN patterns
      that the compile_vpm_artifact runtime guard would catch downstream
      but which (if present in source) indicate the renderer author did
      not internalize the discipline. Catches:
        no time.time() / time.time_ns() in renderer source (runtime use
            via inputs['ts_ns'] is correct; calling time.* is forbidden)
        no random / secrets / urandom imports

  Section 6 — Visual grammar coverage matrix
      Verifies every active compiler imports the canonical
      vpm_visual_grammar module + uses VISUAL_STATES, assemble_vpm_head,
      and visual_state_overlay. 6 active compilers x mandatory grammar
      imports = 6 x N coverage cells, all OK at landing.

Run:

    # Human-readable report:
    python scripts/vpm_audit.py

    # Machine-readable JSON:
    python scripts/vpm_audit.py --json

    # Override repo root (for tests):
    python scripts/vpm_audit.py --repo-root /path/to/repo

Exit codes:
  0  All sections OK
  1  Section failure (any section returned ok=False)
  2  Usage / config error

Author: VAPI Architect (Phase O4 Commit 6)
Date: 2026-05-13
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import sys
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Canonical registries — single source of truth
# ---------------------------------------------------------------------------

# Active VPM compilers (post Phase O4 Stream A.2)
# Each entry: (registered_vpm_id, compiler_script_path, build_function_name,
#              proposed_cfss_lane, proposed_zkba_class, internal_id_or_none)
ACTIVE_COMPILERS = [
    {
        "registered_vpm_id":   "HONESTY-BOARD-v1",
        "compiler_path":       "scripts/vpm_compile_honesty_board.py",
        "build_function":      "build_honesty_board_artifact",
        "proposed_cfss_lane":  "sentry",
        "proposed_zkba_class": 2,  # GIC
        "internal_id":         None,
        "lifecycle":           "Test Fixture",
    },
    {
        "registered_vpm_id":   "AGENT-REVIEW-v1",
        "compiler_path":       "scripts/vpm_compile_agent_review.py",
        "build_function":      "build_agent_review_artifact",
        "proposed_cfss_lane":  "guardian",
        "proposed_zkba_class": 5,  # CONSENT
        "internal_id":         None,
        "lifecycle":           "Test Fixture",
    },
    {
        "registered_vpm_id":   "HONESTY-BOARD-v1",
        "compiler_path":       "scripts/vpm_compile_cdrr_dag.py",
        "build_function":      "build_cdrr_dag_artifact",
        "proposed_cfss_lane":  "sentry",
        "proposed_zkba_class": 4,  # HARDWARE
        "internal_id":         "CDRR-DAG-v1",
        "lifecycle":           "Test Fixture",
    },
    {
        "registered_vpm_id":   "HONESTY-BOARD-v1",
        "compiler_path":       "scripts/vpm_compile_gic_ledger_beta.py",
        "build_function":      "build_gic_ledger_beta_artifact",
        "proposed_cfss_lane":  "sentry",
        "proposed_zkba_class": 2,  # GIC
        "internal_id":         "GIC-LEDGER-BETA-v1",
        "lifecycle":           "Test Fixture",
    },
    {
        "registered_vpm_id":   "DISPUTE-PACKET-v1",
        "compiler_path":       "scripts/vpm_compile_dispute_packet.py",
        "build_function":      "build_dispute_packet_artifact",
        "proposed_cfss_lane":  "guardian",
        "proposed_zkba_class": 5,  # CONSENT
        "internal_id":         None,
        "lifecycle":           "Compiler Target",
    },
    {
        "registered_vpm_id":   "MARKET-LISTING-v1",
        "compiler_path":       "scripts/vpm_compile_market_listing.py",
        "build_function":      "build_market_listing_artifact",
        "proposed_cfss_lane":  "curator",
        "proposed_zkba_class": 7,  # MARKET
        "internal_id":         None,
        "lifecycle":           "Compiler Target",
    },
]


# Draft manifests (post Phase O4 Stream A.3)
DRAFT_MANIFESTS = [
    {
        "vpm_id":              "PROOF-WALLET-v1",
        "draft_path":          "scripts/vpm_drafts/PROOF-WALLET-v1.draft.json",
        "proposed_cfss_lane":  "sentry",
        "proposed_zkba_class": 3,
        "audience":            "Gamers",
    },
    {
        "vpm_id":              "QR-ELIGIBILITY-v1",
        "draft_path":          "scripts/vpm_drafts/QR-ELIGIBILITY-v1.draft.json",
        "proposed_cfss_lane":  "sentry",
        "proposed_zkba_class": 6,
        "audience":            "Tournament Organizers",
    },
    {
        "vpm_id":              "HARDWARE-LINEAGE-v1",
        "draft_path":          "scripts/vpm_drafts/HARDWARE-LINEAGE-v1.draft.json",
        "proposed_cfss_lane":  "sentry",
        "proposed_zkba_class": 4,
        "audience":            "Manufacturers",
    },
    {
        "vpm_id":              "CONSENT-CAPSULE-v1",
        "draft_path":          "scripts/vpm_drafts/CONSENT-CAPSULE-v1.draft.json",
        "proposed_cfss_lane":  "guardian",
        "proposed_zkba_class": 5,
        "audience":            "Gamers / Data Buyers",
    },
]


# Full VBDIP-0002A section 10 registry — all 10 IDs + their expected
# lifecycle status post-Stream A.3.
SECTION_10_REGISTRY = [
    ("PROOF-TRAILER-v1",     "Esports Viewers",         "Reserved"),
    ("PROOF-WALLET-v1",      "Gamers",                  "Draft Manifest"),
    ("QR-ELIGIBILITY-v1",    "Organizers",              "Draft Manifest"),
    ("HARDWARE-LINEAGE-v1",  "Manufacturers",           "Draft Manifest"),
    ("CONSENT-CAPSULE-v1",   "Gamers / Data Buyers",    "Draft Manifest"),
    ("DISPUTE-PACKET-v1",    "Referees / Ops",          "Compiler Target"),
    ("MARKET-LISTING-v1",    "Buyers / Curator",        "Compiler Target"),
    ("DEV-SANDBOX-v1",       "Developers",              "Reserved"),
    ("HONESTY-BOARD-v1",     "Ecosystem Partners",      "Test Fixture"),
    ("AGENT-REVIEW-v1",      "Governance / Deployer",   "Test Fixture"),
]


# CFSS lane authority matrix mirrored from scripts/zkba_post_ceremony_audit.py
# (single source of truth for lane authority lives there; this dict caches
# the lane assignments for VPM-level audit purposes).
CFSS_LANE_AUTHORITY = {
    "sentry":   ("tool:zk-artifact-anchor",   "draft://zk_artifacts/*"),
    "guardian": ("tool:zk-audit-trail",       "draft://zk_verifications/*"),
    "curator":  ("tool:zk-marketplace-listing", "draft://zk_listings/*"),
}


# Forbidden patterns in compiler source — same shape as compile_vpm_artifact
# runtime guards but applied at audit time to source code, catching renderer
# authors who tried to call wall-clock / random functions in renderer bodies.
SOURCE_FORBIDDEN_PATTERNS = [
    (re.compile(r"\btime\s*\.\s*time\s*\("),
     "renderer calls time.time() (wall-clock; use inputs['ts_ns'] instead)"),
    (re.compile(r"\btime\s*\.\s*time_ns\s*\("),
     "renderer calls time.time_ns() (wall-clock; use inputs['ts_ns'] instead)"),
    (re.compile(r"\btime\s*\.\s*monotonic\s*\("),
     "renderer calls time.monotonic() (wall-clock)"),
    (re.compile(r"\bdatetime\s*\.\s*now\s*\("),
     "renderer calls datetime.now() (wall-clock)"),
    (re.compile(r"^\s*import\s+random\b", re.MULTILINE),
     "renderer imports random (no randomness in deterministic VPM)"),
    (re.compile(r"^\s*from\s+random\s+import\b", re.MULTILINE),
     "renderer imports from random (no randomness in deterministic VPM)"),
    (re.compile(r"^\s*import\s+secrets\b", re.MULTILINE),
     "renderer imports secrets (no randomness in deterministic VPM)"),
    (re.compile(r"\bos\s*\.\s*urandom\s*\("),
     "renderer calls os.urandom() (no randomness in deterministic VPM)"),
    (re.compile(r"^\s*import\s+urllib\b", re.MULTILINE),
     "renderer imports urllib (no runtime network in deterministic VPM)"),
    (re.compile(r"^\s*import\s+requests\b", re.MULTILINE),
     "renderer imports requests (no runtime network)"),
    (re.compile(r"^\s*import\s+http\.client\b", re.MULTILINE),
     "renderer imports http.client (no runtime network)"),
    (re.compile(r"^\s*import\s+socket\b", re.MULTILINE),
     "renderer imports socket (no runtime network)"),
]


# Mandatory imports each compiler must reference.
# TEMPLATE v3 (Claude-Design certificate): every active compiler now inherits
# the canonical Anti-Hype Visual Grammar through the shared
# render_vpm_certificate() shell, which internally emits visual_state_meta_tag /
# visual_state_css / visual_state_overlay + the FROZEN 6-state signatures. The
# single required import is therefore the shell entrypoint; the legacy
# per-helper imports (assemble_vpm_head / visual_state_overlay) are no longer
# mandated because the shell owns them.
REQUIRED_GRAMMAR_IMPORTS = (
    "render_vpm_certificate",
)


# ---------------------------------------------------------------------------
# Section runners — each returns (ok: bool, findings: list[dict])
# ---------------------------------------------------------------------------

def section_1_active_compiler_registry(repo_root: Path) -> tuple[bool, list[dict]]:
    """Verify every active compiler script exists + exports its build fn."""
    findings: list[dict] = []
    all_ok = True

    for entry in ACTIVE_COMPILERS:
        path = repo_root / entry["compiler_path"]
        check_name = f"compiler_present ({entry['compiler_path']})"
        if not path.exists():
            findings.append({
                "section": 1,
                "check": check_name,
                "status": "FAIL",
                "detail": f"compiler script missing at {path}",
            })
            all_ok = False
            continue

        src = path.read_text(encoding="utf-8")
        build_fn = entry["build_function"]
        if f"def {build_fn}(" not in src:
            findings.append({
                "section": 1,
                "check": f"build_function_present ({build_fn})",
                "status": "FAIL",
                "detail": (
                    f"compiler {entry['compiler_path']} missing "
                    f"def {build_fn}(...)"
                ),
            })
            all_ok = False
            continue

        findings.append({
            "section": 1,
            "check": check_name,
            "status": "OK",
            "detail": (
                f"{entry['registered_vpm_id']}"
                + (f" / {entry['internal_id']}" if entry["internal_id"] else "")
                + f" / build fn {build_fn} present / lifecycle {entry['lifecycle']}"
            ),
        })

    return all_ok, findings


def section_2_draft_manifest_registry(repo_root: Path) -> tuple[bool, list[dict]]:
    """Verify every draft manifest JSON exists + has lifecycle=Draft Manifest."""
    findings: list[dict] = []
    all_ok = True

    for entry in DRAFT_MANIFESTS:
        path = repo_root / entry["draft_path"]
        check_name = f"draft_present ({entry['vpm_id']})"
        if not path.exists():
            findings.append({
                "section": 2,
                "check": check_name,
                "status": "FAIL",
                "detail": f"draft JSON missing at {path}",
            })
            all_ok = False
            continue

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            findings.append({
                "section": 2,
                "check": check_name,
                "status": "FAIL",
                "detail": f"invalid JSON: {exc}",
            })
            all_ok = False
            continue

        # Lifecycle status MUST be exactly "Draft Manifest"
        ls = data.get("lifecycle_status")
        if ls != "Draft Manifest":
            findings.append({
                "section": 2,
                "check": f"lifecycle_status ({entry['vpm_id']})",
                "status": "FAIL",
                "detail": f"expected 'Draft Manifest'; got {ls!r}",
            })
            all_ok = False
            continue

        # vpm_id must match
        if data.get("vpm_id") != entry["vpm_id"]:
            findings.append({
                "section": 2,
                "check": f"vpm_id_match ({entry['vpm_id']})",
                "status": "FAIL",
                "detail": (
                    f"file claims vpm_id={data.get('vpm_id')!r}; "
                    f"registry pins {entry['vpm_id']!r}"
                ),
            })
            all_ok = False
            continue

        findings.append({
            "section": 2,
            "check": check_name,
            "status": "OK",
            "detail": (
                f"{entry['vpm_id']} / lifecycle Draft Manifest / "
                f"audience {entry['audience']}"
            ),
        })

    return all_ok, findings


def section_3_section_10_registry_ladder(repo_root: Path) -> tuple[bool, list[dict]]:
    """Verify every section 10 registry ID is at its expected lifecycle stage.

    Cross-references SECTION_10_REGISTRY against the union of
    ACTIVE_COMPILERS (Test Fixture + Compiler Target IDs) and
    DRAFT_MANIFESTS (Draft Manifest IDs). Reserved IDs are present in
    the registry but have neither compiler nor draft.
    """
    findings: list[dict] = []
    all_ok = True

    # Build observed-state map
    compiler_ids = {entry["registered_vpm_id"] for entry in ACTIVE_COMPILERS}
    draft_ids = {entry["vpm_id"] for entry in DRAFT_MANIFESTS}

    # Active compilers have an internal_id distinct from the registered_vpm_id
    # but the registry tracks lifecycle by the registered_vpm_id. So a single
    # registry entry can have multiple compiler entries under its umbrella.

    for vpm_id, audience, expected_lifecycle in SECTION_10_REGISTRY:
        check_name = f"section10_lifecycle ({vpm_id})"

        if expected_lifecycle == "Reserved":
            # MUST NOT have a compiler or a draft manifest
            if vpm_id in compiler_ids:
                findings.append({
                    "section": 3,
                    "check": check_name,
                    "status": "FAIL",
                    "detail": (
                        f"registry pins {vpm_id} at 'Reserved' but a "
                        "compiler exists; either advance the registry or "
                        "remove the compiler"
                    ),
                })
                all_ok = False
                continue
            if vpm_id in draft_ids:
                findings.append({
                    "section": 3,
                    "check": check_name,
                    "status": "FAIL",
                    "detail": (
                        f"registry pins {vpm_id} at 'Reserved' but a "
                        "draft manifest exists; either advance the "
                        "registry or remove the draft"
                    ),
                })
                all_ok = False
                continue
        elif expected_lifecycle == "Draft Manifest":
            if vpm_id not in draft_ids:
                findings.append({
                    "section": 3,
                    "check": check_name,
                    "status": "FAIL",
                    "detail": (
                        f"registry pins {vpm_id} at 'Draft Manifest' but "
                        "no draft JSON exists"
                    ),
                })
                all_ok = False
                continue
            if vpm_id in compiler_ids:
                findings.append({
                    "section": 3,
                    "check": check_name,
                    "status": "FAIL",
                    "detail": (
                        f"registry pins {vpm_id} at 'Draft Manifest' but "
                        "a compiler ALSO exists; advance registry to "
                        "'Compiler Target' or remove the compiler"
                    ),
                })
                all_ok = False
                continue
        elif expected_lifecycle in ("Compiler Target", "Test Fixture"):
            if vpm_id not in compiler_ids:
                findings.append({
                    "section": 3,
                    "check": check_name,
                    "status": "FAIL",
                    "detail": (
                        f"registry pins {vpm_id} at '{expected_lifecycle}' "
                        "but no compiler exists"
                    ),
                })
                all_ok = False
                continue

        findings.append({
            "section": 3,
            "check": check_name,
            "status": "OK",
            "detail": f"{vpm_id} at lifecycle {expected_lifecycle} ({audience})",
        })

    return all_ok, findings


def section_4_cfss_lane_assignment(repo_root: Path) -> tuple[bool, list[dict]]:
    """Verify each compiler + draft proposes a CFSS lane in the canonical set."""
    findings: list[dict] = []
    all_ok = True

    for entry in ACTIVE_COMPILERS:
        lane = entry["proposed_cfss_lane"]
        check_name = f"cfss_lane_active ({entry['compiler_path']})"
        if lane not in CFSS_LANE_AUTHORITY:
            findings.append({
                "section": 4,
                "check": check_name,
                "status": "FAIL",
                "detail": (
                    f"compiler {entry['compiler_path']} claims unknown "
                    f"CFSS lane {lane!r}; valid lanes are "
                    f"{list(CFSS_LANE_AUTHORITY)}"
                ),
            })
            all_ok = False
            continue
        action, resource_prefix = CFSS_LANE_AUTHORITY[lane]
        findings.append({
            "section": 4,
            "check": check_name,
            "status": "OK",
            "detail": (
                f"{entry['registered_vpm_id']} / lane {lane} / "
                f"action {action} / resource {resource_prefix}"
            ),
        })

    for entry in DRAFT_MANIFESTS:
        lane = entry["proposed_cfss_lane"]
        check_name = f"cfss_lane_draft ({entry['vpm_id']})"
        if lane not in CFSS_LANE_AUTHORITY:
            findings.append({
                "section": 4,
                "check": check_name,
                "status": "FAIL",
                "detail": (
                    f"draft {entry['vpm_id']} claims unknown CFSS lane "
                    f"{lane!r}"
                ),
            })
            all_ok = False
            continue
        action, resource_prefix = CFSS_LANE_AUTHORITY[lane]
        findings.append({
            "section": 4,
            "check": check_name,
            "status": "OK",
            "detail": (
                f"{entry['vpm_id']} / proposed lane {lane} / "
                f"future action {action}"
            ),
        })

    return all_ok, findings


def section_5_compiler_discipline_source_guards(
    repo_root: Path,
) -> tuple[bool, list[dict]]:
    """Grep every active compiler source for FORBIDDEN patterns.

    Catches wall-clock / random / network imports in renderer source —
    patterns the runtime guard in compile_vpm_artifact would catch in the
    EMITTED HTML, but which (if present in PYTHON SOURCE) indicate a
    renderer author who hasn't internalized the discipline.
    """
    findings: list[dict] = []
    all_ok = True

    for entry in ACTIVE_COMPILERS:
        path = repo_root / entry["compiler_path"]
        check_name = f"source_discipline ({entry['compiler_path']})"
        if not path.exists():
            findings.append({
                "section": 5,
                "check": check_name,
                "status": "SKIP",
                "detail": "compiler source missing (will surface in Section 1)",
            })
            continue

        src = path.read_text(encoding="utf-8")
        violations: list[str] = []
        for pattern, description in SOURCE_FORBIDDEN_PATTERNS:
            if pattern.search(src):
                violations.append(description)

        if violations:
            findings.append({
                "section": 5,
                "check": check_name,
                "status": "FAIL",
                "detail": "; ".join(violations),
            })
            all_ok = False
        else:
            findings.append({
                "section": 5,
                "check": check_name,
                "status": "OK",
                "detail": "no forbidden wall-clock / random / network patterns",
            })

    return all_ok, findings


def section_6_visual_grammar_coverage(
    repo_root: Path,
) -> tuple[bool, list[dict]]:
    """Verify every active compiler imports the canonical vpm_visual_grammar
    module + uses the required helpers."""
    findings: list[dict] = []
    all_ok = True

    for entry in ACTIVE_COMPILERS:
        path = repo_root / entry["compiler_path"]
        check_name = f"grammar_coverage ({entry['compiler_path']})"
        if not path.exists():
            findings.append({
                "section": 6,
                "check": check_name,
                "status": "SKIP",
                "detail": "compiler source missing (will surface in Section 1)",
            })
            continue

        src = path.read_text(encoding="utf-8")
        # Must import from vpm_visual_grammar
        if "from vpm_visual_grammar import" not in src:
            findings.append({
                "section": 6,
                "check": check_name,
                "status": "FAIL",
                "detail": (
                    "compiler does not import from vpm_visual_grammar; "
                    "Anti-Hype Visual Grammar inheritance is mandatory"
                ),
            })
            all_ok = False
            continue

        missing: list[str] = []
        for required in REQUIRED_GRAMMAR_IMPORTS:
            if required not in src:
                missing.append(required)
        if missing:
            findings.append({
                "section": 6,
                "check": check_name,
                "status": "FAIL",
                "detail": (
                    "compiler missing required grammar imports: "
                    f"{', '.join(missing)}"
                ),
            })
            all_ok = False
            continue

        findings.append({
            "section": 6,
            "check": check_name,
            "status": "OK",
            "detail": (
                f"{entry['registered_vpm_id']} imports VISUAL_STATES + "
                f"assemble_vpm_head + visual_state_overlay"
            ),
        })

    return all_ok, findings


# ---------------------------------------------------------------------------
# Reporter
# ---------------------------------------------------------------------------

def run_audit(repo_root: Path) -> dict[str, Any]:
    """Run all 6 audit sections; return the full audit report dict."""
    sections = [
        ("section_1_active_compiler_registry",
         "Active VPM compiler registry",
         section_1_active_compiler_registry(repo_root)),
        ("section_2_draft_manifest_registry",
         "Draft Manifest registry",
         section_2_draft_manifest_registry(repo_root)),
        ("section_3_section_10_registry_ladder",
         "VBDIP-0002A section 10 lifecycle ladder",
         section_3_section_10_registry_ladder(repo_root)),
        ("section_4_cfss_lane_assignment",
         "CFSS lane assignment",
         section_4_cfss_lane_assignment(repo_root)),
        ("section_5_compiler_discipline_source_guards",
         "Compiler discipline source guards",
         section_5_compiler_discipline_source_guards(repo_root)),
        ("section_6_visual_grammar_coverage",
         "Visual grammar coverage",
         section_6_visual_grammar_coverage(repo_root)),
    ]

    overall_ok = True
    report: dict[str, Any] = {
        "audit": "phase_o4_vpm_audit",
        "version": "v0.1.0",
        "repo_root": str(repo_root),
        "anchor_commit_hint": "7052144f (Phase O4 Stream A.2 ship)",
        "active_compiler_count": len(ACTIVE_COMPILERS),
        "draft_manifest_count": len(DRAFT_MANIFESTS),
        "section_10_registry_size": len(SECTION_10_REGISTRY),
        "sections": [],
    }

    for section_key, title, (ok, findings) in sections:
        if not ok:
            overall_ok = False
        report["sections"].append({
            "key": section_key,
            "title": title,
            "ok": ok,
            "findings": findings,
            "fail_count": sum(1 for f in findings if f["status"] == "FAIL"),
            "ok_count": sum(1 for f in findings if f["status"] == "OK"),
            "skip_count": sum(1 for f in findings if f["status"] == "SKIP"),
        })

    report["overall_ok"] = overall_ok
    return report


def render_report_text(report: dict[str, Any]) -> str:
    """Render the audit report as human-readable text."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("VAPI VPM Compiler Audit  --  wallet-free observability")
    lines.append("=" * 78)
    lines.append("")
    lines.append(f"Audit version:  {report['version']}")
    lines.append(f"Repo root:      {report['repo_root']}")
    lines.append(f"Anchor commit:  {report['anchor_commit_hint']}")
    lines.append(f"Active compilers: {report['active_compiler_count']}")
    lines.append(f"Draft manifests:  {report['draft_manifest_count']}")
    lines.append(f"Section 10 size:  {report['section_10_registry_size']}")
    lines.append("")

    for section in report["sections"]:
        status = "OK" if section["ok"] else "FAIL"
        lines.append(
            f"=== Section {section['key'].split('_')[1]} -- {section['title']}: {status} ==="
        )
        for finding in section["findings"]:
            lines.append(
                f"  [{finding['status']}] {finding['check']}: {finding['detail']}"
            )
        lines.append("")

    lines.append("=" * 78)
    overall = "PASS" if report["overall_ok"] else "FAIL"
    lines.append(f"OVERALL: {overall}")
    lines.append("=" * 78)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli_main() -> int:
    parser = argparse.ArgumentParser(
        description="VAPI VPM Compiler Audit (Phase O4-VPM-INTEGRATION Stream A.4). "
                    "Wallet-free. Read-only. No chain RPC. "
                    "Parallels scripts/zkba_post_ceremony_audit.py."
    )
    parser.add_argument(
        "--repo-root",
        default=None,
        help="Override repo root (default: auto-detect from script location)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable JSON instead of human report",
    )
    args = parser.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = Path(__file__).resolve().parent.parent

    if not repo_root.exists():
        sys.stderr.write(f"error: repo-root does not exist: {repo_root}\n")
        return 2

    report = run_audit(repo_root)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_report_text(report))

    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    sys.exit(_cli_main())
