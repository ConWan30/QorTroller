"""Phase O1-FRR endpoint test.

Validates GET /operator/fleet-readiness-root + GET /operator/operator-initiative-advancement-log
return correct shape, honor read-key auth, and surface FRR primitive
to operator-facing surface.

Tests:
  T-O1-FRR-EP-1: /operator/fleet-readiness-root returns FRR + summary
                 shape with cfg-frozen agentIds → all 3 agents in
                 agents_in_frr; phase=O0 (empty store) → fleet aligned;
                 frr_hex is 64-char lowercase hex.
  T-O1-FRR-EP-2: read-key auth — wrong key returns 403, correct key 200.
  T-O1-FRR-EP-3: /operator/operator-initiative-advancement-log returns
                 paginated shape (rows[] + row_count + limit).
  T-O1-FRR-EP-4: limit param honored on advancement-log endpoint
                 (capped at 500).
"""
from __future__ import annotations

import dataclasses
import os
import sys
import tempfile
from pathlib import Path

# Mirror Phase O1 C2 test pattern — add bridge/ to sys.path so
# `from vapi_bridge.X` resolves regardless of pytest invocation cwd.
_BRIDGE_DIR = Path(__file__).resolve().parents[1]
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"
GUARDIAN_ID = "0xbd8c7fba08815b7ed343973c9c7300c062303b1acd19e8d9847a953ce5fa38d1"
CURATOR_ID = "0xed6a2df58e5ec50c1f88e127f6982a348f6855202b662b8ad73ffa1c1fda11a8"


def _build_app(tmp_path: Path):
    """Construct a minimal operator_api app for endpoint testing."""
    from fastapi.testclient import TestClient
    from vapi_bridge.config import Config
    from vapi_bridge.store import Store
    from vapi_bridge.operator_api import create_operator_app

    db = str(tmp_path / "test_phase_o1_frr_ep.db")
    cfg = dataclasses.replace(
        Config(),
        db_path=db,
        operator_api_key="k_o1_frr_ep",
        operator_agent_anchor_sentry_id=SENTRY_ID,
        operator_agent_guardian_id=GUARDIAN_ID,
        operator_agent_curator_id=CURATOR_ID,
    )
    store = Store(db)
    app = create_operator_app(cfg, store)
    return TestClient(app), store, cfg


def test_T_O1_FRR_EP_1_fleet_readiness_root_shape(tmp_path):
    """GET /operator/fleet-readiness-root returns FRR + summary shape."""
    client, _, _ = _build_app(tmp_path)
    r = client.get(
        "/operator/fleet-readiness-root",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text}"
    js = r.json()

    # FRR commitment
    assert "frr_hex" in js
    assert len(js["frr_hex"]) == 64  # SHA-256 → 32B → 64 hex chars
    assert all(c in "0123456789abcdef" for c in js["frr_hex"]), (
        f"FRR hex contains non-hex chars: {js['frr_hex']}"
    )
    assert js["frr_error"] is None

    # Domain tag echoed for downstream verifiers
    assert js["domain_tag"] == "VAPI-FRR-v1"

    # Fleet summary shape
    assert isinstance(js["fleet_phase_aligned"], bool)
    assert isinstance(js["fleet_size"], int)
    assert js["fleet_size"] == 3  # Operator Initiative is a 3-agent fleet
    assert js["next_alignment_target"] in ("O0", "O1_SHADOW", "O2_SUGGEST", "O3_ACT")

    # Per-agent rollup includes all 3 canonical names
    canonical_names = {a["agent_id"] for a in js["per_agent"]}
    assert canonical_names == {"anchor_sentry", "guardian", "curator"}, (
        f"per_agent missing one or more canonical names: {canonical_names}"
    )

    # FRR pre-image agents tuple includes all 3 Q9 hex IDs
    frr_id_hexes = {a["agent_id_hex"].lower() for a in js["agents_in_frr"]}
    assert SENTRY_ID[2:].lower() in frr_id_hexes
    assert GUARDIAN_ID[2:].lower() in frr_id_hexes
    assert CURATOR_ID[2:].lower() in frr_id_hexes

    # Empty-store fleet should be at O0 (no activations) → all phase_codes=0x00
    assert all(a["phase_code"] == 0x00 for a in js["agents_in_frr"])
    assert all(a["current_phase"] == "O0" for a in js["per_agent"])


def test_T_O1_FRR_EP_2_read_key_auth(tmp_path):
    """Wrong key returns 403; correct key returns 200."""
    client, _, _ = _build_app(tmp_path)

    # Wrong key
    r = client.get(
        "/operator/fleet-readiness-root",
        headers={"x-api-key": "wrong_key"},
    )
    assert r.status_code == 403, f"expected 403, got {r.status_code}"

    # Correct key
    r = client.get(
        "/operator/fleet-readiness-root",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    assert r.status_code == 200


def test_T_O1_FRR_EP_3_advancement_log_endpoint_shape(tmp_path):
    """GET /operator/operator-initiative-advancement-log returns paginated shape."""
    client, store, _ = _build_app(tmp_path)

    # Empty initially
    r = client.get(
        "/operator/operator-initiative-advancement-log",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    assert r.status_code == 200
    js = r.json()
    assert "rows" in js
    assert "row_count" in js
    assert "limit" in js
    assert "timestamp" in js
    assert js["row_count"] == 0
    assert js["rows"] == []

    # Insert one row, verify it appears
    store.insert_operator_initiative_advancement_log(
        timestamp=1.0,
        fleet_phase_aligned=True,
        fleet_at_o1_count=0,
        fleet_at_o2_ready_count=0,
        fleet_at_o3_ready_count=0,
        next_alignment_target="O3_ACT",
        per_agent_json='[{"agent_id":"anchor_sentry","current_phase":"O2_SUGGEST"}]',
        frr_hex="b" * 64,
        frr_ts_ns=999,
        error=None,
    )
    r = client.get(
        "/operator/operator-initiative-advancement-log",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    js = r.json()
    assert js["row_count"] == 1
    assert js["rows"][0]["frr_hex"] == "b" * 64
    assert js["rows"][0]["next_alignment_target"] == "O3_ACT"


def test_T_O1_FRR_EP_4_advancement_log_limit_param(tmp_path):
    """limit param honored; capped at 500 by Query validator."""
    client, _, _ = _build_app(tmp_path)

    # limit=1 honored
    r = client.get(
        "/operator/operator-initiative-advancement-log?limit=1",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    assert r.status_code == 200
    assert r.json()["limit"] == 1

    # limit=600 rejected (capped at 500)
    r = client.get(
        "/operator/operator-initiative-advancement-log?limit=600",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    assert r.status_code == 422

    # limit=0 rejected (ge=1)
    r = client.get(
        "/operator/operator-initiative-advancement-log?limit=0",
        headers={"x-api-key": "k_o1_frr_ep"},
    )
    assert r.status_code == 422
