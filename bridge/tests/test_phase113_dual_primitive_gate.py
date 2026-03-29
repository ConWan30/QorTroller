"""
Phase 113 — VAPIDualPrimitiveGate bridge tests.
dual_primitive_gate_enabled=False by default (infrastructure-first).
Tests: store roundtrip, endpoint 8 keys, gate disabled guard,
       schema_version_113, chain method mock, history query.
"""

import hashlib
import os
import sys
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmp_path):
    from vapi_bridge.store import Store
    db = str(tmp_path / "test_p113.db")
    return Store(db)


def _make_cfg(**kwargs):
    cfg = MagicMock()
    cfg.dual_primitive_gate_enabled = False
    cfg.dual_primitive_gate_address = ""
    cfg.adjudication_registry_address = ""
    cfg.operator_api_key = "testkey113"
    cfg.rate_limit_per_minute = 1000
    # Existing Phase guards
    cfg.poad_registry_enabled = False
    cfg.poad_on_chain_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    cfg.ioswarm_vhp_mint_enabled = False
    for k, v in kwargs.items():
        setattr(cfg, k, v)
    return cfg


# ---------------------------------------------------------------------------
# Test 1: insert_dual_eligibility_check roundtrip
# ---------------------------------------------------------------------------

def test_insert_dual_eligibility_check_roundtrip(tmp_path):
    store = _make_store(tmp_path)
    device_id = "test_device_p113"
    poad_hash = hashlib.sha256(b"test_poad_bundle").hexdigest()

    row_id = store.insert_dual_eligibility_check(
        device_id=device_id,
        poad_hash=poad_hash,
        eligible=True,
        poac_valid=True,
        poad_valid=True,
    )
    assert row_id is not None

    history = store.get_dual_eligibility_history(device_id=device_id, limit=10)
    assert len(history) == 1
    assert history[0]["eligible"] is True
    assert history[0]["poac_valid"] is True
    assert history[0]["poad_valid"] is True
    assert history[0]["device_id"] == device_id
    assert history[0]["poad_hash"] == poad_hash


# ---------------------------------------------------------------------------
# Test 2: get_dual_eligibility_history returns newest first, unfiltered
# ---------------------------------------------------------------------------

def test_get_dual_eligibility_history_newest_first(tmp_path):
    store = _make_store(tmp_path)
    poad_a = hashlib.sha256(b"poad_a").hexdigest()
    poad_b = hashlib.sha256(b"poad_b").hexdigest()
    poad_c = hashlib.sha256(b"poad_c").hexdigest()

    store.insert_dual_eligibility_check("dev_1", poad_a, False, False, False)
    time.sleep(0.01)
    store.insert_dual_eligibility_check("dev_1", poad_b, False, True, False)
    time.sleep(0.01)
    store.insert_dual_eligibility_check("dev_2", poad_c, True, True, True)

    # Unfiltered — 3 rows, newest first
    all_checks = store.get_dual_eligibility_history(limit=10)
    assert len(all_checks) == 3
    assert all_checks[0]["poad_hash"] == poad_c  # newest

    # Filtered by device_id
    dev1_checks = store.get_dual_eligibility_history(device_id="dev_1", limit=10)
    assert len(dev1_checks) == 2


# ---------------------------------------------------------------------------
# Test 3: is_dual_eligible chain method — mock returns correct dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_dual_eligible_chain_method_mock():
    from vapi_bridge.chain import ChainClient

    cfg = _make_cfg(
        dual_primitive_gate_address="0x1234567890123456789012345678901234567890"
    )
    chain = ChainClient.__new__(ChainClient)
    chain._cfg = cfg

    mock_w3 = MagicMock()
    chain._w3 = mock_w3

    # Mock the contract call chain
    mock_contract = MagicMock()
    mock_w3.eth.contract.return_value = mock_contract
    mock_w3.to_checksum_address.return_value = "0x1234567890123456789012345678901234567890"
    mock_fn = AsyncMock(return_value=(True, True, False))
    mock_contract.functions.isDualEligible.return_value.call = mock_fn

    device_id_hash_hex = hashlib.sha256(b"device_001").hexdigest()
    poad_hash_hex = hashlib.sha256(b"poad_bundle").hexdigest()

    result = await chain.is_dual_eligible(device_id_hash_hex, poad_hash_hex)

    assert result["eligible"] is True
    assert result["poac_valid"] is True
    assert result["poad_valid"] is False


# ---------------------------------------------------------------------------
# Test 4: is_dual_eligible raises RuntimeError when address not configured
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_is_dual_eligible_raises_when_no_address():
    from vapi_bridge.chain import ChainClient

    cfg = _make_cfg(dual_primitive_gate_address="")
    chain = ChainClient.__new__(ChainClient)
    chain._cfg = cfg

    with pytest.raises(RuntimeError, match="dual_primitive_gate_address not configured"):
        await chain.is_dual_eligible("a" * 64, "b" * 64)


# ---------------------------------------------------------------------------
# Test 5: GET /agent/dual-primitive-status returns 8 keys
# ---------------------------------------------------------------------------

def test_dual_primitive_status_endpoint_8_keys(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg()
    store = _make_store(tmp_path)
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.get("/agent/dual-primitive-status?api_key=testkey113")
    assert resp.status_code == 200
    data = resp.json()
    required_keys = {
        "dual_primitive_gate_enabled",
        "dual_primitive_gate_address",
        "protocol_lens_address",
        "adjudication_registry_address",
        "checks_total",
        "checks_eligible",
        "last_check_device_id",
        "timestamp",
    }
    assert required_keys.issubset(set(data.keys()))


# ---------------------------------------------------------------------------
# Test 6: POST /agent/check-dual-eligibility returns disabled error when gate off
# ---------------------------------------------------------------------------

def test_check_dual_eligibility_returns_disabled_when_gate_off(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg(dual_primitive_gate_enabled=False)
    store = _make_store(tmp_path)
    app = create_operator_app(cfg, store, chain=None)
    client = TestClient(app)

    resp = client.post(
        "/agent/check-dual-eligibility?api_key=testkey113",
        json={"device_id": "dev_001", "poad_hash": "a" * 64},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is False
    assert "disabled" in data.get("error", "").lower()


# ---------------------------------------------------------------------------
# Test 7: POST /agent/check-dual-eligibility stores result when chain succeeds
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_check_dual_eligibility_stores_result(tmp_path):
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg(
        dual_primitive_gate_enabled=True,
        dual_primitive_gate_address="0x1234567890123456789012345678901234567890",
    )
    store = _make_store(tmp_path)

    mock_chain = AsyncMock()
    mock_chain.is_dual_eligible = AsyncMock(
        return_value={"eligible": True, "poac_valid": True, "poad_valid": True}
    )

    app = create_operator_app(cfg, store, chain=mock_chain)
    client = TestClient(app)

    poad_hash = hashlib.sha256(b"test_bundle").hexdigest()
    resp = client.post(
        "/agent/check-dual-eligibility?api_key=testkey113",
        json={"device_id": "dev_p113", "poad_hash": poad_hash},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["eligible"] is True
    assert data["poac_valid"] is True
    assert data["poad_valid"] is True

    # Verify stored
    history = store.get_dual_eligibility_history(device_id="dev_p113", limit=5)
    assert len(history) == 1
    assert history[0]["eligible"] is True


# ---------------------------------------------------------------------------
# Test 8: schema_version_113 present after store init
# ---------------------------------------------------------------------------

def test_schema_version_113(tmp_path):
    store = _make_store(tmp_path)
    with store._conn() as conn:
        row = conn.execute(
            "SELECT phase, migration_name FROM schema_versions WHERE phase = 113"
        ).fetchone()
    assert row is not None
    assert row[0] == 113
    assert row[1] == "dual_primitive_gate"
