"""Phase O5-MLGA Stage 6 — HONESTY-BOARD-v1 autonomous emission tests.

T-HB-1   Tracker constructs with defaults; seed=0 on empty DB
T-HB-2   First poll on empty DB -> emits (no prior emission)
T-HB-3   Re-poll within emission interval -> noop_within_interval
T-HB-4   After emission interval elapses -> emits again
T-HB-5   Restart seeds last_emit_ts_ns from existing vpm_artifact_log row
T-HB-6   Snapshot pulls zkba class count + PV-CI count + activation log
"""
from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bridge"))
sys.path.insert(0, str(ROOT / "scripts"))

sys.modules.setdefault("web3", MagicMock())
sys.modules.setdefault("web3.exceptions", MagicMock())
sys.modules.setdefault("eth_account", MagicMock())


def _make_tracker(*, db_path, emission_interval_s=604800):
    from vapi_bridge.store import Store
    from vapi_bridge.honesty_board_tracker import HonestyBoardTracker
    cfg = MagicMock()
    cfg.honesty_board_tracker_enabled = True
    cfg.honesty_board_poll_interval_s = 3600
    cfg.honesty_board_emission_interval_s = emission_interval_s
    cfg.chain_submission_paused = True
    store = Store(db_path=db_path)
    tracker = HonestyBoardTracker(
        store=store, cfg=cfg,
        emission_interval_s=emission_interval_s,
    )
    return tracker, store


# ----- T-1 -----

def test_t_hb_1_constructs_with_defaults():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, _ = _make_tracker(db_path=os.path.join(td, "t.db"))
        assert tracker._state.last_emit_ts_ns == 0
        assert tracker._state.emissions_this_session == 0


# ----- T-2 -----

def test_t_hb_2_first_poll_emits():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db_path=db)
        result = tracker.poll_once()
        assert result["action"] == "emitted"
        assert tracker._state.emissions_this_session == 1
        # Row in vpm_artifact_log
        con = sqlite3.connect(db, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT vpm_id, zkba_class, proof_weight FROM vpm_artifact_log "
            "WHERE vpm_id='HONESTY-BOARD-v1'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row["vpm_id"] == "HONESTY-BOARD-v1"
        assert row["zkba_class"] == 2
        assert row["proof_weight"] == 3


# ----- T-3 -----

def test_t_hb_3_within_interval_noop():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, _ = _make_tracker(db_path=os.path.join(td, "t.db"))
        r1 = tracker.poll_once()
        r2 = tracker.poll_once()
        assert r1["action"] == "emitted"
        assert r2["action"] == "noop_within_interval"
        assert tracker._state.emissions_this_session == 1


# ----- T-4 -----

def test_t_hb_4_after_interval_emits_again():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        # 1-second interval for fast test
        tracker, _ = _make_tracker(
            db_path=os.path.join(td, "t.db"),
            emission_interval_s=1,
        )
        r1 = tracker.poll_once()
        assert r1["action"] == "emitted"
        time.sleep(1.2)
        r2 = tracker.poll_once()
        assert r2["action"] == "emitted"
        assert tracker._state.emissions_this_session == 2


# ----- T-5 -----

def test_t_hb_5_restart_seeds_last_emit():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db)
        seeded_ts = int(time.time_ns())
        store.insert_vpm_artifact(
            commitment_hex="aa" * 32,
            vpm_id="HONESTY-BOARD-v1",
            zkba_class=2, proof_weight=3,
            visual_state="live", capture_mode="live",
            integrity_label_hash_hex="bb" * 32,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex="cc" * 32,
            manifest_uri="/tmp/fake.html",
            compiler_output_hash_hex="aa" * 32,
            preimage_json="{}",
            ts_ns=seeded_ts,
        )
        from vapi_bridge.honesty_board_tracker import HonestyBoardTracker
        cfg = MagicMock()
        cfg.honesty_board_poll_interval_s = 3600
        cfg.honesty_board_emission_interval_s = 604800
        cfg.chain_submission_paused = True
        tracker = HonestyBoardTracker(store=store, cfg=cfg)
        assert tracker._state.last_emit_ts_ns == seeded_ts
        # Within interval -> noop
        r = tracker.poll_once()
        assert r["action"] == "noop_within_interval"


# ----- T-6 -----

def test_t_hb_6_snapshot_pulls_counts():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db_path=db)
        # Seed a fake zkba_artifact_log row
        con = sqlite3.connect(db, timeout=2.0)
        try:
            con.execute(
                "INSERT INTO zkba_artifact_log "
                "(zkba_class, proof_weight, commitment_hex, preimage_json, "
                " ts_ns, created_at) "
                "VALUES (?, ?, ?, ?, ?, strftime('%s','now'))",
                (2, 3, "f0" * 32, "{}", int(time.time_ns())),
            )
            con.execute(
                "INSERT INTO zkba_artifact_log "
                "(zkba_class, proof_weight, commitment_hex, preimage_json, "
                " ts_ns, created_at) "
                "VALUES (?, ?, ?, ?, ?, strftime('%s','now'))",
                (7, 4, "f1" * 32, "{}", int(time.time_ns())),
            )
            con.commit()
        finally:
            con.close()
        from vapi_bridge.honesty_board_tracker import _snapshot_inputs
        snap = _snapshot_inputs(store=store, cfg=tracker._cfg)
        assert snap["zkba_class_coverage_count"] == 2
        assert snap["chain_submission_paused"] is True
