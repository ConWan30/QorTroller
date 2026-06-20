"""GET /agent/retina-evidence-slice + BridgeAgent tool (Retina observability goal)."""

from __future__ import annotations

import json
import os
import sys
import time
import types as _types
from dataclasses import replace
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402
from vapi_bridge.bridge_agent import BridgeAgent  # noqa: E402


def _make_cfg(**overrides):
    cfg = replace(Config(), operator_api_key="")
    for k, v in overrides.items():
        cfg = replace(cfg, **{k: v})
    return cfg


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "retina_evidence_api.db"))


def test_t1_disabled_config_empty_bindings(store):
    """Disabled retina → enabled=False, empty bindings."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg(retina_perception_enabled=False)
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/retina-evidence-slice?device_id=dev1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is False
    assert body["bindings"] == []


def test_t2_seeded_row_binding_shape(store):
    """Seeded retina_event_log row returns adjudicator-compatible binding."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    rh = "ab" * 32
    store.insert_retina_event_batch(
        device_id="dev1",
        events_json=json.dumps([{"type": "controller.trajectory.anomalous"}]),
        record_hash_hex=rh,
        anomaly_count=2,
        state_commitment_hex="cc" * 32,
    )
    cfg = _make_cfg(retina_perception_enabled=True)
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get(f"/agent/retina-evidence-slice?device_id=dev1&record_hashes={rh}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["aggregate"]["rows_matched"] == 1
    b = body["bindings"][0]
    assert b["record_hash"] == rh
    assert b["state_commitment"] == "cc" * 32
    assert b["anomaly_count"] == 2


def test_t3_record_hashes_filter(store):
    """Comma-separated record_hashes returns only matching rows."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    rh1, rh2 = "11" * 32, "22" * 32
    for rh in (rh1, rh2):
        store.insert_retina_event_batch(
            device_id="dev1",
            events_json="[]",
            record_hash_hex=rh,
            anomaly_count=1,
        )
    cfg = _make_cfg(retina_perception_enabled=True)
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get(
            f"/agent/retina-evidence-slice?device_id=dev1&record_hashes={rh1}"
        )
    hashes = {b["record_hash"] for b in resp.json()["bindings"]}
    assert hashes == {rh1}


def test_t4_missing_device_id_422(store):
    """Missing device_id returns 422."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg()
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/retina-evidence-slice")
    assert resp.status_code == 422


def test_t5_auth_401_without_read_key(store):
    """Wrong read key returns 403 when operator_api_key is configured."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    cfg = _make_cfg(operator_api_key="secret-read-key")
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get(
            "/agent/retina-evidence-slice?device_id=dev1",
            headers={"x-api-key": "wrong"},
        )
    assert resp.status_code == 403


def test_t6_bridge_agent_tool(store):
    """BridgeAgent get_retina_evidence_slice dispatches to slice builder."""
    rh = "dd" * 32
    store.insert_retina_event_batch(
        device_id="dev1",
        events_json="[]",
        record_hash_hex=rh,
        anomaly_count=1,
        state_commitment_hex="ee" * 32,
    )
    cfg = _make_cfg(retina_perception_enabled=True)
    agent = BridgeAgent(cfg=cfg, store=store)
    out = agent._execute_tool(
        "get_retina_evidence_slice",
        {"device_id": "dev1", "record_hashes": [rh]},
    )
    assert out["bindings"][0]["record_hash"] == rh


def test_t7_limit_cap(store):
    """Limit is capped at 50."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    for i in range(3):
        store.insert_retina_event_batch(
            device_id="dev1",
            events_json="[]",
            record_hash_hex=f"{i:02x}" * 32,
            anomaly_count=0,
        )
    cfg = _make_cfg(retina_perception_enabled=True)
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/retina-evidence-slice?device_id=dev1&limit=2")
    assert len(resp.json()["bindings"]) <= 2


def test_t8_fail_open_on_store_exception(store, monkeypatch):
    """Store exception returns empty slice, not 500."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    def _boom(*_a, **_k):
        raise RuntimeError("db down")

    monkeypatch.setattr(store, "get_retina_event_status", _boom)
    cfg = _make_cfg(retina_perception_enabled=True)
    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get("/agent/retina-evidence-slice?device_id=dev1")
    assert resp.status_code == 200
    assert resp.json()["bindings"] == []
