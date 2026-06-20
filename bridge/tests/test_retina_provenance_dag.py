"""Provenance DAG join: POAC_RECORD parent + RETINA_STATE_COMMITMENT child."""

from __future__ import annotations

import hashlib
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
from vapi_bridge.provenance_nodes import poac_record_node_id as _poac_record_node_id


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "retina_dag.db"))


def test_poac_record_and_retina_dag_chain(store):
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

    cfg = replace(Config(), data_provenance_dag_enabled=True)
    agent = CorpusDataCuratorAgent(
        store=store, cfg=cfg, bus=MagicMock(), logger=MagicMock()
    )
    agent._run_provenance_dag()

    parent_id = _poac_record_node_id(rh)
    with store._conn() as conn:
        parent = conn.execute(
            "SELECT node_type FROM data_provenance_dag WHERE node_id = ?",
            (parent_id,),
        ).fetchone()
        child = conn.execute(
            "SELECT node_type, parent_node_id, on_chain_ref "
            "FROM data_provenance_dag WHERE node_type = ?",
            ("RETINA_STATE_COMMITMENT",),
        ).fetchone()
    assert parent is not None
    assert parent[0] == "POAC_RECORD"
    assert child is not None
    assert child[0] == "RETINA_STATE_COMMITMENT"
    assert child[1] == parent_id
    assert child[2] == commitment

    row_id = store.get_retina_event_status("dev1")["entries"][0]["id"]
    leaf_id = "sha256:" + hashlib.sha256(
        f"retina_event_log:{row_id}".encode()
    ).hexdigest()
    chain = store.get_provenance_chain(leaf_id)
    node_types = [n.get("node_type") for n in chain]
    assert "POAC_RECORD" in node_types
    assert "RETINA_STATE_COMMITMENT" in node_types
