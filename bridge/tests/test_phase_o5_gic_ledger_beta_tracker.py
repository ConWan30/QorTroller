"""Phase O5-MLGA Stage 5 — GIC-LEDGER-BETA-v1 autonomous emission tests.

T-GIC-BETA-1   Tracker constructs with defaults; seed=0 on empty DB
T-GIC-BETA-2   poll_once with chain_length<10 -> noop_below_next_milestone
T-GIC-BETA-3   poll_once with chain_length>=10 -> emits + advances state
T-GIC-BETA-4   Re-poll at same milestone -> noop (idempotent within session)
T-GIC-BETA-5   Crosses 20 after 10 -> emits 20, last_emitted_length=20
T-GIC-BETA-6   Restart: tracker seeds from existing vpm_artifact_log rows
T-GIC-BETA-7   GIC_100 on grind_phase235_v1 -> on_chain_anchor=True with
               Phase 239 G3 frozen anchor values
T-GIC-BETA-8   No grind_session_id in cfg -> noop_no_grind_session
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


def _make_tracker(*, db_path, grind_session_id="test_grind_v1"):
    from vapi_bridge.store import Store
    from vapi_bridge.gic_ledger_beta_tracker import GicLedgerBetaTracker
    cfg = MagicMock()
    cfg.gic_ledger_beta_tracker_enabled = True
    cfg.gic_ledger_beta_interval_s = 30
    cfg.grind_session_id = grind_session_id
    store = Store(db_path=db_path)
    tracker = GicLedgerBetaTracker(store=store, cfg=cfg)
    return tracker, store


def _stub_chain_status(monkeypatch, store, *, chain_length, chain_head_hex=None):
    """Patch store.get_grind_chain_status to return canned data."""
    chain_head_hex = chain_head_hex or ("ab" * 32)
    def fake_status(session_id, cfg=None):
        return {
            "grind_session_id": session_id,
            "chain_length":     chain_length,
            "latest_gic_hash":  chain_head_hex,
            "chain_intact":     True,
            "genesis_ts":       1.0,
            "latest_ts":        100.0,
        }
    monkeypatch.setattr(store, "get_grind_chain_status", fake_status)


# ----- T-1 -----

def test_t_gic_beta_1_constructs_with_defaults():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, _ = _make_tracker(db_path=os.path.join(td, "t.db"))
        assert tracker._state.last_emitted_length == 0
        assert tracker._state.emissions_this_session == 0
        assert tracker._milestone_step == 10


# ----- T-2 -----

def test_t_gic_beta_2_below_next_milestone_noop(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, store = _make_tracker(db_path=os.path.join(td, "t.db"))
        _stub_chain_status(monkeypatch, store, chain_length=7)
        result = tracker.poll_once()
        assert result["action"] == "noop_below_next_milestone"
        assert result["next_milestone"] == 10
        assert tracker._state.last_emitted_length == 0


# ----- T-3 -----

def test_t_gic_beta_3_crosses_first_milestone_emits(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db_path=db)
        _stub_chain_status(monkeypatch, store, chain_length=12)
        result = tracker.poll_once()
        assert result["action"] == "emitted"
        assert result["milestone"] == 10
        assert tracker._state.last_emitted_length == 10
        assert tracker._state.emissions_this_session == 1
        # Persisted to vpm_artifact_log
        con = sqlite3.connect(db, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT vpm_id, commitment_hex, zkba_class, proof_weight "
            "FROM vpm_artifact_log WHERE vpm_id='GIC-LEDGER-BETA-v1'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row["vpm_id"] == "GIC-LEDGER-BETA-v1"
        assert row["zkba_class"] == 2     # ZKBAClass.GIC
        assert row["proof_weight"] == 3   # ProofWeightClass.CHAIN_ONLY


# ----- T-4 -----

def test_t_gic_beta_4_repoll_same_milestone_noop(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, store = _make_tracker(db_path=os.path.join(td, "t.db"))
        _stub_chain_status(monkeypatch, store, chain_length=15)
        r1 = tracker.poll_once()
        r2 = tracker.poll_once()
        assert r1["action"] == "emitted"
        assert r2["action"] == "noop_below_next_milestone"
        assert r2["next_milestone"] == 20
        assert tracker._state.emissions_this_session == 1


# ----- T-5 -----

def test_t_gic_beta_5_crosses_second_milestone(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, store = _make_tracker(db_path=os.path.join(td, "t.db"))
        _stub_chain_status(monkeypatch, store, chain_length=12)
        tracker.poll_once()  # emits 10
        _stub_chain_status(monkeypatch, store, chain_length=23,
                            chain_head_hex="cd" * 32)
        r2 = tracker.poll_once()
        assert r2["action"] == "emitted"
        assert r2["milestone"] == 20
        assert tracker._state.last_emitted_length == 20
        assert tracker._state.emissions_this_session == 2


# ----- T-6 -----

def test_t_gic_beta_6_seeds_from_existing_rows(monkeypatch):
    """Bridge restart simulation — tracker seeds last_emitted_length
    from highest existing vpm_artifact_log row."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        # Manually seed an existing emission row
        from vapi_bridge.store import Store
        store = Store(db_path=db)
        store.insert_vpm_artifact(
            commitment_hex="aa" * 32,
            vpm_id="GIC-LEDGER-BETA-v1",
            zkba_class=2, proof_weight=3,
            visual_state="live", capture_mode="live",
            integrity_label_hash_hex="bb" * 32,
            wrapper_schema="vapi-vpm-artifact-v1",
            zkba_manifest_hash_hex="cc" * 32,
            manifest_uri="/tmp/fake.html",
            compiler_output_hash_hex="aa" * 32,
            preimage_json=json.dumps({"gic_chain_length": 50}),
            ts_ns=int(time.time_ns()),
        )
        from vapi_bridge.gic_ledger_beta_tracker import GicLedgerBetaTracker
        cfg = MagicMock()
        cfg.gic_ledger_beta_interval_s = 30
        cfg.grind_session_id = "test_v1"
        tracker = GicLedgerBetaTracker(store=store, cfg=cfg)
        assert tracker._state.last_emitted_length == 50
        # Next emission should be at 60, not at 10
        _stub_chain_status(monkeypatch, store, chain_length=55)
        r = tracker.poll_once()
        assert r["action"] == "noop_below_next_milestone"
        assert r["next_milestone"] == 60


# ----- T-7 -----

def test_t_gic_beta_7_gic_100_on_phase_235_session_has_anchor(monkeypatch):
    """The Phase 239 G3 anchor is FROZEN-pinned for the grind_phase235_v1
    session at chain_length>=100. Tracker emits with the real tx hash +
    block."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, store = _make_tracker(
            db_path=os.path.join(td, "t.db"),
            grind_session_id="grind_phase235_v1",
        )
        # Pre-emit milestones 10..90 so 100 is next
        tracker._state.last_emitted_length = 90
        _stub_chain_status(monkeypatch, store, chain_length=105)
        r = tracker.poll_once()
        assert r["action"] == "emitted"
        assert r["milestone"] == 100
        # Verify preimage_json carries the anchor refs
        con = sqlite3.connect(tracker._store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT preimage_json FROM vpm_artifact_log "
            "WHERE vpm_id='GIC-LEDGER-BETA-v1' ORDER BY id DESC LIMIT 1"
        ).fetchone()
        con.close()
        pre = json.loads(row["preimage_json"])
        assert pre["on_chain_anchor"] is True
        assert pre["anchor_tx_hash"].startswith("0xe807347e")
        assert pre["anchor_block"] == 43348052


# ----- T-8 -----

def test_t_gic_beta_8_no_grind_session_noop(monkeypatch):
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        from vapi_bridge.store import Store
        from vapi_bridge.gic_ledger_beta_tracker import GicLedgerBetaTracker
        cfg = MagicMock()
        cfg.gic_ledger_beta_interval_s = 30
        cfg.grind_session_id = ""  # not set
        tracker = GicLedgerBetaTracker(
            store=Store(db_path=os.path.join(td, "t.db")), cfg=cfg,
        )
        r = tracker.poll_once()
        assert r["action"] == "noop_no_grind_session"
