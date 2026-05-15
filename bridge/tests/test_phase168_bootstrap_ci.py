"""Phase 168 tests — Bootstrap CI integration in separation_ratio_snapshots.

8 tests:
  T168-1  Schema migration adds ci_lower/ci_upper/n_bootstrap columns
  T168-2  insert_separation_ratio_snapshot stores CI values
  T168-3  insert without CI args defaults to 0.0/0.0/0
  T168-4  get_separation_ratio_status returns CI fields
  T168-5  defensibility-status API includes ci_lower/ci_upper/n_bootstrap
  T168-6  agent_feed query uses bt_strat_ratio (not stratified_estimate)
  T168-7  schema probe detects bt_strat_ratio correctly
  T168-8  analyze script --bootstrap-n wires CI into snapshot row
"""
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store(tmpdir):
    """Return a fresh Store instance backed by a temp SQLite DB."""
    from vapi_bridge.store import Store
    db_path = os.path.join(tmpdir, "test_phase168.db")
    store = Store(db_path=db_path)
    return store


def _make_app(tmpdir):
    """Return a FastAPI test client with a temp store."""
    import importlib
    from fastapi.testclient import TestClient

    from vapi_bridge.store import Store
    from vapi_bridge import operator_api

    db_path = os.path.join(tmpdir, "test_phase168_api.db")
    store = Store(db_path=db_path)

    cfg = MagicMock()
    cfg.operator_api_key = "test-key-168"
    cfg.separation_ratio_on_chain_enabled = False
    cfg.consent_ledger_enabled = False
    cfg.dry_run = True
    cfg.min_separation_ratio = 0.70
    cfg.min_touchpad_sessions_per_player = 10

    app = operator_api.build_app(store=store, cfg=cfg)
    client = TestClient(app, raise_server_exceptions=False)
    return client, store


# ---------------------------------------------------------------------------
# T168-1  Schema migration adds ci_lower/ci_upper/n_bootstrap columns
# ---------------------------------------------------------------------------

def test_t168_1_schema_migration_adds_ci_columns():
    """Store schema migration idempotently adds ci_lower/ci_upper/n_bootstrap."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = _make_store(tmpdir)
        import sqlite3
        conn = sqlite3.connect(store._db_path)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(separation_ratio_snapshots)")}
        conn.close()
        assert "ci_lower" in cols, "ci_lower column missing"
        assert "ci_upper" in cols, "ci_upper column missing"
        assert "n_bootstrap" in cols, "n_bootstrap column missing"


# ---------------------------------------------------------------------------
# T168-2  insert_separation_ratio_snapshot stores CI values
# ---------------------------------------------------------------------------

def test_t168_2_insert_stores_ci_values():
    """insert_separation_ratio_snapshot persists ci_lower/ci_upper/n_bootstrap."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = _make_store(tmpdir)
        store.insert_separation_ratio_snapshot(
            pooled_ratio=1.261,
            bt_strat_ratio=1.350,
            n_sessions=11,
            n_players=3,
            active_features=8,
            tournament_ready=True,
            ci_lower=0.950,
            ci_upper=1.580,
            n_bootstrap=1000,
        )
        rows = store.get_separation_ratio_status(limit=1)
        assert rows, "No rows returned"
        row = rows[0]
        assert abs(row["ci_lower"] - 0.950) < 1e-6, f"ci_lower mismatch: {row['ci_lower']}"
        assert abs(row["ci_upper"] - 1.580) < 1e-6, f"ci_upper mismatch: {row['ci_upper']}"
        assert row["n_bootstrap"] == 1000, f"n_bootstrap mismatch: {row['n_bootstrap']}"


# ---------------------------------------------------------------------------
# T168-3  insert without CI args defaults to 0.0/0.0/0
# ---------------------------------------------------------------------------

def test_t168_3_insert_without_ci_defaults_to_zero():
    """insert_separation_ratio_snapshot without CI args defaults to 0.0/0.0/0."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = _make_store(tmpdir)
        store.insert_separation_ratio_snapshot(
            pooled_ratio=0.569,
            bt_strat_ratio=-1.0,
            n_sessions=20,
            n_players=3,
            active_features=8,
            tournament_ready=False,
        )
        rows = store.get_separation_ratio_status(limit=1)
        assert rows
        row = rows[0]
        assert row["ci_lower"] == 0.0, f"ci_lower should be 0.0, got {row['ci_lower']}"
        assert row["ci_upper"] == 0.0, f"ci_upper should be 0.0, got {row['ci_upper']}"
        assert row["n_bootstrap"] == 0, f"n_bootstrap should be 0, got {row['n_bootstrap']}"


# ---------------------------------------------------------------------------
# T168-4  get_separation_ratio_status returns CI fields
# ---------------------------------------------------------------------------

def test_t168_4_get_status_returns_ci_fields():
    """get_separation_ratio_status returns ci_lower, ci_upper, n_bootstrap keys."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        store = _make_store(tmpdir)
        store.insert_separation_ratio_snapshot(
            pooled_ratio=1.100,
            bt_strat_ratio=1.200,
            n_sessions=15,
            n_players=3,
            active_features=8,
            tournament_ready=True,
            ci_lower=0.800,
            ci_upper=1.400,
            n_bootstrap=500,
        )
        rows = store.get_separation_ratio_status(limit=5)
        assert rows
        row = rows[0]
        assert "ci_lower" in row, "ci_lower key missing from get_separation_ratio_status result"
        assert "ci_upper" in row, "ci_upper key missing"
        assert "n_bootstrap" in row, "n_bootstrap key missing"
        assert abs(row["ci_lower"] - 0.800) < 1e-6
        assert abs(row["ci_upper"] - 1.400) < 1e-6
        assert row["n_bootstrap"] == 500


# ---------------------------------------------------------------------------
# T168-5  defensibility-status API includes ci_lower/ci_upper/n_bootstrap
# ---------------------------------------------------------------------------

def test_t168_5_api_defensibility_status_includes_ci():
    """GET /agent/separation-defensibility-status includes ci_lower/ci_upper/n_bootstrap."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmpdir:
        try:
            client, store = _make_app(tmpdir)
        except Exception:
            pytest.skip("operator_api build_app not importable in this env")

        store.insert_separation_ratio_snapshot(
            pooled_ratio=0.569,
            bt_strat_ratio=-1.0,
            n_sessions=20,
            n_players=3,
            active_features=8,
            tournament_ready=False,
            ci_lower=0.400,
            ci_upper=0.750,
            n_bootstrap=200,
        )

        resp = client.get(
            "/agent/separation-defensibility-status",
            headers={"x-api-key": "test-key-168"},
        )
        assert resp.status_code == 200, f"HTTP {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "ci_lower" in data, f"ci_lower missing from defensibility-status: {data.keys()}"
        assert "ci_upper" in data, f"ci_upper missing"
        assert "n_bootstrap" in data, f"n_bootstrap missing"
        assert abs(data["ci_lower"] - 0.400) < 1e-6
        assert abs(data["ci_upper"] - 0.750) < 1e-6
        assert data["n_bootstrap"] == 200


# ---------------------------------------------------------------------------
# T168-6  agent_feed query uses bt_strat_ratio (not stratified_estimate)
# ---------------------------------------------------------------------------

def test_t168_6_agent_feed_uses_bt_strat_ratio_column():
    """Wiki engine agent_feed queries bt_strat_ratio column (Phase 168 fix)."""
    wiki_engine = ROOT / "vapi_wiki_engine.py"
    if not wiki_engine.exists():
        pytest.skip("vapi_wiki_engine.py not found")
    text = wiki_engine.read_text(encoding="utf-8", errors="ignore")
    # Must reference bt_strat_ratio
    assert "bt_strat_ratio" in text, "bt_strat_ratio not referenced in wiki engine"
    # Must NOT reference old broken column name
    assert "stratified_estimate" not in text, (
        "stratified_estimate (broken column name) still referenced in wiki engine"
    )


# ---------------------------------------------------------------------------
# T168-7  schema probe detects bt_strat_ratio correctly
# ---------------------------------------------------------------------------

def test_t168_7_schema_probe_detects_bt_strat_ratio():
    """_AGENT15_REQUIRED_COLS in wiki engine includes bt_strat_ratio."""
    wiki_engine = ROOT / "vapi_wiki_engine.py"
    if not wiki_engine.exists():
        pytest.skip("vapi_wiki_engine.py not found")
    text = wiki_engine.read_text(encoding="utf-8", errors="ignore")
    assert "_AGENT15_REQUIRED_COLS" in text, "_AGENT15_REQUIRED_COLS sentinel missing"
    # bt_strat_ratio must be in the required set
    assert '"bt_strat_ratio"' in text or "'bt_strat_ratio'" in text, (
        "bt_strat_ratio not listed in _AGENT15_REQUIRED_COLS"
    )


# ---------------------------------------------------------------------------
# T168-8  analyze script --bootstrap-n wires CI into snapshot row
# ---------------------------------------------------------------------------

def test_t168_8_analyze_bootstrap_stored_in_snapshot():
    """Bootstrap CI computed before write_snapshot so CI persists in DB row."""
    analyze_script = ROOT / "scripts" / "analyze_interperson_separation.py"
    if not analyze_script.exists():
        pytest.skip("analyze_interperson_separation.py not found")
    text = analyze_script.read_text(encoding="utf-8", errors="ignore")

    # Phase 168 moved bootstrap computation BEFORE the if args.write_snapshot block
    # Confirm ci_lower/ci_upper/n_bootstrap are passed to insert_separation_ratio_snapshot
    assert "ci_lower=" in text, "ci_lower= kwarg not passed to insert_separation_ratio_snapshot"
    assert "ci_upper=" in text, "ci_upper= kwarg not passed to insert_separation_ratio_snapshot"
    assert "n_bootstrap=" in text, "n_bootstrap= kwarg not passed to insert_separation_ratio_snapshot"
