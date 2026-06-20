"""FSCA cross-oracle rules: Retina trajectory vs L4 Mahalanobis distance."""

from __future__ import annotations

import os
import sys
import time
import types as _types
from dataclasses import replace

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)

from vapi_bridge.store import Store  # noqa: E402
from vapi_bridge.config import Config  # noqa: E402
from vapi_bridge.fleet_signal_coherence_agent import CONTRADICTION_RULES  # noqa: E402


@pytest.fixture()
def store(tmp_path):
    return Store(str(tmp_path / "retina_fsca.db"))


def _exec_rule(store, rule_name: str, cfg: Config) -> list[dict]:
    rule = CONTRADICTION_RULES[rule_name]
    if "guard" in rule and not rule["guard"](cfg):
        return []
    params = rule["params"](cfg)
    with store._conn() as conn:
        rows = conn.execute(rule["query"], params).fetchall()
    return [dict(r) for r in rows]


def _seed_record(conn, record_hash: str, device_id: str, l4_distance: float | None):
    now = time.time()
    conn.execute(
        "INSERT OR IGNORE INTO devices (device_id, pubkey_hex, first_seen, last_seen) "
        "VALUES (?, ?, ?, ?)",
        (device_id, "aa" * 32, now, now),
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
            int(now * 1000),
            0,
            0,
            200,
            80,
            0,
            0.0,
            0.0,
            "pending",
            b"\x00" * 228,
            now,
            l4_distance,
        ),
    )


def test_retina_trajectory_without_l4_anomaly_fires(store):
    cfg = replace(Config(), retina_perception_enabled=True)
    rh = "ab" * 32
    with store._conn() as conn:
        _seed_record(conn, rh, "dev1", l4_distance=2.0)
        conn.execute(
            """
            INSERT INTO retina_event_log (
                device_id, events_json, world_state_json, record_hash_hex,
                state_commitment_hex, anomaly_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("dev1", "[]", "{}", rh, "cc" * 32, 2, time.time()),
        )
    rows = _exec_rule(store, "RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY", cfg)
    assert len(rows) == 1
    assert rows[0]["record_hash_hex"] == rh


def test_l4_anomaly_without_retina_signal_fires(store):
    cfg = replace(Config(), retina_perception_enabled=True)
    rh = "dd" * 32
    with store._conn() as conn:
        _seed_record(conn, rh, "dev2", l4_distance=cfg.l4_anomaly_threshold + 1.0)
    rows = _exec_rule(store, "L4_ANOMALY_WITHOUT_RETINA_SIGNAL", cfg)
    assert len(rows) == 1
    assert rows[0]["record_hash"] == rh


def test_retina_rules_guard_dormant_when_disabled(store):
    cfg = replace(Config(), retina_perception_enabled=False)
    rh = "ef" * 32
    with store._conn() as conn:
        _seed_record(conn, rh, "dev3", l4_distance=2.0)
        conn.execute(
            """
            INSERT INTO retina_event_log (
                device_id, events_json, world_state_json, record_hash_hex,
                state_commitment_hex, anomaly_count, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("dev3", "[]", "{}", rh, "11" * 32, 1, time.time()),
        )
    assert _exec_rule(store, "RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY", cfg) == []
    assert _exec_rule(store, "L4_ANOMALY_WITHOUT_RETINA_SIGNAL", cfg) == []


def test_retina_fsca_rule_count_invariant():
    assert "RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY" in CONTRADICTION_RULES
    assert "L4_ANOMALY_WITHOUT_RETINA_SIGNAL" in CONTRADICTION_RULES
    assert len(CONTRADICTION_RULES) == 30
    for name in (
        "RETINA_TRAJECTORY_WITHOUT_L4_ANOMALY",
        "L4_ANOMALY_WITHOUT_RETINA_SIGNAL",
    ):
        rule = CONTRADICTION_RULES[name]
        assert rule["severity"] == "MEDIUM"
        assert callable(rule["params"])
        assert rule.get("guard") is not None
