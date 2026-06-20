"""Smoke tests for scripts/unified_session_monitor.py (read-only DB polling)."""

from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from bridge.vapi_bridge.store import Store
from scripts.unified_session_monitor import (
    connect_readonly,
    fetch_gic_snapshot,
    fetch_l6b_snapshot,
)


@pytest.fixture()
def empty_bridge_db(tmp_path):
  db = tmp_path / "bridge.db"
  Store(str(db))
  return db


@pytest.fixture()
def populated_bridge_db(empty_bridge_db):
  store = Store(str(empty_bridge_db))
  with store._conn() as conn:
      conn.execute(
          "INSERT INTO ruling_validation_log "
          "(ruling_id, device_id, llm_verdict, fallback_verdict, llm_confidence, "
          "fallback_confidence, divergence, grind_chain_hash, gic_ts_ns, grind_session_id, created_at) "
          "VALUES (1, 'dev1', 'FLAG', 'FLAG', 0.5, 0.5, 0, ?, ?, ?, ?)",
          ("aa" * 32, 1_700_000_000_000_000_000, "grind_test", 1.0),
      )
  store.insert_l6b_probe(
      "dev1",
      probe_ts_ms=1_700_000_000_000,
      latency_ms=120.5,
      classification="HUMAN",
      accel_delta_peak=600.0,
      reflex_verdict="REFLEX_OBSERVED",
  )
  return empty_bridge_db


def test_fetch_gic_and_l6b_empty_db(empty_bridge_db):
  conn = connect_readonly(empty_bridge_db)
  try:
      gic = fetch_gic_snapshot(conn, "grind_test")
      l6b = fetch_l6b_snapshot(conn)
      assert gic.chain_length == 0
      assert gic.global_chain_length == 0
      assert l6b.probe_count == 0
      assert l6b.latest_probe is None
  finally:
      conn.close()


def test_fetch_gic_and_l6b_populated_db(populated_bridge_db):
  conn = connect_readonly(populated_bridge_db)
  try:
      gic = fetch_gic_snapshot(conn, "grind_test")
      l6b = fetch_l6b_snapshot(conn)
      assert gic.chain_length == 1
      assert gic.latest_gic_hash == "aa" * 32
      assert l6b.probe_count == 1
      assert l6b.latest_probe["reflex_verdict"] == "REFLEX_OBSERVED"
      assert l6b.reflex_verdict_distribution["REFLEX_OBSERVED"] == 1
  finally:
      conn.close()


def test_readonly_connection_rejects_write(empty_bridge_db):
  conn = connect_readonly(empty_bridge_db)
  try:
      with pytest.raises(sqlite3.OperationalError):
          conn.execute("INSERT INTO l6b_probe_log (device_id, probe_ts_ms, classification) VALUES ('x', 1, 'HUMAN')")
  finally:
      conn.close()
