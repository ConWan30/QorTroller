"""Phase O5-MLGA Stage 4 — close_session VPM hook tests.

T-MLGA-HOOK-1   close_session invokes compiler + inserts row in vpm_artifact_log
T-MLGA-HOOK-2   Compiler failure does NOT prevent dataproof persist (fail-open)
T-MLGA-HOOK-3   vpm_artifact_log row has wrapper_schema='vapi-mlga-session-artifact-v1'
T-MLGA-HOOK-4   Row's zkba_manifest_hash_hex matches MLGA dataproof hex byte-identically
"""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_tracker(db_path):
    from vapi_bridge.store import Store
    from vapi_bridge.mlga_session_tracker import MLGASessionTracker
    cfg = MagicMock()
    cfg.mlga_session_tracker_enabled = True
    cfg.mlga_session_tracker_interval_s = 30
    cfg.mlga_session_max_duration_s = 3600
    store = Store(db_path=db_path)
    tracker = MLGASessionTracker(store=store, cfg=cfg)
    return tracker, store


def _query_vpm_log(db_path):
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    rows = con.execute("SELECT * FROM vpm_artifact_log").fetchall()
    con.close()
    return [dict(r) for r in rows]


# ----- T-1 -----

def test_t_mlga_hook_1_close_inserts_vpm_artifact_row():
    """Open + close session → vpm_artifact_log gets a row + mlga_session_log
    also gets the dataproof row. Both surfaces persist together."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db)

        tracker.open_session("test_open", ts_ns=1_000_000_000_000_000_000)
        # Simulate accumulated state during the session
        tracker._open.n_poac_records = 1000
        tracker._open.n_trigger_pulls_r2 = 50
        tracker._open.n_trigger_pulls_l2 = 20
        tracker._open.gic_advances_in_session = 5
        tracker._open.apop_state_counts = {"ACTIVE_MATCH_PLAY": 800}
        tracker._open.bt_observability = 1

        closed = tracker.close_session(
            "test_close", ts_ns=1_000_001_800_000_000_000,  # 30 min later
        )
        assert closed is True

        # Both surfaces persisted
        mlga_status = store.get_mlga_session_status()
        assert mlga_status["total_sessions"] == 1

        vpm_rows = _query_vpm_log(db)
        assert len(vpm_rows) == 1, (
            f"expected exactly 1 vpm row; got {len(vpm_rows)}"
        )


# ----- T-2 -----

def test_t_mlga_hook_2_compiler_failure_does_not_break_dataproof_persist():
    """Fail-open contract: if the VPM compiler raises, the dataproof row
    in mlga_session_log MUST still exist. The dataproof is load-bearing;
    the VPM is the projection. Critical for grind continuity."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db)

        tracker.open_session("test_open", ts_ns=1_000_000_000_000_000_000)
        tracker._open.n_poac_records = 100
        tracker._open.gic_advances_in_session = 1

        # Monkey-patch build_mlga_session_artifact to RAISE — simulates
        # compiler crash mid-render.
        import mlga_compile_session_artifact as mod
        original = mod.build_mlga_session_artifact
        def _fail(*a, **kw):
            raise RuntimeError("simulated compiler failure")
        try:
            mod.build_mlga_session_artifact = _fail
            closed = tracker.close_session("test_close",
                                            ts_ns=1_000_000_001_000_000_000)
        finally:
            mod.build_mlga_session_artifact = original

        assert closed is True
        # Dataproof persisted despite compiler failure
        mlga_status = store.get_mlga_session_status()
        assert mlga_status["total_sessions"] == 1
        # But vpm_artifact_log has NO row (compiler crashed before insert)
        vpm_rows = _query_vpm_log(db)
        assert len(vpm_rows) == 0


# ----- T-3 -----

def test_t_mlga_hook_3_wrapper_schema_canonical():
    """vpm_artifact_log row carries the FROZEN wrapper_schema literal."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db)

        tracker.open_session("test_open", ts_ns=2_000_000_000_000_000_000)
        tracker._open.n_poac_records = 500
        tracker._open.gic_advances_in_session = 3
        tracker.close_session("test_close", ts_ns=2_000_001_000_000_000_000)

        vpm_rows = _query_vpm_log(db)
        assert len(vpm_rows) == 1
        assert vpm_rows[0]["wrapper_schema"] == "vapi-mlga-session-artifact-v1"
        assert vpm_rows[0]["vpm_id"] == "MLGA-SESSION-v1"
        assert vpm_rows[0]["zkba_class"] == 2  # ZKBAClass.GIC
        assert vpm_rows[0]["capture_mode"] == "live"


# ----- T-4 -----

def test_t_mlga_hook_4_zkba_manifest_hash_matches_dataproof_byte_identical():
    """Critical cryptographic invariant: the vpm_artifact_log row's
    zkba_manifest_hash_hex column MUST equal the mlga_session_log row's
    dataproof_hex byte-identically. This is the binding between the
    VPM projection and the MLGA dataproof commitment."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db)

        tracker.open_session("test_open", ts_ns=3_000_000_000_000_000_000)
        tracker._open.n_poac_records = 200
        tracker._open.n_trigger_pulls_r2 = 10
        tracker._open.gic_advances_in_session = 2
        tracker.close_session("test_close", ts_ns=3_000_001_000_000_000_000)

        # Read both rows
        con = sqlite3.connect(db)
        con.row_factory = sqlite3.Row
        mlga_row = con.execute(
            "SELECT dataproof_hex FROM mlga_session_log LIMIT 1"
        ).fetchone()
        vpm_row = con.execute(
            "SELECT zkba_manifest_hash_hex FROM vpm_artifact_log LIMIT 1"
        ).fetchone()
        con.close()

        assert mlga_row is not None
        assert vpm_row is not None
        # Byte-identical binding — the dataproof IS the manifest hash
        assert mlga_row["dataproof_hex"] == vpm_row["zkba_manifest_hash_hex"]
        # And both are valid hex
        assert len(mlga_row["dataproof_hex"]) == 64
        int(mlga_row["dataproof_hex"], 16)  # valid hex
