"""Phase O4-VPM-INTEGRATION Stream B.0-B.3 — VPM registry bridge endpoints.

Test band:
  T-VPM-B0-1:   vpm_artifact_log table created on Store init
  T-VPM-B0-2:   insert_vpm_artifact persists row + idempotent on UNIQUE
  T-VPM-B0-3:   get_vpm_artifact_status returns dict on hit; None on miss
  T-VPM-B0-4:   get_vpm_artifact_history filters by vpm_id + visual_state +
                since_minutes; respects limit; DESC by ts_ns
  T-VPM-B0-5:   get_vpm_artifact_summary aggregates total + per-vpm_id +
                per-visual_state + latest

  T-VPM-B1-1:   GET /operator/vpm-list with read-key returns empty list
                on empty store
  T-VPM-B1-2:   GET /operator/vpm-list filters pass through; missing
                read-key returns 403
  T-VPM-B1-3:   GET /operator/vpm-list since_minutes out-of-range -> 422

  T-VPM-B2-1:   GET /operator/vpm-artifact/{commit} miss returns 200 +
                found=False (NOT 404; matches zkba pattern)
  T-VPM-B2-2:   GET /operator/vpm-artifact/{commit} hit returns HTML body
                + FROZEN CSP header set
  T-VPM-B2-3:   GET /operator/vpm-artifact/{commit} present row but file
                missing returns found=True + file_missing=True

  T-VPM-B3-1:   GET /operator/vpm-manifest/{commit} miss returns
                found=False + manifest=None
  T-VPM-B3-2:   GET /operator/vpm-manifest/{commit} hit returns parsed
                sidecar JSON + db_row metadata
  T-VPM-B3-3:   GET /operator/vpm-manifest/{commit} sidecar missing
                returns found=True + file_missing=True

Author: VAPI Architect (Phase O4 Stream B Commit 1)
"""
from __future__ import annotations

import dataclasses
import json
import os
import sys
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
from vpm_compile_honesty_board import build_honesty_board_artifact  # noqa: E402


# Single shared key for both read and write (per Phase 224 W1 fix:
# operator_api_key serves both _check_read_key and full-key auth)
_API_KEY = "test-operator-key-vpm-b"


def _make_client(tmp_path) -> tuple[TestClient, Store, Config]:
    """Build a TestClient + Store + Config sharing tmp_path-scoped state.

    Config is a frozen dataclass — uses dataclasses.replace to set the
    operator_api_key field (matches the pattern from
    test_phase_o3_zkba_validator_endpoint.py)."""
    db_path = str(tmp_path / "bridge_test.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db_path,
        operator_api_key=_API_KEY,
    )
    store = Store(db_path)
    # create_operator_app signature: (cfg, store) — cfg first
    app = create_operator_app(cfg, store)
    client = TestClient(app)
    return client, store, cfg


# Canonical fixture inputs
_FIXTURE_INTEGRITY_LABEL = {
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


def _insert_canonical_vpm_row(
    store: Store,
    *,
    commitment_hex: str,
    vpm_id: str = "HONESTY-BOARD-v1",
    visual_state: str = "live",
    manifest_uri: str | None = None,
    ts_ns: int = 1779600000000000000,
) -> int:
    """Insert one VPM row into the store via the helper. Returns row id."""
    return store.insert_vpm_artifact(
        commitment_hex=commitment_hex,
        vpm_id=vpm_id,
        zkba_class=2,         # GIC
        proof_weight=1,       # CHAIN_ONLY
        visual_state=visual_state,
        capture_mode="live",
        integrity_label_hash_hex="a" * 64,
        wrapper_schema="vapi-vpm-manifest-v1",
        zkba_manifest_hash_hex="b" * 64,
        manifest_uri=manifest_uri,
        compiler_output_hash_hex="c" * 64,
        preimage_json='{"ts_ns": ' + str(ts_ns) + '}',
        ts_ns=ts_ns,
    )


# ---------------------------------------------------------------------------
# T-VPM-B0-1..5 — store schema + helpers
# ---------------------------------------------------------------------------

def test_t_vpm_b0_1_table_created(tmp_path):
    """vpm_artifact_log table exists on Store init."""
    db_path = str(tmp_path / "test_b01.db")
    store = Store(db_path)
    with store._conn() as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='vpm_artifact_log'"
        ).fetchall()
    assert len(rows) == 1


def test_t_vpm_b0_2_insert_idempotent(tmp_path):
    """insert_vpm_artifact returns same row id on UNIQUE collision."""
    db_path = str(tmp_path / "test_b02.db")
    store = Store(db_path)
    commit = "f" * 64
    row_id_1 = _insert_canonical_vpm_row(store, commitment_hex=commit)
    row_id_2 = _insert_canonical_vpm_row(store, commitment_hex=commit)
    assert row_id_1 == row_id_2
    assert row_id_1 > 0
    # Confirm only one row in table
    with store._conn() as conn:
        cnt = conn.execute("SELECT COUNT(*) FROM vpm_artifact_log").fetchone()[0]
    assert int(cnt) == 1


def test_t_vpm_b0_3_get_status_hit_and_miss(tmp_path):
    db_path = str(tmp_path / "test_b03.db")
    store = Store(db_path)
    commit = "e" * 64
    _insert_canonical_vpm_row(store, commitment_hex=commit)
    hit = store.get_vpm_artifact_status(commit)
    assert hit is not None
    assert hit["commitment_hex"] == commit
    assert hit["vpm_id"] == "HONESTY-BOARD-v1"
    assert hit["visual_state"] == "live"
    miss = store.get_vpm_artifact_status("0" * 64)
    assert miss is None


def test_t_vpm_b0_4_get_history_filters(tmp_path):
    db_path = str(tmp_path / "test_b04.db")
    store = Store(db_path)
    # 4 distinct rows: 2 HONESTY-BOARD (1 live, 1 dry-run), 2 AGENT-REVIEW (live)
    _insert_canonical_vpm_row(store, commitment_hex="1" * 64,
                              vpm_id="HONESTY-BOARD-v1", visual_state="live",
                              ts_ns=1779600000000000000)
    _insert_canonical_vpm_row(store, commitment_hex="2" * 64,
                              vpm_id="HONESTY-BOARD-v1", visual_state="dry-run",
                              ts_ns=1779600000000000100)
    _insert_canonical_vpm_row(store, commitment_hex="3" * 64,
                              vpm_id="AGENT-REVIEW-v1", visual_state="live",
                              ts_ns=1779600000000000200)
    _insert_canonical_vpm_row(store, commitment_hex="4" * 64,
                              vpm_id="AGENT-REVIEW-v1", visual_state="live",
                              ts_ns=1779600000000000300)
    # Unfiltered: 4 rows, DESC ts_ns
    all_rows = store.get_vpm_artifact_history(limit=20)
    assert len(all_rows) == 4
    assert all_rows[0]["commitment_hex"] == "4" * 64
    assert all_rows[-1]["commitment_hex"] == "1" * 64
    # vpm_id filter
    hb = store.get_vpm_artifact_history(vpm_id="HONESTY-BOARD-v1", limit=20)
    assert len(hb) == 2
    assert all(r["vpm_id"] == "HONESTY-BOARD-v1" for r in hb)
    # visual_state filter
    live_only = store.get_vpm_artifact_history(visual_state="live", limit=20)
    assert len(live_only) == 3
    assert all(r["visual_state"] == "live" for r in live_only)
    # Combined filter
    hb_dryrun = store.get_vpm_artifact_history(
        vpm_id="HONESTY-BOARD-v1", visual_state="dry-run", limit=20,
    )
    assert len(hb_dryrun) == 1
    assert hb_dryrun[0]["commitment_hex"] == "2" * 64
    # Limit
    limited = store.get_vpm_artifact_history(limit=2)
    assert len(limited) == 2


def test_t_vpm_b0_5_get_summary_aggregates(tmp_path):
    db_path = str(tmp_path / "test_b05.db")
    store = Store(db_path)
    _insert_canonical_vpm_row(store, commitment_hex="5" * 64,
                              vpm_id="HONESTY-BOARD-v1", visual_state="live",
                              ts_ns=1779600000000000000)
    _insert_canonical_vpm_row(store, commitment_hex="6" * 64,
                              vpm_id="HONESTY-BOARD-v1", visual_state="dry-run",
                              ts_ns=1779600000000000100)
    _insert_canonical_vpm_row(store, commitment_hex="7" * 64,
                              vpm_id="MARKET-LISTING-v1", visual_state="live",
                              ts_ns=1779600000000000200)
    summary = store.get_vpm_artifact_summary()
    assert summary["total_artifacts"] == 3
    assert summary["vpm_id_breakdown"]["HONESTY-BOARD-v1"] == 2
    assert summary["vpm_id_breakdown"]["MARKET-LISTING-v1"] == 1
    assert summary["visual_state_breakdown"]["live"] == 2
    assert summary["visual_state_breakdown"]["dry-run"] == 1
    assert summary["latest"]["commitment_hex"] == "7" * 64  # newest ts_ns


# ---------------------------------------------------------------------------
# T-VPM-B1-1..3 — GET /operator/vpm-list
# ---------------------------------------------------------------------------

def test_t_vpm_b1_1_vpm_list_empty(tmp_path):
    client, store, cfg = _make_client(tmp_path)
    resp = client.get("/operator/vpm-list", headers={"x-api-key": _API_KEY})
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 0
    assert body["rows"] == []
    assert body["filter_summary"]["limit"] == 50  # default


def test_t_vpm_b1_2_vpm_list_filter_passthrough_and_auth(tmp_path):
    client, store, cfg = _make_client(tmp_path)
    # Seed rows
    _insert_canonical_vpm_row(store, commitment_hex="a" * 64,
                              vpm_id="HONESTY-BOARD-v1", visual_state="live")
    _insert_canonical_vpm_row(store, commitment_hex="b" * 64,
                              vpm_id="HONESTY-BOARD-v1", visual_state="dry-run")
    _insert_canonical_vpm_row(store, commitment_hex="c" * 64,
                              vpm_id="AGENT-REVIEW-v1", visual_state="live")

    # Filtered query: vpm_id=HONESTY-BOARD-v1
    resp = client.get(
        "/operator/vpm-list",
        params={"vpm_id": "HONESTY-BOARD-v1"},
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["row_count"] == 2
    assert body["filter_summary"]["vpm_id"] == "HONESTY-BOARD-v1"
    for row in body["rows"]:
        assert row["vpm_id"] == "HONESTY-BOARD-v1"

    # Missing read-key
    resp_no_key = client.get("/operator/vpm-list")
    assert resp_no_key.status_code == 403


def test_t_vpm_b1_3_vpm_list_out_of_range_since_minutes(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.get(
        "/operator/vpm-list",
        params={"since_minutes": 99999},  # > 43200 cap (30 days)
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# T-VPM-B2-1..3 — GET /operator/vpm-artifact/{commit}
# ---------------------------------------------------------------------------

def test_t_vpm_b2_1_vpm_artifact_miss_returns_found_false(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.get(
        f"/operator/vpm-artifact/{'0' * 64}",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["commitment_hex"] == "0" * 64


def test_t_vpm_b2_2_vpm_artifact_hit_serves_html_with_csp_headers(tmp_path):
    client, store, cfg = _make_client(tmp_path)
    # Compile a real HONESTY-BOARD artifact in tmp dir
    art_dir = tmp_path / "vpm_artifacts"
    manifest = build_honesty_board_artifact(
        fleet_phase_aligned=True,
        fleet_phase_target="O1_SHADOW",
        zkba_class_coverage_count=7,
        chain_submission_paused=True,
        cedar_v2_bundles_anchored=True,
        pv_ci_invariants_count=67,
        wallet_balance_iotx="15.03",
        last_anchor_tx_hash="0xabc",
        last_anchor_block=42,
        integrity_label=_FIXTURE_INTEGRITY_LABEL,
        zkba_manifest_hash_hex="b" * 64,
        visual_state="live",
        capture_mode="live",
        output_dir=art_dir,
        ts_ns=1779600000000000000,
    )
    # Record in store
    store.insert_vpm_artifact(
        commitment_hex=manifest.input_commitment_hex,
        vpm_id=manifest.vpm_id,
        zkba_class=manifest.zkba_class,
        proof_weight=manifest.proof_weight,
        visual_state=manifest.visual_state,
        capture_mode=manifest.capture_mode,
        integrity_label_hash_hex=manifest.integrity_label_hash_hex,
        wrapper_schema=manifest.wrapper_schema,
        zkba_manifest_hash_hex=manifest.zkba_manifest_hash_hex,
        manifest_uri=manifest.output_path,
        compiler_output_hash_hex=manifest.output_hash_hex,
        preimage_json='{}',
        ts_ns=manifest.ts_ns,
    )
    # GET the artifact
    resp = client.get(
        f"/operator/vpm-artifact/{manifest.input_commitment_hex}",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    # HTML body returned (not JSON wrapper)
    body_text = resp.text
    assert "VAPI Honesty Board" in body_text
    assert 'class="vpm-integrity-label"' in body_text
    # FROZEN CSP header set
    csp = resp.headers.get("content-security-policy", "")
    assert "default-src 'none'" in csp
    assert "frame-ancestors 'self'" in csp
    assert "form-action 'none'" in csp
    assert resp.headers.get("x-content-type-options") == "nosniff"
    assert resp.headers.get("x-frame-options") == "SAMEORIGIN"
    assert resp.headers.get("referrer-policy") == "no-referrer"
    assert "text/html" in resp.headers.get("content-type", "")


def test_t_vpm_b2_3_vpm_artifact_row_present_file_missing(tmp_path):
    client, store, _ = _make_client(tmp_path)
    # Insert row with a manifest_uri pointing to non-existent file
    commit = "d" * 64
    _insert_canonical_vpm_row(
        store,
        commitment_hex=commit,
        manifest_uri=str(tmp_path / "nonexistent_artifact.html"),
    )
    resp = client.get(
        f"/operator/vpm-artifact/{commit}",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["file_missing"] is True
    assert "missing from disk" in body["reason"]


# ---------------------------------------------------------------------------
# T-VPM-B3-1..3 — GET /operator/vpm-manifest/{commit}
# ---------------------------------------------------------------------------

def test_t_vpm_b3_1_vpm_manifest_miss(tmp_path):
    client, _, _ = _make_client(tmp_path)
    resp = client.get(
        f"/operator/vpm-manifest/{'9' * 64}",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["manifest"] is None
    assert body["db_row"] is None


def test_t_vpm_b3_2_vpm_manifest_hit_returns_sidecar(tmp_path):
    client, store, _ = _make_client(tmp_path)
    # Compile a real artifact (writes HTML + .vpm.manifest.json sidecar)
    art_dir = tmp_path / "vpm_for_manifest"
    manifest = build_honesty_board_artifact(
        fleet_phase_aligned=True,
        fleet_phase_target="O1_SHADOW",
        zkba_class_coverage_count=7,
        chain_submission_paused=True,
        cedar_v2_bundles_anchored=True,
        pv_ci_invariants_count=67,
        wallet_balance_iotx="15.03",
        last_anchor_tx_hash="0xabc",
        last_anchor_block=42,
        integrity_label=_FIXTURE_INTEGRITY_LABEL,
        zkba_manifest_hash_hex="b" * 64,
        visual_state="live",
        capture_mode="live",
        output_dir=art_dir,
        ts_ns=1779600000000000000,
    )
    store.insert_vpm_artifact(
        commitment_hex=manifest.input_commitment_hex,
        vpm_id=manifest.vpm_id,
        zkba_class=manifest.zkba_class,
        proof_weight=manifest.proof_weight,
        visual_state=manifest.visual_state,
        capture_mode=manifest.capture_mode,
        integrity_label_hash_hex=manifest.integrity_label_hash_hex,
        wrapper_schema=manifest.wrapper_schema,
        zkba_manifest_hash_hex=manifest.zkba_manifest_hash_hex,
        manifest_uri=manifest.output_path,
        compiler_output_hash_hex=manifest.output_hash_hex,
        preimage_json='{}',
        ts_ns=manifest.ts_ns,
    )
    resp = client.get(
        f"/operator/vpm-manifest/{manifest.input_commitment_hex}",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["file_missing"] is False
    sidecar = body["manifest"]
    assert sidecar is not None
    # Sidecar fields per VPMArtifactManifest dataclass
    assert sidecar["schema"] == "vapi-vpm-artifact-v1"
    assert sidecar["vpm_id"] == "HONESTY-BOARD-v1"
    assert sidecar["visual_state"] == "live"
    assert len(sidecar["integrity_label_hash_hex"]) == 64
    # DB row metadata also surfaced
    assert body["db_row"]["commitment_hex"] == manifest.input_commitment_hex


def test_t_vpm_b3_3_vpm_manifest_sidecar_missing(tmp_path):
    """Row present + manifest_uri points to nonexistent file -> found=True
    + file_missing=True."""
    client, store, _ = _make_client(tmp_path)
    commit = "8" * 64
    _insert_canonical_vpm_row(
        store,
        commitment_hex=commit,
        manifest_uri=str(tmp_path / "nonexistent.html"),
    )
    resp = client.get(
        f"/operator/vpm-manifest/{commit}",
        headers={"x-api-key": _API_KEY},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is True
    assert body["file_missing"] is True
    assert body["manifest"] is None
    assert "sidecar missing" in body["reason"]
