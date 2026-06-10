"""HWFL-1 Cycle 1 — Sensor A v0.1 variant tests.

Tests variant #16 `mythos_path_a_spec_impl_parity` per the chassis pattern
established by variant #15 (`mythos_agent_utility_honesty`): fail-open,
COVERAGE_BOUNDARY first finding, never raises, returns structured
MythosFindingResult list.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from bridge.vapi_bridge.mythos_variants import mythos_path_a_spec_impl_parity


REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _run(repo_root: Path):
    return asyncio.run(mythos_path_a_spec_impl_parity(repo_root=repo_root))


def test_t_sensor_a_1_returns_list_against_real_repo():
    """Live repo: variant returns a non-empty list and never raises."""
    findings = _run(REPO_ROOT)
    assert isinstance(findings, list)
    assert len(findings) >= 1


def test_t_sensor_a_2_coverage_boundary_first():
    """COVERAGE_BOUNDARY finding is always first emission (variant #14/#15 chassis pattern)."""
    findings = _run(REPO_ROOT)
    assert findings[0].variant == "path_a_spec_impl_parity"
    assert "COVERAGE_BOUNDARY" in findings[0].description
    assert findings[0].severity == "LOW"


def test_t_sensor_a_3_emits_b1_pebble_firmware_boundary():
    """B1 scope-boundary finding fires because firmware/boards/pebble_tracker.overlay exists."""
    findings = _run(REPO_ROOT)
    b1 = [f for f in findings if "B1 firmware-tree scope boundary" in f.description]
    assert len(b1) == 1, (
        "B1 firmware-scope-boundary finding expected when pebble_tracker.overlay exists. "
        f"Got descriptions: {[f.description[:80] for f in findings]}"
    )
    assert b1[0].file_path == "firmware/boards/pebble_tracker.overlay"


def test_t_sensor_a_4_emits_b2_phi_scope_boundary():
    """B2 scope-boundary finding fires because pre_processor.py is host-side."""
    findings = _run(REPO_ROOT)
    b2 = [f for f in findings if "B2 phi-sanitization scope boundary" in f.description]
    assert len(b2) == 1, (
        "B2 phi-scope-boundary finding expected. "
        f"Got descriptions: {[f.description[:80] for f in findings]}"
    )


def test_t_sensor_a_5_no_probe_marker_misses_on_clean_repo():
    """On a clean repo, all six P-probes (P1-P6) should pass — no marker-miss findings."""
    findings = _run(REPO_ROOT)
    marker_misses = [f for f in findings if "missing expected marker" in f.description]
    assert marker_misses == [], (
        "Sensor A v0.1 expected no probe marker misses on a clean repo. "
        f"Got: {[f.description[:80] for f in marker_misses]}"
    )


def test_t_sensor_a_6_fail_open_on_missing_spec(tmp_path: Path):
    """Variant emits ONE HIGH-severity setup-failure finding and bails when spec absent."""
    # tmp_path has no docs/path-a-manufacturing-spec.md
    findings = _run(tmp_path)
    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert "canonical spec doc" in findings[0].description
    assert findings[0].file_path == "docs/path-a-manufacturing-spec.md"


def test_t_sensor_a_7_severity_distribution_on_real_repo():
    """Severity distribution sanity-check: only LOW + (maybe) MEDIUM on a clean repo."""
    findings = _run(REPO_ROOT)
    severities = {f.severity for f in findings}
    assert severities <= {"LOW", "MEDIUM"}, (
        f"Real-repo run should not emit HIGH/CRITICAL. Got: {severities}"
    )


def test_t_sensor_a_8_never_raises_on_partial_repo(tmp_path: Path):
    """Partial repo with spec present but everything else missing — variant emits findings, never raises."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir()
    (docs_dir / "path-a-manufacturing-spec.md").write_text("# stub spec\n", encoding="utf-8")
    findings = _run(tmp_path)
    # Should emit COVERAGE_BOUNDARY + 6 MEDIUM file-missing P-probes; no B1/B2 (firmware/ + pre_processor.py absent).
    assert findings[0].severity == "LOW"  # COVERAGE_BOUNDARY
    missing_probes = [f for f in findings if "is missing. The Path A spec references" in f.description]
    assert len(missing_probes) == 6, (
        f"Expected 6 file-missing probe findings on stub repo, got: "
        f"{[f.description[:80] for f in missing_probes]}"
    )
    for f in missing_probes:
        assert f.severity == "MEDIUM"
