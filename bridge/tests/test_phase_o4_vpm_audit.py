"""Phase O4-VPM-INTEGRATION Stream A.4 — VPM audit tooling tests.

Test band:
  T-VPM-AUDIT-1: Section 1 — active compiler registry returns ok=True
                 against the live tree; all 6 active compilers found.
  T-VPM-AUDIT-2: Section 2 — draft manifest registry returns ok=True;
                 all 4 drafts found with lifecycle=Draft Manifest.
  T-VPM-AUDIT-3: Section 3 — VBDIP-0002A section 10 ladder coverage
                 returns ok=True for all 10 registered IDs.
  T-VPM-AUDIT-4: Section 4 — CFSS lane assignment returns ok=True for
                 all compilers + drafts (lanes match canonical set).
  T-VPM-AUDIT-5: Section 5 — compiler discipline source guards return
                 ok=True (no time.time / random / urllib in renderer
                 sources).
  T-VPM-AUDIT-6: Section 6 — visual grammar coverage returns ok=True;
                 every active compiler imports VISUAL_STATES +
                 assemble_vpm_head + visual_state_overlay.

Plus consolidated invariants:
  T-VPM-AUDIT-7: full audit overall_ok=True
  T-VPM-AUDIT-8: registry sums correct (6 active + 4 drafts + 10 section 10)
  T-VPM-AUDIT-9: missing-compiler injection surfaces as section 1 FAIL
                 (tests the negative path; uses --repo-root with a synthetic
                 repo missing one of the expected compilers)

Author: VAPI Architect (Phase O4 Commit 6)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _SCRIPTS)

from vpm_audit import (  # noqa: E402
    ACTIVE_COMPILERS,
    DRAFT_MANIFESTS,
    SECTION_10_REGISTRY,
    run_audit,
    section_1_active_compiler_registry,
    section_2_draft_manifest_registry,
    section_3_section_10_registry_ladder,
    section_4_cfss_lane_assignment,
    section_5_compiler_discipline_source_guards,
    section_6_visual_grammar_coverage,
)


_LIVE_REPO_ROOT = Path(_REPO)


# ---------------------------------------------------------------------------
# T-VPM-AUDIT-1..6 — each section returns ok=True on live tree
# ---------------------------------------------------------------------------

def test_t_vpm_audit_1_section_1_active_compiler_registry_ok():
    ok, findings = section_1_active_compiler_registry(_LIVE_REPO_ROOT)
    assert ok, f"section 1 FAIL: {[f for f in findings if f['status'] == 'FAIL']}"
    # 6 active compiler entries; section emits at least one finding per entry
    assert len(findings) >= len(ACTIVE_COMPILERS)


def test_t_vpm_audit_2_section_2_draft_manifest_registry_ok():
    ok, findings = section_2_draft_manifest_registry(_LIVE_REPO_ROOT)
    assert ok, f"section 2 FAIL: {[f for f in findings if f['status'] == 'FAIL']}"
    assert len(findings) == len(DRAFT_MANIFESTS)
    # All 4 drafts found at lifecycle Draft Manifest
    for finding in findings:
        assert finding["status"] == "OK"


def test_t_vpm_audit_3_section_3_section_10_ladder_ok():
    ok, findings = section_3_section_10_registry_ladder(_LIVE_REPO_ROOT)
    assert ok, f"section 3 FAIL: {[f for f in findings if f['status'] == 'FAIL']}"
    assert len(findings) == len(SECTION_10_REGISTRY) == 10
    # All 10 section 10 IDs accounted for at expected lifecycle
    statuses = {f["status"] for f in findings}
    assert statuses == {"OK"}


def test_t_vpm_audit_4_section_4_cfss_lane_assignment_ok():
    ok, findings = section_4_cfss_lane_assignment(_LIVE_REPO_ROOT)
    assert ok, f"section 4 FAIL: {[f for f in findings if f['status'] == 'FAIL']}"
    # 6 active compilers + 4 drafts = 10 lane checks
    assert len(findings) == len(ACTIVE_COMPILERS) + len(DRAFT_MANIFESTS) == 10


def test_t_vpm_audit_5_section_5_source_discipline_ok():
    ok, findings = section_5_compiler_discipline_source_guards(_LIVE_REPO_ROOT)
    assert ok, f"section 5 FAIL: {[f for f in findings if f['status'] == 'FAIL']}"
    # Every active compiler checked
    assert len(findings) == len(ACTIVE_COMPILERS)


def test_t_vpm_audit_6_section_6_visual_grammar_coverage_ok():
    ok, findings = section_6_visual_grammar_coverage(_LIVE_REPO_ROOT)
    assert ok, f"section 6 FAIL: {[f for f in findings if f['status'] == 'FAIL']}"
    assert len(findings) == len(ACTIVE_COMPILERS)


# ---------------------------------------------------------------------------
# T-VPM-AUDIT-7..9 — consolidated invariants + negative path
# ---------------------------------------------------------------------------

def test_t_vpm_audit_7_run_audit_overall_ok():
    """Full audit returns overall_ok=True with 6 sections each ok=True."""
    report = run_audit(_LIVE_REPO_ROOT)
    assert report["overall_ok"] is True, f"audit FAIL: {report}"
    assert len(report["sections"]) == 6
    for section in report["sections"]:
        assert section["ok"] is True, (
            f"section {section['key']} FAIL: "
            f"{[f for f in section['findings'] if f['status'] == 'FAIL']}"
        )


def test_t_vpm_audit_8_registry_sums_correct():
    """Registry cardinality invariants:
       - 6 active compilers (4 internal under HONESTY-BOARD umbrella +
         2 consumer-facing)
       - 4 draft manifests
       - 10 section 10 registered IDs
       - The 6+4 = 10 active-or-draft entries account for 6 distinct
         registered VPM IDs from section 10 (HONESTY-BOARD umbrella collapses
         4 compilers to 1 id)."""
    assert len(ACTIVE_COMPILERS) == 6
    assert len(DRAFT_MANIFESTS) == 4
    assert len(SECTION_10_REGISTRY) == 10

    # Distinct registered_vpm_ids in ACTIVE_COMPILERS
    active_ids = {entry["registered_vpm_id"] for entry in ACTIVE_COMPILERS}
    # 4 of the 6 active compilers share HONESTY-BOARD-v1 + 2 are distinct
    # (AGENT-REVIEW-v1, DISPUTE-PACKET-v1, MARKET-LISTING-v1 each unique)
    assert "HONESTY-BOARD-v1" in active_ids
    assert "AGENT-REVIEW-v1" in active_ids
    assert "DISPUTE-PACKET-v1" in active_ids
    assert "MARKET-LISTING-v1" in active_ids
    assert len(active_ids) == 4

    # 6 of 10 registered IDs are covered by compilers or drafts; 2 remain
    # Reserved (PROOF-TRAILER-v1, DEV-SANDBOX-v1) — section 3 verifies this
    draft_ids = {entry["vpm_id"] for entry in DRAFT_MANIFESTS}
    reserved_ids = {
        vid for vid, _, lifecycle in SECTION_10_REGISTRY
        if lifecycle == "Reserved"
    }
    assert reserved_ids == {"PROOF-TRAILER-v1", "DEV-SANDBOX-v1"}
    assert active_ids.isdisjoint(reserved_ids)
    assert draft_ids.isdisjoint(reserved_ids)
    assert draft_ids.isdisjoint(active_ids)


def test_t_vpm_audit_9_missing_compiler_surfaces_as_fail(tmp_path):
    """Negative-path test: synthetic repo-root missing the compilers must
    surface as a Section 1 FAIL. Proves the audit catches drift; not just
    that it asserts on the existing tree."""
    # tmp_path is an empty directory with no scripts/ or vpm_compile_* files
    # The audit's repo_root override targets this empty tree.
    report = run_audit(tmp_path)
    assert report["overall_ok"] is False
    section_1 = next(s for s in report["sections"]
                     if s["key"] == "section_1_active_compiler_registry")
    assert section_1["ok"] is False
    assert section_1["fail_count"] >= 1
    # All 6 active compilers should show FAIL for compiler_present
    fail_finds = [f for f in section_1["findings"] if f["status"] == "FAIL"]
    assert len(fail_finds) >= len(ACTIVE_COMPILERS)
    # Every FAIL should mention "compiler script missing"
    for f in fail_finds:
        assert "missing" in f["detail"]
