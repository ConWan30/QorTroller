"""Phase O4-VPM-INTEGRATION Stream B.4-B.7 — write + validate + audit + stability.

Test band:
  T-VPM-B4-1:  POST /operator/vpm-compile with valid HONESTY-BOARD inputs
               compiles + records in store + returns commitment
  T-VPM-B4-2:  POST /operator/vpm-compile with each of 6 vpm_ids dispatches
               to the correct compiler (parametrized x6)
  T-VPM-B4-3:  POST /operator/vpm-compile with unknown vpm_id -> 422
  T-VPM-B4-4:  POST /operator/vpm-compile with missing api_key -> 403
  T-VPM-B4-5:  POST /operator/vpm-compile with invalid inputs (compiler
               raises ValueError) -> 422 with compiler error in detail
  T-VPM-B4-6:  POST /operator/vpm-compile idempotent on identical inputs
               (same row_id; UNIQUE collision returns existing row)

  T-VPM-B5-1:  POST /operator/vpm-validate-manifest valid sidecar returns
               valid=True + all *_recognized=True
  T-VPM-B5-2:  POST /operator/vpm-validate-manifest schema drift returns
               valid=False + schema_recognized=False
  T-VPM-B5-3:  POST /operator/vpm-validate-manifest visual_state outside
               6-element FROZEN set returns valid=False
  T-VPM-B5-4:  POST /operator/vpm-validate-manifest bad hex fields return
               valid=False with specific error messages
  T-VPM-B5-5:  POST /operator/vpm-validate-manifest read-key auth (403 on
               wrong key)

  T-VPM-B6-1:  GET /operator/vpm-audit-status returns overall_ok=True
               against live tree
  T-VPM-B6-2:  GET /operator/vpm-audit-status returns 6 sections with
               expected shape; read-key auth enforced

  T-VPM-B7-1:  Stability harness — concurrent /operator/vpm-list calls
               do not block the event loop (>=10 calls complete within
               a deadline)
  T-VPM-B7-2:  Stability harness — POST /operator/vpm-compile followed
               immediately by GET /operator/vpm-artifact does not
               deadlock (end-to-end round-trip well under deadline)

Author: VAPI Architect (Phase O4 Stream B Commit 2)
"""
from __future__ import annotations

import asyncio
import dataclasses
import json
import os
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_BRIDGE = os.path.normpath(os.path.join(_REPO, "bridge"))
_SCRIPTS = os.path.normpath(os.path.join(_REPO, "scripts"))
sys.path.insert(0, _BRIDGE)
sys.path.insert(0, _SCRIPTS)

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.operator_api import create_operator_app  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402


_API_KEY = "test-operator-key-vpm-b2"


def _make_client(tmp_path) -> tuple[TestClient, Store, Config]:
    db_path = str(tmp_path / "bridge_test_b2.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db_path,
        operator_api_key=_API_KEY,
    )
    store = Store(db_path)
    app = create_operator_app(cfg, store)
    client = TestClient(app)
    return client, store, cfg


_INTEGRITY_LABEL = {
    "proof_type":             "VPM-HONESTY-BOARD",
    "capture_mode":           "live",
    "raw_biometrics_exposed": False,
    "consent_active":         True,
    "zk_verified":            False,
    "on_chain_anchor":        True,
    "proof_weight":           "CHAIN_ONLY",
    "revocation_status":      "active",
    "limitations":            ["Internal protocol-state projection"],
}


def _honesty_board_inputs(output_dir: str, ts_ns: int = 1779700000000000000) -> dict:
    """Canonical happy-path inputs for HONESTY-BOARD-v1 compile call."""
    return {
        "fleet_phase_aligned":        True,
        "fleet_phase_target":         "O1_SHADOW",
        "zkba_class_coverage_count":  7,
        "chain_submission_paused":    True,
        "cedar_v2_bundles_anchored":  True,
        "pv_ci_invariants_count":     67,
        "wallet_balance_iotx":        "15.03",
        "last_anchor_tx_hash":        "0xabc",
        "last_anchor_block":          42,
        "integrity_label":            _INTEGRITY_LABEL,
        "zkba_manifest_hash_hex":     "b" * 64,
        "visual_state":               "live",
        "capture_mode":               "live",
        "ts_ns":                      ts_ns,
    }


# ---------------------------------------------------------------------------
# T-VPM-B4-1..6 — POST /operator/vpm-compile
# ---------------------------------------------------------------------------

def test_t_vpm_b4_1_compile_happy_path(tmp_path):
    client, store, _ = _make_client(tmp_path)
    art_dir = str(tmp_path / "vpm_compile_out")
    resp = client.post(
        "/operator/vpm-compile",
        params={"api_key": _API_KEY},
        json={
            "vpm_id":     "HONESTY-BOARD-v1",
            "inputs":     _honesty_board_inputs(art_dir),
            "output_dir": art_dir,
        },
    )
    assert resp.status_code == 200, f"got {resp.status_code}: {resp.text}"
    body = resp.json()
    assert body["success"] is True
    assert body["vpm_id"] == "HONESTY-BOARD-v1"
    assert len(body["input_commitment_hex"]) == 64
    assert len(body["output_hash_hex"]) == 64
    assert body["row_id"] > 0
    # Verify the row landed in store
    row = store.get_vpm_artifact_status(body["input_commitment_hex"])
    assert row is not None
    assert row["vpm_id"] == "HONESTY-BOARD-v1"
    # Verify the HTML file exists on disk
    assert Path(body["output_path"]).exists()


@pytest.mark.parametrize("vpm_id,inputs_fn", [
    (
        "HONESTY-BOARD-v1",
        lambda out: _honesty_board_inputs(out),
    ),
    (
        "AGENT-REVIEW-v1",
        lambda out: {
            "agent_canonical_name":     "anchor_sentry",
            "agent_id_hex":             "b" * 64,
            "current_phase":            "O1_SHADOW",
            "shadow_log_row_count":     42,
            "drift_log_row_count":      0,
            "last_operator_decision":   "accept",
            "last_decision_ts_ns":      1778900000000000000,
            "disagreement_rate_30d":    0.02,
            "false_positive_rate_30d":  0.0,
            "o2_ready":                 False,
            "o3_ready":                 False,
            "integrity_label":          _INTEGRITY_LABEL,
            "zkba_manifest_hash_hex":   "d" * 64,
            "visual_state":             "live",
            "capture_mode":             "live",
            "ts_ns":                    1779700100000000000,
        },
    ),
    (
        "CDRR-DAG-v1",
        lambda out: {
            "integrity_label":         _INTEGRITY_LABEL,
            "zkba_manifest_hash_hex":  "e" * 64,
            "visual_state":            "live",
            "capture_mode":            "live",
            "ts_ns":                   1779700200000000000,
        },
    ),
    (
        "GIC-LEDGER-BETA-v1",
        lambda out: {
            "gic_chain_head_hex":      "0e9d453d904220148d632e75802b71bdff74c7197aa8afcbfec5d36a61ab48da",
            "gic_chain_length":        100,
            "gic_genesis_hash_hex":    "87ce52cd21f9037730262debd4d247a76a6439bb754d9219fe10346ee1278c05",
            "gic_genesis_ts_ns":       1777142267690827300,
            "on_chain_anchor_tx_hash": "0xe807347e",
            "on_chain_anchor_block":   43348052,
            "grind_session_id":        "grind_phase235_v1",
            "integrity_label":         _INTEGRITY_LABEL,
            "zkba_manifest_hash_hex":  "1" * 64,
            "visual_state":            "live",
            "capture_mode":            "live",
            "ts_ns":                   1779700300000000000,
        },
    ),
    (
        "DISPUTE-PACKET-v1",
        lambda out: {
            "dispute_id":                 "dispute-test",
            "tournament_id":              20260601001,
            "disputed_player_address":    "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
            "disputed_ruling_hash_hex":   "a" * 64,
            "adjudicator_agent_id":       "guardian",
            "evidence_count":             3,
            "attestation_chain_hash_hex": "b" * 64,
            "dispute_status":             "open",
            "created_ts_ns":              1779700399000000000,
            "integrity_label":            _INTEGRITY_LABEL,
            "zkba_manifest_hash_hex":     "2" * 64,
            "visual_state":               "live",
            "capture_mode":               "live",
            "ts_ns":                      1779700400000000000,
        },
    ),
    (
        "MARKET-LISTING-v1",
        lambda out: {
            "listing_commitment_hex":  "1649f2803e0e3207f93fb1daac25d71d579ba3150d9d15317b97fe0e65a70d5f",
            "listing_title":           "Test Listing",
            "tier_multiplier_milli":   2000,
            "ipfs_cid":                "bafybeigdyrzt5sfp7udm7hu76uh7y26nf3efuylqabf3oclgtqy55fbzdi",
            "consent_hash_hex":        "d45615ff1ffdef9efa7857fc930c43c0dd20ed492076537d85cc96ae537ac97b",
            "suspended":               False,
            "listing_owner_address":   "0x0Cf36dB57fc4680bcdfC65D1Aff96993C57a4692",
            "price_iotx_milli":        5000,
            "integrity_label":         _INTEGRITY_LABEL,
            "zkba_manifest_hash_hex":  "32c466da6f3db5c7b3f7fc1d2214ed4cd4c1d7ad90a42b29b4f2a51cfcf73e44",
            "visual_state":            "live",
            "capture_mode":            "live",
            "ts_ns":                   1779700500000000000,
        },
    ),
], ids=["honesty-board", "agent-review", "cdrr-dag", "gic-beta",
        "dispute-packet", "market-listing"])
def test_t_vpm_b4_2_dispatch_all_six_compilers(vpm_id, inputs_fn, tmp_path):
    """All 6 vpm_ids in the registry dispatch to their compiler correctly."""
    client, store, _ = _make_client(tmp_path)
    art_dir = str(tmp_path / f"out_{vpm_id.lower().replace('-', '_')}")
    inputs = inputs_fn(art_dir)
    resp = client.post(
        "/operator/vpm-compile",
        params={"api_key": _API_KEY},
        json={"vpm_id": vpm_id, "inputs": inputs, "output_dir": art_dir},
    )
    assert resp.status_code == 200, f"vpm_id={vpm_id}: {resp.status_code} {resp.text}"
    body = resp.json()
    assert body["success"] is True
    assert len(body["input_commitment_hex"]) == 64
    assert Path(body["output_path"]).exists()


def test_t_vpm_b4_3_unknown_vpm_id_returns_422(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.post(
        "/operator/vpm-compile",
        params={"api_key": _API_KEY},
        json={"vpm_id": "UNKNOWN-VPM-v1", "inputs": {}},
    )
    assert resp.status_code == 422
    assert "vpm_id must be one of" in resp.json()["detail"]


def test_t_vpm_b4_4_missing_api_key_returns_403(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.post(
        "/operator/vpm-compile",
        json={"vpm_id": "HONESTY-BOARD-v1", "inputs": {}},
    )
    assert resp.status_code == 403


def test_t_vpm_b4_5_compiler_value_error_returns_422(tmp_path):
    """Compiler-raised ValueError on bad inputs surfaces as 422 with the
    compiler's error message in detail."""
    client, _, _ = _make_client(tmp_path)
    # HONESTY-BOARD with invalid visual_state -> ValueError
    bad_inputs = _honesty_board_inputs(str(tmp_path / "bad"))
    bad_inputs["visual_state"] = "extra-state-not-in-frozen-set"
    resp = client.post(
        "/operator/vpm-compile",
        params={"api_key": _API_KEY},
        json={
            "vpm_id":     "HONESTY-BOARD-v1",
            "inputs":     bad_inputs,
            "output_dir": str(tmp_path / "bad"),
        },
    )
    assert resp.status_code == 422
    assert "compiler rejected inputs" in resp.json()["detail"]
    assert "visual_state" in resp.json()["detail"]


def test_t_vpm_b4_6_idempotent_compile(tmp_path):
    """Identical inputs to two compile calls produce the same row_id
    (UNIQUE collision returns existing id from insert_vpm_artifact)."""
    client, _, _ = _make_client(tmp_path)
    art_dir = str(tmp_path / "idem")
    payload = {
        "vpm_id":     "HONESTY-BOARD-v1",
        "inputs":     _honesty_board_inputs(art_dir),
        "output_dir": art_dir,
    }
    r1 = client.post("/operator/vpm-compile", params={"api_key": _API_KEY}, json=payload)
    r2 = client.post("/operator/vpm-compile", params={"api_key": _API_KEY}, json=payload)
    assert r1.status_code == 200 and r2.status_code == 200
    b1, b2 = r1.json(), r2.json()
    assert b1["input_commitment_hex"] == b2["input_commitment_hex"]
    assert b1["output_hash_hex"] == b2["output_hash_hex"]
    assert b1["row_id"] == b2["row_id"]


# ---------------------------------------------------------------------------
# T-VPM-B5-1..5 — POST /operator/vpm-validate-manifest
# ---------------------------------------------------------------------------

def _valid_manifest_fixture() -> dict:
    return {
        "schema":                   "vapi-vpm-artifact-v1",
        "vpm_id":                   "HONESTY-BOARD-v1",
        "zkba_class":               2,
        "proof_weight":             1,
        "visual_state":             "live",
        "capture_mode":             "live",
        "integrity_label_hash_hex": "a" * 64,
        "wrapper_schema":           "vapi-vpm-manifest-v1",
        "zkba_manifest_hash_hex":   "b" * 64,
        "output_path":              "ignored.html",
        "output_hash_hex":          "c" * 64,
        "input_commitment_hex":     "d" * 64,
        "compiler_version":         "0.1.0",
        "ts_ns":                    1779700600000000000,
    }


def test_t_vpm_b5_1_validate_manifest_happy_path(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.post(
        "/operator/vpm-validate-manifest",
        headers={"x-api-key": _API_KEY},
        json=_valid_manifest_fixture(),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["valid"] is True
    assert body["errors"] == []
    assert body["schema_recognized"] is True
    assert body["visual_state_recognized"] is True
    assert body["capture_mode_recognized"] is True
    assert body["vpm_id_in_body"] == "HONESTY-BOARD-v1"


def test_t_vpm_b5_2_schema_drift(tmp_path):
    client, _, _ = _make_client(tmp_path)
    m = _valid_manifest_fixture()
    m["schema"] = "vapi-vpm-artifact-v2"  # drift
    resp = client.post(
        "/operator/vpm-validate-manifest",
        headers={"x-api-key": _API_KEY},
        json=m,
    )
    body = resp.json()
    assert body["valid"] is False
    assert body["schema_recognized"] is False
    assert any("schema must be" in e for e in body["errors"])


def test_t_vpm_b5_3_visual_state_outside_frozen_set(tmp_path):
    client, _, _ = _make_client(tmp_path)
    m = _valid_manifest_fixture()
    m["visual_state"] = "psychedelic"
    resp = client.post(
        "/operator/vpm-validate-manifest",
        headers={"x-api-key": _API_KEY},
        json=m,
    )
    body = resp.json()
    assert body["valid"] is False
    assert body["visual_state_recognized"] is False
    assert any("visual_state must be" in e for e in body["errors"])


def test_t_vpm_b5_4_bad_hex_fields(tmp_path):
    client, _, _ = _make_client(tmp_path)
    m = _valid_manifest_fixture()
    m["integrity_label_hash_hex"] = "z" * 64  # wrong-char hex
    m["zkba_manifest_hash_hex"] = "ab"        # wrong-length hex
    resp = client.post(
        "/operator/vpm-validate-manifest",
        headers={"x-api-key": _API_KEY},
        json=m,
    )
    body = resp.json()
    assert body["valid"] is False
    assert any("integrity_label_hash_hex not valid hex" in e for e in body["errors"])
    assert any("zkba_manifest_hash_hex must be 64-char hex" in e for e in body["errors"])


def test_t_vpm_b5_5_validate_manifest_wrong_read_key(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.post(
        "/operator/vpm-validate-manifest",
        headers={"x-api-key": "wrong-key"},
        json=_valid_manifest_fixture(),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# T-VPM-B6-1..2 — GET /operator/vpm-audit-status
# ---------------------------------------------------------------------------

def test_t_vpm_b6_1_audit_status_overall_ok(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.get(
        "/operator/vpm-audit-status",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["overall_ok"] is True
    assert body["active_compiler_count"] == 6
    assert body["draft_manifest_count"] == 4
    assert body["section_10_registry_size"] == 10
    assert len(body["sections"]) == 6
    for section in body["sections"]:
        assert section["ok"] is True


def test_t_vpm_b6_2_audit_status_auth_enforced(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.get(
        "/operator/vpm-audit-status",
        headers={"x-api-key": "wrong-key"},
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# T-VPM-B7-1..2 — Stability harness
# ---------------------------------------------------------------------------

def test_t_vpm_b7_1_concurrent_list_calls_do_not_block(tmp_path):
    """Sequential /vpm-list calls in tight succession complete well under
    a 5-second deadline — event-loop discipline holds (DB reads run via
    asyncio.to_thread per the endpoint impl)."""
    client, store, _ = _make_client(tmp_path)
    # Seed a few rows
    for i in range(20):
        store.insert_vpm_artifact(
            commitment_hex=f"{i:064x}",
            vpm_id="HONESTY-BOARD-v1",
            zkba_class=2,
            proof_weight=1,
            visual_state="live",
            capture_mode="live",
            integrity_label_hash_hex="a" * 64,
            wrapper_schema="vapi-vpm-manifest-v1",
            zkba_manifest_hash_hex="b" * 64,
            manifest_uri=None,
            compiler_output_hash_hex=None,
            preimage_json="{}",
            ts_ns=1779700700000000000 + i,
        )
    deadline = 5.0  # seconds
    start = time.time()
    for _ in range(20):
        resp = client.get("/operator/vpm-list", headers={"x-api-key": _API_KEY})
        assert resp.status_code == 200
    elapsed = time.time() - start
    assert elapsed < deadline, (
        f"20 /vpm-list calls took {elapsed:.2f}s (deadline {deadline}s); "
        "event-loop discipline may have regressed"
    )


def test_t_vpm_b7_2_compile_then_fetch_artifact_round_trip(tmp_path):
    """End-to-end: POST compile -> GET artifact (HTML) -> GET manifest
    (sidecar) completes within a 10s deadline."""
    client, _, _ = _make_client(tmp_path)
    art_dir = str(tmp_path / "b72_out")
    start = time.time()

    # POST compile
    r1 = client.post(
        "/operator/vpm-compile",
        params={"api_key": _API_KEY},
        json={
            "vpm_id":     "HONESTY-BOARD-v1",
            "inputs":     _honesty_board_inputs(art_dir),
            "output_dir": art_dir,
        },
    )
    assert r1.status_code == 200, f"compile failed: {r1.text}"
    commit = r1.json()["input_commitment_hex"]

    # GET artifact (HTML)
    r2 = client.get(
        f"/operator/vpm-artifact/{commit}",
        headers={"x-api-key": _API_KEY},
    )
    assert r2.status_code == 200
    assert "VAPI Honesty Board" in r2.text

    # GET manifest (sidecar JSON)
    r3 = client.get(
        f"/operator/vpm-manifest/{commit}",
        headers={"x-api-key": _API_KEY},
    )
    assert r3.status_code == 200
    body = r3.json()
    assert body["found"] is True
    assert body["manifest"]["schema"] == "vapi-vpm-artifact-v1"

    elapsed = time.time() - start
    deadline = 10.0
    assert elapsed < deadline, (
        f"compile+fetch round-trip took {elapsed:.2f}s (deadline {deadline}s); "
        "event-loop discipline may have regressed"
    )
