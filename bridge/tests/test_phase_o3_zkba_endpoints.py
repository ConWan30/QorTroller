"""Phase O3-ZKBA-TRACK1 (post-C5) — VAPIZKBA bridge HTTP endpoint tests.

Closes the wire-contract loop with VAPIZKBA SDK shipped at C4. The SDK
class at sdk/vapi_sdk.py:9170+ was wire-locked against future endpoints;
this test file proves the endpoints now satisfy that contract.

Endpoint surface under test:
  - GET /operator/zkba-status                       (read-key)
  - GET /operator/zkba-artifact/{commitment_hex}    (read-key)
  - GET /operator/zkba-history?limit=N              (read-key)

  T-ZKBA-EP-1: GET /operator/zkba-status — empty DB returns zero-state
               shape (total=0, anchored=0, holds=True, latest={},
               frozen_v1_position=10, domain_tag=VAPI-ZKBA-ARTIFACT-v1)
  T-ZKBA-EP-2: GET /operator/zkba-status — seeded artifacts surface in
               total + class_breakdown + latest (DESC by ts_ns)
  T-ZKBA-EP-3: GET /operator/zkba-status — wrong x-api-key returns 403
               (read-key auth contract)
  T-ZKBA-EP-4: GET /operator/zkba-artifact/<missing_hex> — found=False
               (NOT 404; SDK consumes the boolean)
  T-ZKBA-EP-5: GET /operator/zkba-artifact/<seeded_hex> — found=True +
               db_row populated with commitment_hex / zkba_class /
               proof_weight / preimage_json / ts_ns / manifest_uri /
               compiler_output_hash_hex / anchor_tx_hash NULL / created_at
  T-ZKBA-EP-6: GET /operator/zkba-history — default limit; DESC ts_ns
               order; row_count matches rows length
  T-ZKBA-EP-7: GET /operator/zkba-history?limit=0 → 422; limit=501 → 422
               (Query bounds 1..500)
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path

import pytest

_BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


def _build_app(tmp_path: Path):
    """Construct a minimal operator_api app for endpoint testing."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    db = str(tmp_path / "test_o3_zkba_ep.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db,
        operator_api_key="k_zkba_ep",
    )
    store = Store(db)
    app = create_operator_app(cfg, store)
    return TestClient(app), store, cfg


def _seed_zkba(store, *, n: int, base_ts_ns: int = 1_700_000_000_000_000_000) -> list[str]:
    """Seed N ZKBA artifacts under varying classes + monotonic ts_ns. Returns
    the list of commitment hex strings in insertion order (oldest first)."""
    hexes: list[str] = []
    for i in range(n):
        hex_i = f"{i:064x}"
        # Vary zkba_class across [1, 2, 3] (AIT/GIC/VHP) to exercise breakdown
        zkba_class = (i % 3) + 1
        store.insert_zkba_artifact(
            zkba_class=zkba_class,
            proof_weight=3,  # CHAIN_ONLY (Track 1 invariant for GIC ledger)
            commitment_hex=hex_i,
            preimage_json=f'{{"i":{i}}}',
            ts_ns=base_ts_ns + i,
            manifest_uri=f"file://manifest_{i}.json",
            compiler_output_hash_hex=f"output_hash_{i:056x}",
        )
        hexes.append(hex_i)
    return hexes


# --------------------------------------------------------------------------
# T-ZKBA-EP-1: status on empty DB
# --------------------------------------------------------------------------
def test_t_zkba_ep_1_status_empty_db_zero_state(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    resp = client.get(
        "/operator/zkba-status",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_artifacts"] == 0
    assert body["anchored_count"] == 0
    assert body["track1_invariant_holds"] is True
    assert body["class_breakdown"] == {}
    assert body["latest"] == {}
    assert body["frozen_v1_position"] == 10
    assert body["domain_tag"] == "VAPI-ZKBA-ARTIFACT-v1"
    assert "timestamp" in body and isinstance(body["timestamp"], float)


# --------------------------------------------------------------------------
# T-ZKBA-EP-2: status reflects seeded artifacts + class_breakdown + latest
# --------------------------------------------------------------------------
def test_t_zkba_ep_2_status_with_seeded_artifacts(tmp_path):
    client, store, _cfg = _build_app(tmp_path)
    hexes = _seed_zkba(store, n=5)  # 5 artifacts; classes 1,2,3,1,2

    resp = client.get(
        "/operator/zkba-status",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total_artifacts"] == 5
    assert body["anchored_count"] == 0
    assert body["track1_invariant_holds"] is True
    # class_breakdown is JSON-serialised with str keys
    cb = body["class_breakdown"]
    # class 1 (AIT): i in {0, 3} → 2; class 2 (GIC): i in {1, 4} → 2;
    # class 3 (VHP): i in {2} → 1.
    assert cb == {"1": 2, "2": 2, "3": 1}
    # Latest is the newest by ts_ns (DESC) — last inserted (i=4).
    assert body["latest"]["commitment_hex"] == hexes[4]
    assert body["latest"]["zkba_class"] == 2  # (4 % 3) + 1
    assert body["latest"]["proof_weight"] == 3


# --------------------------------------------------------------------------
# T-ZKBA-EP-3: read-key auth — wrong key 403
# --------------------------------------------------------------------------
def test_t_zkba_ep_3_status_auth_wrong_key_403(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    resp = client.get(
        "/operator/zkba-status",
        headers={"x-api-key": "wrong_key"},
    )
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------------
# T-ZKBA-EP-4: get-artifact on miss returns found=False (NOT 404)
# --------------------------------------------------------------------------
def test_t_zkba_ep_4_get_artifact_miss_returns_found_false(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)
    missing_hex = "0" * 64
    resp = client.get(
        f"/operator/zkba-artifact/{missing_hex}",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] is False
    assert body["commitment_hex"] == missing_hex


# --------------------------------------------------------------------------
# T-ZKBA-EP-5: get-artifact on hit returns found=True + db_row populated
# --------------------------------------------------------------------------
def test_t_zkba_ep_5_get_artifact_hit_returns_row(tmp_path):
    client, store, _cfg = _build_app(tmp_path)
    hexes = _seed_zkba(store, n=3)
    target = hexes[1]  # middle row

    resp = client.get(
        f"/operator/zkba-artifact/{target}",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] is True
    assert body["commitment_hex"] == target
    row = body["db_row"]
    assert row["commitment_hex"] == target
    assert row["zkba_class"] == 2  # (1 % 3) + 1
    assert row["proof_weight"] == 3
    assert row["preimage_json"] == '{"i":1}'
    # Track 1 invariant: anchor_tx_hash NULL across all rows.
    assert row["anchor_tx_hash"] is None
    assert row["manifest_uri"] == "file://manifest_1.json"


# --------------------------------------------------------------------------
# T-ZKBA-EP-6: history DESC ts_ns order + row_count
# --------------------------------------------------------------------------
def test_t_zkba_ep_6_history_desc_order(tmp_path):
    client, store, _cfg = _build_app(tmp_path)
    hexes = _seed_zkba(store, n=4)  # i=0..3, ts_ns monotonically ascending

    resp = client.get(
        "/operator/zkba-history?limit=10",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] == 10
    assert body["row_count"] == 4
    assert len(body["rows"]) == 4
    # DESC by ts_ns — newest first means the row with i=3 leads.
    assert body["rows"][0]["commitment_hex"] == hexes[3]
    assert body["rows"][-1]["commitment_hex"] == hexes[0]


# --------------------------------------------------------------------------
# T-ZKBA-EP-7: history limit bounds — 422 on out-of-range
# --------------------------------------------------------------------------
def test_t_zkba_ep_7_history_limit_bounds(tmp_path):
    client, _store, _cfg = _build_app(tmp_path)

    # limit=0 below ge=1 → 422
    resp_low = client.get(
        "/operator/zkba-history?limit=0",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp_low.status_code == 422

    # limit=501 above le=500 → 422
    resp_high = client.get(
        "/operator/zkba-history?limit=501",
        headers={"x-api-key": "k_zkba_ep"},
    )
    assert resp_high.status_code == 422
