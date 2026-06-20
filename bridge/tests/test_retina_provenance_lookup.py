"""Provenance lookup by PoAC record_hash (operator convenience)."""

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
from vapi_bridge.corpus_curator_agent import CorpusDataCuratorAgent  # noqa: E402
from vapi_bridge.provenance_nodes import poac_record_node_id  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "retina_prov_lookup.db"))


def test_provenance_lookup_by_record_hash(store):
    """GET data-provenance-chain?record_hash= resolves retina child commitments."""
    import unittest.mock
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    rh = "ab" * 32
    commitment = "cd" * 32
    now = time.time()
    with store._conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO devices (device_id, pubkey_hex, first_seen, last_seen) "
            "VALUES (?, ?, ?, ?)",
            ("dev1", "aa" * 32, now, now),
        )
        conn.execute(
            """
            INSERT INTO records (
                record_hash, device_id, counter, timestamp_ms, inference, action_code,
                confidence, battery_pct, bounty_id, latitude, longitude, status,
                raw_data, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rh, "dev1", 1, int(now * 1000), 0, 0, 200, 80, 0, 0.0, 0.0,
                "pending", b"\x00" * 228, now,
            ),
        )
    store.insert_retina_event_batch(
        device_id="dev1",
        events_json=json.dumps([{"type": "controller.trajectory.anomalous"}]),
        record_hash_hex=rh,
        anomaly_count=1,
        state_commitment_hex=commitment,
    )
    cfg = replace(Config(), data_provenance_dag_enabled=True, operator_api_key="")
    CorpusDataCuratorAgent(
        store=store, cfg=cfg, bus=MagicMock(), logger=MagicMock()
    )._run_provenance_dag()

    with unittest.mock.patch.dict(os.environ, {"OPERATOR_API_KEY": ""}, clear=False):
        app = create_operator_app(cfg, store)
        client = TestClient(app)
        resp = client.get(f"/agent/data-provenance-chain?record_hash={rh}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["resolved_from_record_hash"] == rh
    assert body["leaf_node_id"] == poac_record_node_id(rh)
    assert len(body["retina_commitments"]) >= 1
    assert body["retina_commitments"][0].get("on_chain_ref") == commitment


def test_poac_record_node_id_stable():
    """poac_record_node_id matches curator DAG parent id."""
    rh = "ff" * 32
    assert poac_record_node_id(rh).startswith("sha256:")
