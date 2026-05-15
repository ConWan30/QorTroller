"""Phase O5-MLGA Stage 8 — CDRR-DAG-v1 autonomous emission tests.

T-CDRR-1   Tracker constructs; empty fleet_coherence_log -> last_seen=0
T-CDRR-2   poll with no findings -> noop
T-CDRR-3   poll with new HIGH finding -> emits + advances last_seen
T-CDRR-4   poll twice on same finding -> emit once then noop
T-CDRR-5   MEDIUM severity finding -> noop (only HIGH/CRITICAL trigger)
T-CDRR-6   Restart skips historical findings (seeds at current max)
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


def _make_tracker(*, db_path):
    from vapi_bridge.store import Store
    from vapi_bridge.cdrr_dag_tracker import CdrrDagTracker
    cfg = MagicMock()
    cfg.cdrr_dag_tracker_enabled = True
    cfg.cdrr_dag_poll_interval_s = 60
    store = Store(db_path=db_path)
    tracker = CdrrDagTracker(store=store, cfg=cfg)
    return tracker, store


def _seed_coherence(db_path, *, rule_name, severity, coherence_id):
    with sqlite3.connect(db_path, timeout=2.0) as con:
        con.execute(
            "INSERT INTO fleet_coherence_log "
            "(coherence_id, failure_mode, rule_name, agents_involved, "
            " severity, explanation, resolution) "
            "VALUES (?, 'CONTRADICTION', ?, '[]', ?, 'test', 'test')",
            (coherence_id, rule_name, severity),
        )
        con.commit()
        row = con.execute(
            "SELECT id FROM fleet_coherence_log WHERE coherence_id=?",
            (coherence_id,),
        ).fetchone()
    return row[0]


# ----- T-1 -----

def test_t_cdrr_1_constructs_empty_db():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, _ = _make_tracker(db_path=os.path.join(td, "t.db"))
        assert tracker._state.last_seen_coherence_id == 0
        assert tracker._state.emissions_this_session == 0


# ----- T-2 -----

def test_t_cdrr_2_no_findings_noop():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        tracker, _ = _make_tracker(db_path=os.path.join(td, "t.db"))
        result = tracker.poll_once()
        assert result["action"] == "noop_no_new_findings"


# ----- T-3 -----

def test_t_cdrr_3_new_high_finding_emits():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db_path=db)
        # Reset seeded state — tracker was just instantiated; seed
        # would have grabbed current max (0). Now insert a row.
        row_id = _seed_coherence(
            db, rule_name="TEST_RULE", severity="HIGH",
            coherence_id="coh_test_001",
        )
        result = tracker.poll_once()
        assert result["action"] == "emitted"
        assert result["trigger_row_id"] == row_id
        assert tracker._state.last_seen_coherence_id == row_id
        assert tracker._state.emissions_this_session == 1
        # Verify vpm_artifact_log row
        con = sqlite3.connect(db, timeout=2.0)
        con.row_factory = sqlite3.Row
        vrow = con.execute(
            "SELECT vpm_id, zkba_class, proof_weight, preimage_json "
            "FROM vpm_artifact_log WHERE vpm_id='CDRR-DAG-v1'"
        ).fetchone()
        con.close()
        assert vrow is not None
        assert vrow["zkba_class"] == 4    # HARDWARE
        assert vrow["proof_weight"] == 3  # CHAIN_ONLY
        snap = json.loads(vrow["preimage_json"])
        assert snap["severity"] == "HIGH"
        assert snap["rule_name"] == "TEST_RULE"


# ----- T-4 -----

def test_t_cdrr_4_same_finding_emits_once():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, store = _make_tracker(db_path=db)
        _seed_coherence(db, rule_name="R1", severity="HIGH",
                         coherence_id="coh_a")
        r1 = tracker.poll_once()
        r2 = tracker.poll_once()
        assert r1["action"] == "emitted"
        assert r2["action"] == "noop_no_new_findings"
        assert tracker._state.emissions_this_session == 1


# ----- T-5 -----

def test_t_cdrr_5_medium_severity_noop():
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        tracker, _ = _make_tracker(db_path=db)
        _seed_coherence(db, rule_name="R_MED", severity="MEDIUM",
                         coherence_id="coh_med_1")
        result = tracker.poll_once()
        assert result["action"] == "noop_no_new_findings"
        assert tracker._state.emissions_this_session == 0


# ----- T-6 -----

def test_t_cdrr_6_restart_skips_historical():
    """A bridge restart should NOT replay every historical
    HIGH/CRITICAL finding; it should seed at the current max."""
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        db = os.path.join(td, "t.db")
        from vapi_bridge.store import Store
        store = Store(db_path=db)
        # Seed historical HIGH findings BEFORE the tracker is constructed
        _seed_coherence(db, rule_name="R_OLD_1", severity="HIGH",
                         coherence_id="coh_old_1")
        _seed_coherence(db, rule_name="R_OLD_2", severity="CRITICAL",
                         coherence_id="coh_old_2")
        from vapi_bridge.cdrr_dag_tracker import CdrrDagTracker
        cfg = MagicMock()
        cfg.cdrr_dag_poll_interval_s = 60
        tracker = CdrrDagTracker(store=store, cfg=cfg)
        # Seeded at 2 (current max), so first poll is noop
        assert tracker._state.last_seen_coherence_id == 2
        result = tracker.poll_once()
        assert result["action"] == "noop_no_new_findings"
        # New finding after restart -> emits
        _seed_coherence(db, rule_name="R_NEW", severity="HIGH",
                         coherence_id="coh_new_1")
        r2 = tracker.poll_once()
        assert r2["action"] == "emitted"
        assert tracker._state.emissions_this_session == 1
