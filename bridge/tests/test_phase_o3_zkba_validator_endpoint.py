"""Phase O3-ZKBA-TRACK1 Lane B G4 follow-up — bridge HTTP endpoint tests.

Tests for POST /operator/zkba-validate-manifest at operator_api.py.

Mirrors test_phase_o3_zkba_endpoints.py pattern for the existing
GET /operator/zkba-* endpoints. The new endpoint completes the C4 →
c2510883 architectural progression for the G4 validator: Python lib
(scripts/zkba_manifest_validator.py) → MCP tool (knowledge_server.py
vapi_validate_zkba_manifest) → bridge HTTP (this endpoint).

  T-ZKBA-VEP-1  POST happy path: representative GIC manifest → valid=True
                with GIC / CHAIN_ONLY / implementation surface
  T-ZKBA-VEP-2  POST malformed manifest: missing required fields → valid=False
                with errors populated
  T-ZKBA-VEP-3  POST read-key auth — wrong key returns 403
  T-ZKBA-VEP-4  POST non-JSON body returns 422
  T-ZKBA-VEP-5  POST non-object body (JSON array) returns 422
  T-ZKBA-VEP-6  POST surfaces schema_name_form drift (spec_design_time
                vs implementation) for cross-document interop
  T-ZKBA-VEP-7  POST round-trip with all 7 ZKBA classes representative
                manifests (parametrized; mirrors G4 T-MV-1 coverage at
                bridge layer)
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
from pathlib import Path

import pytest

_BRIDGE_DIR = Path(__file__).resolve().parents[1]
_REPO = Path(__file__).resolve().parents[2]
_SCRIPTS = _REPO / "scripts"
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))


def _build_app(tmp_path: Path):
    """Construct a minimal operator_api app for endpoint testing."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    db = str(tmp_path / "test_zkba_vep.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db,
        operator_api_key="k_zkba_vep",
    )
    store = Store(db)
    app = create_operator_app(cfg, store)
    return TestClient(app), store, cfg


def _gic_manifest():
    """Build a representative GIC manifest dict using the G4 helper."""
    from zkba_manifest_validator import build_representative_manifest
    from vapi_bridge.zkba_artifact import ZKBAClass
    return build_representative_manifest(zkba_class=ZKBAClass.GIC)


# --------------------------------------------------------------------------
# T-ZKBA-VEP-1: happy path
# --------------------------------------------------------------------------
def test_t_zkba_vep_1_post_happy_path_gic(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    manifest = _gic_manifest()
    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "k_zkba_vep"},
        json=manifest,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True, f"unexpected errors: {body['errors']}"
    assert body["errors"] == []
    assert body["zkba_class_name"] == "GIC"
    assert body["proof_weight_name"] == "CHAIN_ONLY"
    assert body["schema_name_form"] == "implementation"
    assert "timestamp" in body and isinstance(body["timestamp"], (int, float))


# --------------------------------------------------------------------------
# T-ZKBA-VEP-2: malformed manifest (missing required fields)
# --------------------------------------------------------------------------
def test_t_zkba_vep_2_post_malformed_manifest(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    manifest = _gic_manifest()
    # Remove a required field to trigger validation failure
    del manifest["proof_weight"]
    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "k_zkba_vep"},
        json=manifest,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is False
    assert len(body["errors"]) > 0
    assert any("missing required fields" in e for e in body["errors"])
    # Endpoint preserves fail-open: validator returns result; endpoint
    # does NOT raise 422 for invalid manifest content (422 reserved for
    # body-parsing errors, not content-validation errors)


# --------------------------------------------------------------------------
# T-ZKBA-VEP-3: read-key auth — wrong key returns 403
# --------------------------------------------------------------------------
def test_t_zkba_vep_3_post_wrong_key_403(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "wrong_key"},
        json=_gic_manifest(),
    )
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------
# T-ZKBA-VEP-4: non-JSON body returns 422
# --------------------------------------------------------------------------
def test_t_zkba_vep_4_post_non_json_body(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "k_zkba_vep", "content-type": "application/json"},
        content=b"this is not json",
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "invalid JSON body" in body.get("detail", "")


# --------------------------------------------------------------------------
# T-ZKBA-VEP-5: non-object body (JSON array) returns 422
# --------------------------------------------------------------------------
def test_t_zkba_vep_5_post_non_object_body(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    # JSON list is valid JSON but not a JSON object
    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "k_zkba_vep"},
        json=["a", "b", "c"],
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert "body must be a JSON object" in body.get("detail", "")


# --------------------------------------------------------------------------
# T-ZKBA-VEP-6: schema_name_form drift surfaced for both names
# --------------------------------------------------------------------------
def test_t_zkba_vep_6_schema_name_form_drift_surface(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    manifest = _gic_manifest()
    # Switch schema to the §9.2 design-time name
    manifest["schema"] = "zkba.projection_manifest.v1"
    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "k_zkba_vep"},
        json=manifest,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True, f"errors: {body['errors']}"
    assert body["schema_name_form"] == "spec_design_time", \
        "endpoint must surface §9.2-vs-implementation drift via schema_name_form"


# --------------------------------------------------------------------------
# T-ZKBA-VEP-7: all 7 ZKBA classes round-trip through endpoint
# --------------------------------------------------------------------------
@pytest.mark.parametrize("class_name", [
    "AIT", "GIC", "VHP", "HARDWARE", "CONSENT", "TOURNAMENT", "MARKET",
])
def test_t_zkba_vep_7_all_seven_classes_round_trip(tmp_path, class_name):
    """B.8 G4 7-class coverage mirrored at bridge layer: each ZKBA class
    representative manifest must round-trip cleanly through the
    endpoint."""
    from zkba_manifest_validator import build_representative_manifest
    from vapi_bridge.zkba_artifact import ZKBAClass

    client, _store, _cfg = _build_app(tmp_path)
    zkba_class = ZKBAClass[class_name]
    manifest = build_representative_manifest(zkba_class=zkba_class)

    resp = client.post(
        "/operator/zkba-validate-manifest",
        headers={"x-api-key": "k_zkba_vep"},
        json=manifest,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["valid"] is True, \
        f"class {class_name} default manifest rejected: {body['errors']}"
    assert body["zkba_class_name"] == class_name
    # proof_weight_name must be present + non-empty (specific value per class
    # comes from DEFAULT_PROOF_WEIGHT_BY_CLASS table)
    assert body["proof_weight_name"]
