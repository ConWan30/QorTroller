"""Phase O3-ZKBA-TRACK1 Layer 7 coverage audit tests.

Verifies the wallet-free observability deliverable at
`scripts/layer7_coverage_audit.py` enforces 7-of-7 ZKBAClass coverage
across all five audit sections.

T-L7-AUDIT-1  LAYER7_CLASSES has exactly 7 entries with all 7 ZKBAClass
              values 1..7 (no duplicates, no gaps).
T-L7-AUDIT-2  Section 1 returns ok=True against the live
              bridge/vapi_bridge/zkba_artifact.py enum (catches future
              drift between the audit table and the FROZEN-v1 enum).
T-L7-AUDIT-3  Section 2 finds all 7 compiler scripts at expected paths
              with their canonical build_<artifact>_artifact symbol.
T-L7-AUDIT-4  Section 3 exercises 3 distinct ProofWeightClass values
              (CHAIN_ONLY, CALIBRATION_PLUS_CONTEXT, MARKETPLACE_DERIVED).
T-L7-AUDIT-5  Section 4 covers all 4 audiences (gamer, operator, buyer,
              manufacturer).
T-L7-AUDIT-6  Section 5 covers all 3 CFSS lanes with the expected
              distribution (sentry: 5 entries, guardian: 1, curator: 1).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path


_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
if _SCRIPTS not in sys.path:
    sys.path.insert(0, _SCRIPTS)


from layer7_coverage_audit import (  # noqa: E402
    LAYER7_CLASSES,
    EXPECTED_PROOF_WEIGHTS,
    EXPECTED_AUDIENCES,
    EXPECTED_CFSS_LANES,
    EXPECTED_LANE_DISTRIBUTION,
    section_1_zkba_class_coverage,
    section_2_compiler_script_presence,
    section_3_proof_weight_distribution,
    section_4_audience_coverage,
    section_5_cfss_lane_coverage,
)


_REPO_ROOT = Path(_REPO).resolve()


def test_t_l7_audit_1_layer7_classes_has_seven_entries_one_per_value():
    """LAYER7_CLASSES has exactly 7 entries spanning ZKBAClass values 1..7."""
    assert len(LAYER7_CLASSES) == 7, (
        f"expected exactly 7 entries; got {len(LAYER7_CLASSES)}"
    )
    values = [e["zkba_class_value"] for e in LAYER7_CLASSES]
    assert sorted(values) == [1, 2, 3, 4, 5, 6, 7], (
        f"expected contiguous values 1..7; got {sorted(values)}"
    )
    names = [e["name"] for e in LAYER7_CLASSES]
    assert len(set(names)) == 7, f"duplicate class names: {names}"


def test_t_l7_audit_2_section_1_passes_against_live_enum():
    """Section 1 (ZKBAClass enum coverage) PASSES against live zkba_artifact.py."""
    ok, findings = section_1_zkba_class_coverage(_REPO_ROOT)
    assert ok is True, f"section 1 failed; findings={findings}"
    # Spot-check: enum_member_count finding must be present + OK
    member_count_check = [
        f for f in findings if f.get("check") == "enum_member_count"
    ]
    assert member_count_check, "enum_member_count finding missing"
    assert member_count_check[0]["ok"] is True


def test_t_l7_audit_3_section_2_finds_all_seven_compiler_scripts():
    """Section 2 (compiler script presence) finds all 7 build fns."""
    ok, findings = section_2_compiler_script_presence(_REPO_ROOT)
    assert ok is True, f"section 2 failed; findings={findings}"
    # Verify every class has a build_fn_declared finding that is OK
    classes_seen = {f.get("class") for f in findings if f.get("check") == "build_fn_declared"}
    expected_classes = {e["name"] for e in LAYER7_CLASSES}
    assert classes_seen == expected_classes, (
        f"missing class checks: {expected_classes - classes_seen}; "
        f"unexpected: {classes_seen - expected_classes}"
    )


def test_t_l7_audit_4_section_3_exercises_three_distinct_proof_weights():
    """Section 3 confirms all 3 expected ProofWeightClass values exercised."""
    ok, findings = section_3_proof_weight_distribution()
    assert ok is True, f"section 3 failed; findings={findings}"
    counts = [f.get("counts") for f in findings if "counts" in f][0]
    observed = set(counts.keys())
    assert observed == EXPECTED_PROOF_WEIGHTS, (
        f"proof weight distribution drift; observed={observed} "
        f"expected={EXPECTED_PROOF_WEIGHTS}"
    )
    # CHAIN_ONLY is dominant (5 of 7); the other two each exercised once.
    assert counts["CHAIN_ONLY"] == 5
    assert counts["CALIBRATION_PLUS_CONTEXT"] == 1
    assert counts["MARKETPLACE_DERIVED"] == 1


def test_t_l7_audit_5_section_4_covers_all_four_audiences():
    """Section 4 confirms all 4 audiences (gamer/operator/buyer/manufacturer)."""
    ok, findings = section_4_audience_coverage()
    assert ok is True, f"section 4 failed; findings={findings}"
    counts = [f.get("counts") for f in findings if "counts" in f][0]
    observed = set(counts.keys())
    assert observed == EXPECTED_AUDIENCES, (
        f"audience distribution drift; observed={observed} "
        f"expected={EXPECTED_AUDIENCES}"
    )


def test_t_l7_audit_6_section_5_covers_all_three_cfss_lanes_with_expected_distribution():
    """Section 5 confirms sentry=5 / guardian=1 / curator=1 CFSS distribution."""
    ok, findings = section_5_cfss_lane_coverage()
    assert ok is True, f"section 5 failed; findings={findings}"
    counts = [f.get("counts") for f in findings if "counts" in f][0]
    observed = set(counts.keys())
    assert observed == EXPECTED_CFSS_LANES, (
        f"CFSS lane drift; observed={observed} expected={EXPECTED_CFSS_LANES}"
    )
    assert counts == EXPECTED_LANE_DISTRIBUTION, (
        f"CFSS distribution drift; observed={counts} "
        f"expected={EXPECTED_LANE_DISTRIBUTION}"
    )
