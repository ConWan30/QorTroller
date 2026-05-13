"""Tests for scripts/cfss_lane_drift_sweep.py.

Validates the CFSS Cedar-policy lane authority drift detector ships
correct semantics: PASS against live anchored bundles, CFSS_VIOLATION
on synthetic bundle tamper, BUNDLE_LOAD_ERROR on missing files,
CONFIG_ERROR on missing dir.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "cfss_lane_drift_sweep.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("cfss_drift", SCRIPT_PATH)
cfss_drift = importlib.util.module_from_spec(_spec)  # type: ignore
sys.modules["cfss_drift"] = cfss_drift
_spec.loader.exec_module(cfss_drift)  # type: ignore

LIVE_BUNDLE_DIR = (
    PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
)


def _copy_v2_bundles(target_dir: Path) -> None:
    """Copy the three live v2 bundle files into target_dir."""
    for fname in (
        "anchor_sentry_o2_suggest_v2.json",
        "guardian_o2_suggest_v2.json",
        "curator_o2_suggest_v2.json",
    ):
        src = LIVE_BUNDLE_DIR / fname
        dst = target_dir / fname
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")


# ---- T-CFSS-1: live anchored bundles -> PASS exit 0 -------------------

def test_t_cfss_1_live_bundles_pass():
    """Sweeping against the live v2 bundles should produce PASS — these
    are the bundles that were dual-anchored 2026-05-12."""
    report = cfss_drift.sweep_once(LIVE_BUNDLE_DIR)
    assert report["verdict"] == "PASS"
    assert report["exit_code"] == 0
    assert len(report["violations"]) == 0
    assert len(report["rows"]) == 12  # matches EXPECTED_LANE_MATRIX cardinality


# ---- T-CFSS-2: missing bundle dir -> CONFIG_ERROR exit 3 --------------

def test_t_cfss_2_missing_dir_returns_config_error():
    nonexistent = Path("/this/path/should/not/exist/cedar_bundles")
    report = cfss_drift.sweep_once(nonexistent)
    assert report["verdict"] == "CONFIG_ERROR"
    assert report["exit_code"] == 3


# ---- T-CFSS-3: missing bundle file -> BUNDLE_LOAD_ERROR exit 2 --------

def test_t_cfss_3_missing_bundle_returns_load_error():
    with tempfile.TemporaryDirectory() as tmp:
        # Empty dir — no bundles inside.
        report = cfss_drift.sweep_once(Path(tmp))
        assert report["verdict"] == "BUNDLE_LOAD_ERROR"
        assert report["exit_code"] == 2
        assert len(report["bundle_load_errors"]) > 0


# ---- T-CFSS-4: tampered bundle (Sentry policy removed) -> VIOLATION ----

def test_t_cfss_4_removed_permit_detected():
    """If a permit policy is removed from a v2 bundle (silent tamper),
    the matrix evaluation surfaces CFSS_VIOLATION."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _copy_v2_bundles(tmp_path)

        # Tamper: remove Sentry's zk-artifact-anchor permit policy.
        sentry_path = tmp_path / "anchor_sentry_o2_suggest_v2.json"
        bundle = json.loads(sentry_path.read_text(encoding="utf-8"))
        bundle["policies"] = [
            p for p in bundle["policies"]
            if not (
                p.get("effect") == "permit"
                and p.get("action") == "tool:zk-artifact-anchor"
            )
        ]
        sentry_path.write_text(json.dumps(bundle), encoding="utf-8")

        report = cfss_drift.sweep_once(tmp_path)
        assert report["verdict"] == "CFSS_VIOLATION"
        assert report["exit_code"] == 1
        # The removed permit should be in the violation list.
        violation_actions = {v["action"] for v in report["violations"]}
        assert "tool:zk-artifact-anchor" in violation_actions


# ---- T-CFSS-5: tampered bundle (cross-lane permit injected) -> VIOLATION ----

def test_t_cfss_5_injected_cross_lane_permit_detected():
    """If a cross-fleet permit (Curator gaining zk-artifact-anchor) is
    silently injected, matrix evaluation surfaces CFSS_VIOLATION on
    Curator's row — Curator's expected effect for zk-artifact-anchor is
    'forbid'."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _copy_v2_bundles(tmp_path)

        # Tamper: append a permit policy for zk-artifact-anchor to Curator.
        # This is the most security-relevant CFSS violation — Curator
        # gaining write authority over Sentry's zk_artifacts/ lane.
        curator_path = tmp_path / "curator_o2_suggest_v2.json"
        bundle = json.loads(curator_path.read_text(encoding="utf-8"))

        # Remove the existing forbid + replace with permit, to simulate
        # a policy-substitution attack.
        bundle["policies"] = [
            p for p in bundle["policies"]
            if not (
                p.get("action") == "tool:zk-artifact-anchor"
            )
        ]
        # Inject the cross-lane permit.
        bundle["policies"].append({
            "effect": "permit",
            "action": "tool:zk-artifact-anchor",
            "resource": "draft://zk_artifacts/*",
        })
        curator_path.write_text(json.dumps(bundle), encoding="utf-8")

        report = cfss_drift.sweep_once(tmp_path)
        assert report["verdict"] == "CFSS_VIOLATION"
        assert report["exit_code"] == 1

        # Curator should have a violation on tool:zk-artifact-anchor row.
        curator_violations = [
            v for v in report["violations"]
            if v["agent_id"] == "curator"
            and v["action"] == "tool:zk-artifact-anchor"
        ]
        assert len(curator_violations) == 1
        v = curator_violations[0]
        assert v["expected_effect"] == "forbid"
        assert v["actual_effect"] == "permit"


# ---- T-CFSS-6: malformed JSON bundle -> BUNDLE_LOAD_ERROR exit 2 -------

def test_t_cfss_6_malformed_json_returns_load_error():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        _copy_v2_bundles(tmp_path)

        # Corrupt one bundle file with non-JSON content.
        sentry_path = tmp_path / "anchor_sentry_o2_suggest_v2.json"
        sentry_path.write_text("{not json", encoding="utf-8")

        report = cfss_drift.sweep_once(tmp_path)
        assert report["verdict"] == "BUNDLE_LOAD_ERROR"
        assert report["exit_code"] == 2


# ---- T-CFSS-7: JSON output mode produces valid JSON --------------------

def test_t_cfss_7_json_mode_emits_valid_json(capsys):
    exit_code = cfss_drift.main([
        "--bundle-dir", str(LIVE_BUNDLE_DIR),
        "--json",
    ])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    assert exit_code == 0
    assert parsed["verdict"] == "PASS"
    assert parsed["expected_rows"] == 12
    assert "rows" in parsed and len(parsed["rows"]) == 12


# ---- T-CFSS-8: EXPECTED_LANE_MATRIX has 12 rows -----------------------

def test_t_cfss_8_expected_matrix_cardinality_pinned():
    """The CFSS triangle is a 3-agent × 4-row matrix = 12 rows.
    Catch accidental matrix shrinkage at PR time."""
    assert len(cfss_drift.EXPECTED_LANE_MATRIX) == 12

    # Verify every agent appears in exactly 4 rows.
    by_agent = {}
    for row in cfss_drift.EXPECTED_LANE_MATRIX:
        agent_id = row[0]
        by_agent[agent_id] = by_agent.get(agent_id, 0) + 1
    assert by_agent == {
        "anchor_sentry": 4,
        "guardian": 4,
        "curator": 4,
    }


# ---- T-CFSS-9: every row's expected_effect is in valid set ------------

def test_t_cfss_9_expected_effects_are_canonical():
    """expected_effect must be 'permit' or 'forbid' — these are the only
    two Cedar v2 effect values. Catch accidental new-effect introduction."""
    valid = {"permit", "forbid"}
    for row in cfss_drift.EXPECTED_LANE_MATRIX:
        _, _, _, expected_effect = row
        assert expected_effect in valid
