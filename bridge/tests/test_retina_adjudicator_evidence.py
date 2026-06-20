"""Retina evidence slice for SessionAdjudicator (read-only enrichment)."""

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
from vapi_bridge.retina_perception import (  # noqa: E402
    SCHEMA_TAG,
    build_retina_evidence_slice,
)
from vapi_bridge.session_adjudicator import SessionAdjudicator  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "retina_adj_evidence.db"))


def _seed_record(conn, record_hash: str, device_id: str, l4_distance: float | None):
    conn.execute(
        "INSERT OR IGNORE INTO devices (device_id, pubkey_hex, first_seen, last_seen) "
        "VALUES (?, ?, ?, ?)",
        (device_id, "aa" * 32, time.time(), time.time()),
    )
    conn.execute(
        """
        INSERT INTO records (
            record_hash, device_id, counter, timestamp_ms, inference, action_code,
            confidence, battery_pct, bounty_id, latitude, longitude, status,
            raw_data, created_at, pitl_l4_distance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            record_hash,
            device_id,
            1,
            int(time.time() * 1000),
            0,
            0,
            200,
            80,
            0,
            0.0,
            0.0,
            "pending",
            b"\x00" * 228,
            time.time(),
            l4_distance,
        ),
    )


def test_build_retina_evidence_slice_by_record_hashes(store):
    rh = "ab" * 32
    store.insert_retina_event_batch(
        device_id="dev1",
        events_json=json.dumps([{"type": "controller.trajectory.anomalous"}]),
        record_hash_hex=rh,
        anomaly_count=2,
        state_commitment_hex="cc" * 32,
        ts_ns=time.time_ns(),
    )
    slice_ = build_retina_evidence_slice(
        store, "dev1", record_hashes=[rh, "ff" * 32], enabled=True
    )
    assert slice_["schema"] == SCHEMA_TAG
    assert slice_["enabled"] is True
    assert slice_["aggregate"]["rows_matched"] == 1
    assert slice_["aggregate"]["total_trajectory_anomalies"] == 2
    assert slice_["bindings"][0]["record_hash"] == rh
    assert slice_["bindings"][0]["state_commitment"] == "cc" * 32


def test_get_retina_by_record_hash_roundtrip(store):
    rh = "dd" * 32
    store.insert_retina_event_batch(
        device_id="dev2",
        events_json=json.dumps([{"type": "x"}]),
        record_hash_hex=rh,
        anomaly_count=1,
        state_commitment_hex="ee" * 32,
    )
    row = store.get_retina_by_record_hash(rh)
    assert row is not None
    assert row["record_hash_hex"] == rh
    assert store.get_retina_by_record_hash("") is None


def test_session_adjudicator_enrich_retina_evidence(store):
    rh = "11" * 32
    store.insert_retina_event_batch(
        device_id="dev3",
        events_json=json.dumps([{"type": "controller.trajectory.anomalous"}]),
        record_hash_hex=rh,
        anomaly_count=1,
        state_commitment_hex="22" * 32,
    )
    cfg = replace(Config(), retina_perception_enabled=True)
    adj = SessionAdjudicator(cfg=cfg, store=store, bus=MagicMock())
    evidence: dict = {}
    adj._enrich_retina_evidence(evidence, "dev3", [rh])
    assert "retina" in evidence
    assert evidence["retina"]["bindings"][0]["record_hash"] == rh
