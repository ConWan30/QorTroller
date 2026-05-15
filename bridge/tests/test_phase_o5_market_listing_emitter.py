"""Phase O5-MLGA Stage 10 — MARKET-LISTING-v1 autonomous emission tests.

T-ML-1   emit with minimal listing dict (synthesizes consent)
T-ML-2   emit with full listing dict + suspended=True -> revoked status
T-ML-3   invalid commitment_hex -> returns None
T-ML-4   verdict label flows through to preimage
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

def test_t_ml_1_minimal_listing():
    from vapi_bridge.market_listing_emitter import emit_market_listing
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        commit = "ab" * 32
        result = emit_market_listing(
            store=store, cfg=cfg,
            commitment_hex=commit,
            listing={},  # minimal — emitter synthesizes everything
            verdict="APPROVED",
        )
        assert result is not None
        assert result["action"] == "emitted"
        con = sqlite3.connect(store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        row = con.execute(
            "SELECT vpm_id, zkba_class, proof_weight, preimage_json "
            "FROM vpm_artifact_log WHERE vpm_id='MARKET-LISTING-v1'"
        ).fetchone()
        con.close()
        assert row is not None
        assert row["zkba_class"] == 7    # MARKET
        assert row["proof_weight"] == 4  # MARKETPLACE_DERIVED
        snap = json.loads(row["preimage_json"])
        assert snap["listing_commitment_hex"] == commit
        assert snap["verdict"] == "APPROVED"
        assert snap["suspended"] is False


# ----- T-2 -----

def test_t_ml_2_full_listing_suspended():
    from vapi_bridge.market_listing_emitter import emit_market_listing
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        commit = "cd" * 32
        listing = {
            "seller_address": "0xAbCdEf0123456789aBCdEf0123456789aBcDeF01",
            "ipfs_cid": "bafyreidfytestpinfor1234567890",
            "tier_multiplier_milli": 2500,
            "price_iotx": 1.5,
            "consent_hash": "ef" * 32,
            "suspended": True,
            "listing_title": "Test Listing",
        }
        result = emit_market_listing(
            store=store, cfg=cfg,
            commitment_hex=commit,
            listing=listing,
            verdict="FLAGGED_TIER_MISMATCH",
        )
        assert result is not None
        con = sqlite3.connect(store._db_path, timeout=2.0)
        con.row_factory = sqlite3.Row
        snap = json.loads(con.execute(
            "SELECT preimage_json FROM vpm_artifact_log "
            "WHERE vpm_id='MARKET-LISTING-v1'"
        ).fetchone()["preimage_json"])
        con.close()
        assert snap["suspended"] is True
        assert snap["ipfs_cid"] == "bafyreidfytestpinfor1234567890"
        assert snap["price_iotx_milli"] == 1500
        assert snap["tier_multiplier_milli"] == 2500
        assert snap["verdict"] == "FLAGGED_TIER_MISMATCH"


# ----- T-3 -----

def test_t_ml_3_invalid_commitment_returns_none():
    from vapi_bridge.market_listing_emitter import emit_market_listing
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        result = emit_market_listing(
            store=store, cfg=cfg,
            commitment_hex="too-short",
            listing={},
        )
        assert result is None


# ----- T-4 -----

def test_t_ml_4_verdict_flows_to_preimage():
    from vapi_bridge.market_listing_emitter import emit_market_listing
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as td:
        store = _make_store(td)
        cfg = MagicMock()
        for verdict in ["APPROVED", "FLAGGED_ANCHOR_STALE",
                         "REJECTED_INVALID_COMMITMENT"]:
            # Distinct commit per call to avoid UNIQUE collision
            commit = f"{ord(verdict[0]):02x}" + ("ff" * 31)
            result = emit_market_listing(
                store=store, cfg=cfg,
                commitment_hex=commit,
                listing={},
                verdict=verdict,
            )
            assert result is not None
        # Should have 3 rows total
        con = sqlite3.connect(store._db_path, timeout=2.0)
        n = con.execute(
            "SELECT COUNT(*) FROM vpm_artifact_log "
            "WHERE vpm_id='MARKET-LISTING-v1'"
        ).fetchone()[0]
        con.close()
        assert n == 3
