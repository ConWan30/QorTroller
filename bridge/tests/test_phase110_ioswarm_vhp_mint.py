"""Phase 110 — IoSwarm VHP Mint Authorization (8 bridge tests).

Tests:
  1. ioswarm_vhp_mint_log insert + roundtrip (12 fields)
  2. consecutive_clean=5, blocks=0 → 5/5 AUTHORIZE → authorized=True
  3. recent_block_count=3 → 5/5 DENY → authorized=False
  4. consecutive_clean=0, blocks=0 → DENY quorum → authorized=False
  5. fail-closed on broken emulator → authorized=False, error present
  6. swarm_fingerprint == SHA-256(json.dumps(node_verdicts, sort_keys=True))
  7. GET /agent/ioswarm-vhp-mint-status → 200, 8 required keys
  8. Tool #78 get_ioswarm_vhp_mint_status returns 7 required fields
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
import types
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store():
    from bridge.vapi_bridge.store import Store
    tmp = tempfile.mkdtemp()
    return Store(os.path.join(tmp, "test.db"))


def _make_cfg(**overrides):
    cfg = types.SimpleNamespace(
        ioswarm_vhp_mint_enabled=False,
        ioswarm_vhp_mint_quorum=0.80,
        # Phase 109C / 109B / 109A guards (prevent MagicMock truthy routing)
        ioswarm_adjudication_enabled=False,
        ioswarm_renewal_enabled=False,
        ioswarm_enabled=False,
        # Phase 99C / 108 guard
        agent_dry_run_mode=True,
        separation_ratio_current=0.362,
        touchpad_recapture_complete=False,
    )
    for k, v in overrides.items():
        setattr(cfg, k, v)
    return cfg


def _make_emulator():
    from bridge.vapi_bridge.ioswarm_vhp_mint_emulator import IoSwarmVHPMintEmulator
    return IoSwarmVHPMintEmulator(n_nodes=5, seed=110)


# ---------------------------------------------------------------------------
# Test 1: store insert + roundtrip
# ---------------------------------------------------------------------------

def test_1_vhp_mint_log_insert_roundtrip():
    store = _make_store()
    fingerprint = "abc123deadbeef" * 4  # 56 chars, plausible
    row_id = store.insert_ioswarm_vhp_mint(
        device_id="dev_roundtrip",
        authorized=True,
        quorum_verdict="AUTHORIZE",
        agreement_ratio=0.8,
        node_count=5,
        consecutive_clean=5,
        recent_block_count=0,
        node_verdicts_json='[{"verdict":"AUTHORIZE"}]',
        swarm_fingerprint=fingerprint,
    )
    assert isinstance(row_id, int) and row_id > 0

    logs = store.get_ioswarm_vhp_mint_log(device_id="dev_roundtrip", limit=5)
    assert len(logs) == 1
    r = logs[0]

    # 12 required fields
    for field in (
        "id", "device_id", "authorized", "quorum_verdict",
        "agreement_ratio", "node_count", "consecutive_clean",
        "recent_block_count", "node_verdicts",
        "swarm_fingerprint", "error_msg", "created_at",
    ):
        assert field in r, f"Missing field: {field}"

    assert r["device_id"] == "dev_roundtrip"
    assert bool(r["authorized"]) is True
    assert r["quorum_verdict"] == "AUTHORIZE"
    assert r["swarm_fingerprint"] == fingerprint


# ---------------------------------------------------------------------------
# Test 2: clean streak → all AUTHORIZE → authorized=True
# ---------------------------------------------------------------------------

def test_2_clean_streak_authorizes():
    from bridge.vapi_bridge.ioswarm_vhp_mint_coordinator import IoSwarmVHPMintCoordinator
    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=True, ioswarm_vhp_mint_quorum=0.80)
    coord = IoSwarmVHPMintCoordinator(cfg=cfg, store=store, mint_emulator=_make_emulator())

    result = coord.authorize("dev_clean", consecutive_clean=5, recent_block_count=0)

    assert result["authorized"] is True, f"Expected authorized=True, got {result}"
    assert result["agreement_ratio"] == 1.0
    assert result["quorum_verdict"] == "AUTHORIZE"
    assert result["swarm_fingerprint"] is not None
    assert len(result["node_verdicts"]) == 5
    assert all(v["verdict"] == "AUTHORIZE" for v in result["node_verdicts"])


# ---------------------------------------------------------------------------
# Test 3: recent blocks → all DENY → authorized=False
# ---------------------------------------------------------------------------

def test_3_recent_blocks_denies():
    from bridge.vapi_bridge.ioswarm_vhp_mint_coordinator import IoSwarmVHPMintCoordinator
    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=True, ioswarm_vhp_mint_quorum=0.80)
    coord = IoSwarmVHPMintCoordinator(cfg=cfg, store=store, mint_emulator=_make_emulator())

    result = coord.authorize("dev_blocks", consecutive_clean=5, recent_block_count=3)

    assert result["authorized"] is False, f"Expected authorized=False, got {result}"
    assert result["quorum_verdict"] == "DENY"
    assert all(v["verdict"] == "DENY" for v in result["node_verdicts"])


# ---------------------------------------------------------------------------
# Test 4: low streak, no blocks → DENY quorum
# ---------------------------------------------------------------------------

def test_4_low_clean_denies():
    from bridge.vapi_bridge.ioswarm_vhp_mint_coordinator import IoSwarmVHPMintCoordinator
    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=True, ioswarm_vhp_mint_quorum=0.80)
    coord = IoSwarmVHPMintCoordinator(cfg=cfg, store=store, mint_emulator=_make_emulator())

    result = coord.authorize("dev_low", consecutive_clean=0, recent_block_count=0)

    # With consecutive_clean=0 and blocks=0, most nodes vote DENY
    assert result["authorized"] is False, f"Expected authorized=False (low streak), got {result}"


# ---------------------------------------------------------------------------
# Test 5: fail-closed on broken emulator
# ---------------------------------------------------------------------------

def test_5_fail_closed_on_error():
    from bridge.vapi_bridge.ioswarm_vhp_mint_coordinator import IoSwarmVHPMintCoordinator
    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=True, ioswarm_vhp_mint_quorum=0.80)

    class BrokenEmulator:
        def evaluate_vhp_mint(self, *a, **k):
            raise RuntimeError("emulator failure")

    coord = IoSwarmVHPMintCoordinator(cfg=cfg, store=store, mint_emulator=BrokenEmulator())
    result = coord.authorize("dev_fail", consecutive_clean=5, recent_block_count=0)

    assert result["authorized"] is False, "Fail-CLOSED: exception must → authorized=False"
    assert "error" in result
    assert "emulator failure" in result["error"]
    assert result["quorum_verdict"] == "DENY"
    assert result["agreement_ratio"] == 0.0


# ---------------------------------------------------------------------------
# Test 6: swarm_fingerprint == SHA-256(json.dumps(node_verdicts, sort_keys=True))
# ---------------------------------------------------------------------------

def test_6_swarm_fingerprint_is_sha256():
    from bridge.vapi_bridge.ioswarm_vhp_mint_coordinator import IoSwarmVHPMintCoordinator
    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=True, ioswarm_vhp_mint_quorum=0.80)
    coord = IoSwarmVHPMintCoordinator(cfg=cfg, store=store, mint_emulator=_make_emulator())

    result = coord.authorize("dev_fp", consecutive_clean=5, recent_block_count=0)

    assert result["swarm_fingerprint"] is not None
    expected = hashlib.sha256(
        json.dumps(result["node_verdicts"], sort_keys=True).encode()
    ).hexdigest()
    assert result["swarm_fingerprint"] == expected, (
        f"Fingerprint mismatch: got {result['swarm_fingerprint']!r}, expected {expected!r}"
    )


# ---------------------------------------------------------------------------
# Test 7: GET /agent/ioswarm-vhp-mint-status → 200, 8 required keys
# ---------------------------------------------------------------------------

def test_7_ioswarm_vhp_mint_endpoint_200():
    from fastapi.testclient import TestClient
    from bridge.vapi_bridge.operator_api import create_operator_app

    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=False)
    cfg.operator_api_key = "test-key-110"

    bus = MagicMock()
    bus.subscribe = MagicMock(return_value=None)
    bus.publish_sync = MagicMock(return_value=None)

    chain = MagicMock()
    app   = create_operator_app(cfg=cfg, store=store, chain=chain, bus=bus)

    with TestClient(app) as client:
        resp = client.get("/agent/ioswarm-vhp-mint-status?api_key=test-key-110")
    assert resp.status_code == 200, resp.text

    data = resp.json()
    required_keys = {
        "ioswarm_vhp_mint_enabled",
        "mint_quorum",
        "authorized_count",
        "denied_count",
        "recent_vhp_mint_logs",
        "task_spec_registered",
        "swarm_fingerprint_count",
        "timestamp",
    }
    missing = required_keys - set(data.keys())
    assert not missing, f"Missing keys: {missing}"
    assert data["task_spec_registered"] is True
    assert data["ioswarm_vhp_mint_enabled"] is False


# ---------------------------------------------------------------------------
# Test 8: Tool #78 returns all 7 required fields
# ---------------------------------------------------------------------------

def test_8_tool_78_required_fields():
    import bridge.vapi_bridge.bridge_agent as _ba_mod
    from bridge.vapi_bridge.bridge_agent import BridgeAgent

    store = _make_store()
    cfg   = _make_cfg(ioswarm_vhp_mint_enabled=False)

    # Verify Tool #78 definition exists in module-level _TOOLS list
    tool_names = [t["name"] for t in _ba_mod._TOOLS]
    assert "get_ioswarm_vhp_mint_status" in tool_names, (
        f"Tool #78 definition not found in _TOOLS. Tools: {tool_names[-5:]}"
    )

    # Invoke via _execute_tool
    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg   = cfg
    agent._chain = MagicMock()
    agent._llm   = None

    response = agent._execute_tool("get_ioswarm_vhp_mint_status", {})
    required = {
        "ioswarm_vhp_mint_enabled",
        "mint_quorum",
        "authorized_count",
        "denied_count",
        "task_spec_registered",
        "swarm_fingerprint_count",
        "timestamp",
    }
    missing = required - set(response.keys())
    assert not missing, f"Tool #78 missing fields: {missing}"
