"""Phase O4-VPM-INT follow-up — HTTP endpoint tests for the 3 audit
harnesses exposed at /operator/g7-curator-readiness +
/operator/cfss-lane-drift-status + /operator/curator-graduation-
readiness.

T-AUDIT-EP-1: G7 endpoint returns 403 without read key
T-AUDIT-EP-2: G7 endpoint returns valid report shape with read key
T-AUDIT-EP-3: CFSS endpoint returns 403 without read key
T-AUDIT-EP-4: CFSS endpoint returns valid report shape against live bundles
T-AUDIT-EP-5: Curator-graduation endpoint returns 403 without read key
T-AUDIT-EP-6: Curator-graduation endpoint returns valid 5-section report
T-AUDIT-EP-7: All three endpoints have http_exit_code or verdict field
T-AUDIT-EP-8: Endpoint paths are pinned (regression guard against rename)
"""
from __future__ import annotations

import dataclasses
import sys
import tempfile
from pathlib import Path

import pytest


_BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


def _build_app(tmp_path: Path):
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    db = str(tmp_path / "test_audit_ep.db")
    # Read-key endpoints use the same operator_api_key field; the
    # _check_read_key function fail-opens when key is empty (dev), so
    # we set a key here to exercise the auth path.
    cfg = dataclasses.replace(
        Config(),
        db_path=db,
        operator_api_key="rk_audit_ep",
    )
    store = Store(db)
    app = create_operator_app(cfg, store)
    return TestClient(app), store, cfg


# ---- T-AUDIT-EP-1: G7 requires read key --------------------------------

def test_t_audit_ep_1_g7_requires_read_key(tmp_path):
    client, _, _ = _build_app(tmp_path)
    r = client.get("/operator/g7-curator-readiness")
    # Operator app is mounted at /operator + inner /operator prefix per
    # the codebase convention documented in commit 51be8db6 (test_phase_
    # o1_c10_e2e_shadow_stack T-O1-C10-6).
    assert r.status_code in (401, 403), (
        f"expected auth failure without read key; got {r.status_code}"
    )


# ---- T-AUDIT-EP-2: G7 returns valid report with read key --------------

def test_t_audit_ep_2_g7_returns_valid_report(tmp_path):
    client, _, _ = _build_app(tmp_path)
    r = client.get(
        "/operator/g7-curator-readiness",
        headers={"x-api-key": "rk_audit_ep"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # G7 audit on fresh DB with no Curator drafts -> NO_CURATOR_DRAFTS
    # verdict (exit 3). Verify the report shape.
    assert "timestamp" in body
    assert "http_exit_code" in body
    assert body["http_exit_code"] in (0, 1, 2, 3, 4)


# ---- T-AUDIT-EP-3: CFSS requires read key ------------------------------

def test_t_audit_ep_3_cfss_requires_read_key(tmp_path):
    client, _, _ = _build_app(tmp_path)
    r = client.get("/operator/cfss-lane-drift-status")
    assert r.status_code in (401, 403)


# ---- T-AUDIT-EP-4: CFSS returns PASS against live anchored bundles ----

def test_t_audit_ep_4_cfss_returns_valid_report(tmp_path):
    client, _, _ = _build_app(tmp_path)
    r = client.get(
        "/operator/cfss-lane-drift-status",
        headers={"x-api-key": "rk_audit_ep"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "verdict" in body
    # Live v2 bundles at HEAD should produce PASS (verified by
    # T-CFSS-1 in test_cfss_lane_drift_sweep.py + T-CGR-8 in
    # test_curator_graduation_readiness_audit.py).
    assert body["verdict"] == "PASS"
    assert body.get("expected_rows") == 12
    assert "timestamp" in body


# ---- T-AUDIT-EP-5: Curator-graduation requires read key ---------------

def test_t_audit_ep_5_curator_grad_requires_read_key(tmp_path):
    client, _, _ = _build_app(tmp_path)
    r = client.get("/operator/curator-graduation-readiness")
    assert r.status_code in (401, 403)


# ---- T-AUDIT-EP-6: Curator-graduation returns 5-section report --------

def test_t_audit_ep_6_curator_grad_returns_valid_report(tmp_path):
    client, _, _ = _build_app(tmp_path)
    r = client.get(
        "/operator/curator-graduation-readiness",
        headers={"x-api-key": "rk_audit_ep"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # 5-section consolidated report shape.
    assert "section_1_g7_acceptance_gate" in body
    assert "section_2_operator_initiative_watcher" in body
    assert "section_3_cfss_lane_authority" in body
    assert "section_4_on_chain_anchor_state" in body
    assert "section_5_consolidated_verdict" in body
    s5 = body["section_5_consolidated_verdict"]
    assert s5["verdict"] in ("READY", "BLOCKED", "FAIL", "ERROR")


# ---- T-AUDIT-EP-7: all 3 endpoints include shape contract fields ------

def test_t_audit_ep_7_all_endpoints_include_shape_fields(tmp_path):
    client, _, _ = _build_app(tmp_path)
    paths = [
        "/operator/g7-curator-readiness",
        "/operator/cfss-lane-drift-status",
        "/operator/curator-graduation-readiness",
    ]
    for path in paths:
        r = client.get(path, headers={"x-api-key": "rk_audit_ep"})
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text}"
        body = r.json()
        # Every audit endpoint MUST include either http_exit_code or
        # verdict (or both — the consolidated audit has both).
        has_exit = "http_exit_code" in body
        has_verdict = "verdict" in body or "final_verdict" in body or (
            "section_5_consolidated_verdict" in body
        )
        assert has_exit or has_verdict, (
            f"{path}: missing exit_code/verdict shape field; got keys "
            f"{list(body.keys())[:10]}"
        )


# ---- T-AUDIT-EP-8: endpoint paths pinned (regression guard) -----------

def test_t_audit_ep_8_endpoint_paths_pinned():
    """Catch accidental rename of any audit endpoint at PR time.
    Frontend code targets these specific paths; renames break the
    Operator Console dashboards without test failure if not pinned."""
    src = Path(__file__).resolve().parents[1] / "vapi_bridge" / "operator_api.py"
    text = src.read_text(encoding="utf-8")
    for path in (
        '"/operator/g7-curator-readiness"',
        '"/operator/cfss-lane-drift-status"',
        '"/operator/curator-graduation-readiness"',
    ):
        assert path in text, (
            f"Endpoint path {path} not pinned in operator_api.py — "
            f"frontend Operator Console dashboards will break silently"
        )
