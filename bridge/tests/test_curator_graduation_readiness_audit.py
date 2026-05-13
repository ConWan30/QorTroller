"""Tests for scripts/curator_graduation_readiness_audit.py.

Validates the consolidated audit harness produces correct verdicts
under each section's PASS/BLOCKED/FAIL state. Tests the section-5
reduction logic directly (section-1..4 already covered by their
respective test bands).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "curator_graduation_readiness_audit.py"

if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

_spec = importlib.util.spec_from_file_location("curator_grad_audit", SCRIPT_PATH)
curator_audit = importlib.util.module_from_spec(_spec)  # type: ignore
sys.modules["curator_grad_audit"] = curator_audit
_spec.loader.exec_module(curator_audit)  # type: ignore


def _mk(verdict_class: str) -> dict:
    """Build a minimal section dict with the requested verdict_class."""
    return {"verdict_class": verdict_class}


# ---- T-CGR-1: all-PASS -> READY exit 0 ---------------------------------

def test_t_cgr_1_all_pass_returns_ready():
    s5 = curator_audit.section_5_consolidated(
        _mk("PASS"), _mk("PASS"), _mk("PASS"), _mk("PASS"),
    )
    assert s5["verdict"] == "READY"
    assert s5["exit_code"] == 0


# ---- T-CGR-2: any FAIL -> FAIL exit 2 ----------------------------------

def test_t_cgr_2_any_fail_returns_fail():
    s5 = curator_audit.section_5_consolidated(
        _mk("PASS"), _mk("FAIL"), _mk("PASS"), _mk("PASS"),
    )
    assert s5["verdict"] == "FAIL"
    assert s5["exit_code"] == 2
    assert "watcher" in s5["reason"]


# ---- T-CGR-3: BLOCKED without FAIL -> BLOCKED exit 1 -------------------

def test_t_cgr_3_blocked_without_fail_returns_blocked():
    s5 = curator_audit.section_5_consolidated(
        _mk("BLOCKED"), _mk("PASS"), _mk("PASS"), _mk("PASS"),
    )
    assert s5["verdict"] == "BLOCKED"
    assert s5["exit_code"] == 1


# ---- T-CGR-4: ERROR -> ERROR exit 3 ------------------------------------

def test_t_cgr_4_error_returns_error():
    s5 = curator_audit.section_5_consolidated(
        _mk("PASS"), _mk("PASS"), _mk("ERROR"), _mk("PASS"),
    )
    assert s5["verdict"] == "ERROR"
    assert s5["exit_code"] == 3


# ---- T-CGR-5: FAIL takes priority over BLOCKED ------------------------

def test_t_cgr_5_fail_priority_over_blocked():
    """If at least one section is FAIL and another is BLOCKED, the
    consolidated verdict is FAIL — FAIL is the higher severity."""
    s5 = curator_audit.section_5_consolidated(
        _mk("BLOCKED"), _mk("FAIL"), _mk("PASS"), _mk("PASS"),
    )
    assert s5["verdict"] == "FAIL"


# ---- T-CGR-6: ERROR takes priority over FAIL -------------------------

def test_t_cgr_6_error_priority_over_fail():
    """ERROR (audit failed to evaluate) takes priority over FAIL (audit
    evaluated and found a hard block). Operator should investigate the
    audit infrastructure before trusting downstream verdicts."""
    s5 = curator_audit.section_5_consolidated(
        _mk("FAIL"), _mk("ERROR"), _mk("PASS"), _mk("PASS"),
    )
    assert s5["verdict"] == "ERROR"


# ---- T-CGR-7: _g7_verdict_class maps correctly -----------------------

def test_t_cgr_7_g7_verdict_class_mapping():
    assert curator_audit._g7_verdict_class("PASS") == "PASS"
    assert curator_audit._g7_verdict_class("BLOCKED") == "BLOCKED"
    assert curator_audit._g7_verdict_class("FAIL") == "FAIL"
    assert curator_audit._g7_verdict_class(
        "FAIL_ZERO_TOLERANCE_VIOLATION"
    ) == "FAIL"
    assert curator_audit._g7_verdict_class("NO_CURATOR_DRAFTS") == "FAIL"
    assert curator_audit._g7_verdict_class("UNKNOWN_VERDICT") == "ERROR"


# ---- T-CGR-8: section_3_cfss live smoke against anchored bundles -----

def test_t_cgr_8_section_3_cfss_live_smoke():
    """Section 3 against the live anchored v2 bundles MUST PASS — the
    bundles were dual-anchored 2026-05-12 and remain byte-stable."""
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    s3 = curator_audit.section_3_cfss(bundle_dir)
    assert s3["verdict_class"] == "PASS"
    assert s3["curator_rows_checked"] == 4
    assert s3["curator_violations"] == 0


# ---- T-CGR-9: section_4_on_chain live smoke against anchored bundles -

def test_t_cgr_9_section_4_on_chain_live_smoke():
    """Section 4 against the live anchored v2 Curator bundle MUST PASS
    — the bundle's recomputed Merkle matches EXPECTED_MERKLES."""
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    s4 = curator_audit.section_4_on_chain(bundle_dir)
    assert s4["verdict_class"] == "PASS"
    assert s4["curator_finding"]["status"] == "MATCH"


# ---- T-CGR-10: JSON output mode produces valid JSON ------------------

def test_t_cgr_10_json_mode_emits_valid_json(capsys):
    """When invoked with --json, the script emits parseable JSON."""
    db_path = PROJECT_ROOT / "bridge" / "vapi_store.db"
    bundle_dir = PROJECT_ROOT / "bridge" / "vapi_bridge" / "cedar_bundles"
    exit_code = curator_audit.main([
        "--db", str(db_path),
        "--bundle-dir", str(bundle_dir),
        "--json",
    ])
    captured = capsys.readouterr()
    parsed = json.loads(captured.out)

    # Exit code is one of {0,1,2,3} per consolidated verdict spec.
    assert exit_code in (0, 1, 2, 3)
    assert "section_5_consolidated_verdict" in parsed
    assert parsed["section_5_consolidated_verdict"]["verdict"] in (
        "READY", "BLOCKED", "FAIL", "ERROR",
    )


# ---- T-CGR-11: render_human handles all verdicts -----------------------

def test_t_cgr_11_render_human_handles_all_verdicts():
    """render_human must not raise on any combination of section
    verdicts. Smoke against synthetic reports."""
    for s1c, s2c, s3c, s4c in [
        ("PASS", "PASS", "PASS", "PASS"),
        ("FAIL", "PASS", "PASS", "PASS"),
        ("BLOCKED", "PASS", "PASS", "PASS"),
        ("ERROR", "PASS", "PASS", "PASS"),
    ]:
        s1 = {"verdict_class": s1c, "reason": "test"}
        s2 = {"verdict_class": s2c, "reason": "test"}
        s3 = {"verdict_class": s3c, "reason": "test"}
        s4 = {"verdict_class": s4c, "reason": "test"}
        s5 = curator_audit.section_5_consolidated(s1, s2, s3, s4)
        report = {
            "timestamp_unix": 1.0,
            "section_1_g7_acceptance_gate": s1,
            "section_2_operator_initiative_watcher": s2,
            "section_3_cfss_lane_authority": s3,
            "section_4_on_chain_anchor_state": s4,
            "section_5_consolidated_verdict": s5,
        }
        rendered = curator_audit.render_human(report)
        assert "FINAL VERDICT" in rendered
        assert s5["verdict"] in rendered
