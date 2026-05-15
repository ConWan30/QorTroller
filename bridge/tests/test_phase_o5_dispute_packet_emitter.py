"""Phase O5-MLGA Stage 9 — DISPUTE-PACKET-v1 autonomous emission tests.

T-DP-1   emit succeeds with minimal inputs (no ruling lookup)
T-DP-2   emit resolves ruling_commitment from ruling_validation_log
T-DP-3   invalid adjudicator -> defaults to 'guardian'
T-DP-4   invalid status -> defaults to 'open'
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


def _make_store(td):
    from vapi_bridge.store import Store
    return Store(db_path=os.path.join(td, "t.db"))


# ----- T-1 -----

def test_t_dp_1_emit_minimal_inputs():
    from vapi_bridge.dispute_packet_emitter import emit_dispute_packet
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        result = emit_dispute_packet(
            store=store, cfg=cfg,
            dispute_id="dispute-test-001",
            reason="operator override under test",
        )
        assert result is not None
        assert result["action"] == "emitted"
        # Verify row
        con = sqlite3.connect(store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT vpm_id, zkba_class, proof_weight, preimage_json "
            "FROM vpm_artifact_log WHERE vpm_id='DISPUTE-PACKET-v1'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row["zkba_class"] == 5    # CONSENT
        assert row["proof_weight"] == 3  # CHAIN_ONLY
        snap = json.loads(row["preimage_json"])
        assert snap["dispute_status"] == "open"
        assert snap["adjudicator_agent_id"] == "guardian"


# ----- T-2 -----

def test_t_dp_2_resolves_ruling_commitment():
    from vapi_bridge.dispute_packet_emitter import emit_dispute_packet
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        # Seed a ruling_validation_log row with a known
        # grind_chain_hash (Phase 235-A GIC chain link hash; this is
        # the per-ruling cryptographic identifier the dispute emitter
        # references).
        known_chain_hash = "abcd" * 16
        con = sqlite3.connect(store._db_path, timeout=2.0)
        try:
            con.execute(
                "INSERT INTO ruling_validation_log "
                "(ruling_id, device_id, llm_verdict, fallback_verdict, "
                " llm_confidence, fallback_confidence, divergence, "
                " grind_chain_hash, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (1, "test_device", "FLAG", "FLAG", 0.1, 0.05, 0,
                 known_chain_hash, time.time()),
            )
            con.commit()
            row = con.execute(
                "SELECT id FROM ruling_validation_log "
                "WHERE grind_chain_hash=?",
                (known_chain_hash,),
            ).fetchone()
            rvl_id = row[0]
        finally:
            con.close()

        cfg = MagicMock()
        result = emit_dispute_packet(
            store=store, cfg=cfg,
            dispute_id="dispute-test-002",
            ruling_validation_log_id=rvl_id,
            reason="dispute references real ruling row",
        )
        assert result is not None
        # Check preimage shows the resolved hash
        con = sqlite3.connect(store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        vrow = con.execute(
            "SELECT preimage_json FROM vpm_artifact_log "
            "WHERE vpm_id='DISPUTE-PACKET-v1'"
        ).fetchone()
        con.close()
        snap = json.loads(vrow["preimage_json"])
        assert snap["disputed_ruling_hash_hex"] == known_chain_hash


# ----- T-3 -----

def test_t_dp_3_invalid_adjudicator_defaults_guardian():
    from vapi_bridge.dispute_packet_emitter import emit_dispute_packet
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        result = emit_dispute_packet(
            store=store, cfg=cfg,
            dispute_id="dispute-test-003",
            adjudicator_agent_id="nonexistent_agent",
            reason="test invalid adjudicator default",
        )
        assert result is not None
        con = sqlite3.connect(store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        snap = json.loads(con.execute(
            "SELECT preimage_json FROM vpm_artifact_log "
            "WHERE vpm_id='DISPUTE-PACKET-v1'"
        ).fetchone()["preimage_json"])
        con.close()
        assert snap["adjudicator_agent_id"] == "guardian"


# ----- T-4 -----

def test_t_dp_4_invalid_status_defaults_open():
    from vapi_bridge.dispute_packet_emitter import emit_dispute_packet
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        result = emit_dispute_packet(
            store=store, cfg=cfg,
            dispute_id="dispute-test-004",
            dispute_status="UNKNOWN_STATUS",
            reason="test invalid status default",
        )
        assert result is not None
        con = sqlite3.connect(store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        snap = json.loads(con.execute(
            "SELECT preimage_json FROM vpm_artifact_log "
            "WHERE vpm_id='DISPUTE-PACKET-v1'"
        ).fetchone()["preimage_json"])
        con.close()
        assert snap["dispute_status"] == "open"
