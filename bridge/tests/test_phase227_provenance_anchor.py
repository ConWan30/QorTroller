"""
bridge/tests/test_phase227_provenance_anchor.py
Phase 227 — ProtocolCoherence + GovernanceProvenance On-Chain Anchor (8 tests)

T227-1: _anchor_cycle() reads get_latest_governance_provenance_hash from store
T227-2: _anchor_cycle() calls anchor_coherence_with_provenance when gov hash available
T227-3: _anchor_cycle() falls back to anchor_coherence when no gov hash (empty string)
T227-4: _anchor_cycle() falls back to anchor_coherence when gov hash is all zeros
T227-5: insert_protocol_coherence_log accepts and stores governance_provenance_hash
T227-6: get_protocol_coherence_status returns governance_provenance_hash field
T227-7: GOVERNANCE_PROVENANCE_ANCHOR_DRIFT contradiction rule fires on hash mismatch
T227-8: GOVERNANCE_PROVENANCE_ANCHOR_DRIFT does not fire when hashes match
"""

import asyncio
import sqlite3
import sys
import tempfile
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# ---------------------------------------------------------------------------
# Store helpers
# ---------------------------------------------------------------------------

def make_store(tmp_dir):
    from vapi_bridge.store import Store
    db_path = os.path.join(tmp_dir, "test_phase227.db")
    return Store(db_path)


# ---------------------------------------------------------------------------
# T227-1: _anchor_cycle reads get_latest_governance_provenance_hash
# ---------------------------------------------------------------------------

def test_t227_1_anchor_cycle_reads_gov_prov_hash(tmp_path):
    """_anchor_cycle() calls get_latest_governance_provenance_hash() on store."""
    store = make_store(str(tmp_path))

    from unittest.mock import MagicMock, AsyncMock, patch

    cfg = MagicMock()
    cfg.protocol_coherence_registry_address = ""

    reads = []
    original_get = store.get_latest_governance_provenance_hash

    def mock_get():
        reads.append(1)
        return ""

    store.get_latest_governance_provenance_hash = mock_get

    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent
    agent = ProtocolCoherenceAgent(store=store, cfg=cfg, chain=None)

    asyncio.get_event_loop().run_until_complete(agent._anchor_cycle())
    assert len(reads) >= 1, "Expected at least one call to get_latest_governance_provenance_hash"


# ---------------------------------------------------------------------------
# T227-2: calls anchor_coherence_with_provenance when gov hash available
# ---------------------------------------------------------------------------

def test_t227_2_uses_with_provenance_when_hash_available(tmp_path):
    """_anchor_cycle() uses anchor_coherence_with_provenance when gov_prov_hash is non-empty and non-zero."""
    store = make_store(str(tmp_path))

    from unittest.mock import MagicMock, AsyncMock

    cfg = MagicMock()
    cfg.protocol_coherence_registry_address = "0xdeadbeef"

    chain = MagicMock()
    chain.anchor_coherence_with_provenance = AsyncMock(return_value="0xabc123tx")
    chain.anchor_coherence = AsyncMock(return_value="0xlegacytx")

    prov_hash = "a" * 64
    store.get_latest_governance_provenance_hash = lambda: prov_hash

    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent
    agent = ProtocolCoherenceAgent(store=store, cfg=cfg, chain=chain)

    asyncio.get_event_loop().run_until_complete(agent._anchor_cycle())

    chain.anchor_coherence_with_provenance.assert_called_once()
    chain.anchor_coherence.assert_not_called()


# ---------------------------------------------------------------------------
# T227-3: falls back to anchor_coherence when no gov hash
# ---------------------------------------------------------------------------

def test_t227_3_fallback_when_no_gov_hash(tmp_path):
    """_anchor_cycle() falls back to anchor_coherence when gov_prov_hash is empty."""
    store = make_store(str(tmp_path))

    from unittest.mock import MagicMock, AsyncMock

    cfg = MagicMock()
    cfg.protocol_coherence_registry_address = "0xdeadbeef"

    chain = MagicMock()
    chain.anchor_coherence_with_provenance = AsyncMock(return_value="0xabc123tx")
    chain.anchor_coherence = AsyncMock(return_value="0xlegacytx")

    store.get_latest_governance_provenance_hash = lambda: ""

    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent
    agent = ProtocolCoherenceAgent(store=store, cfg=cfg, chain=chain)

    asyncio.get_event_loop().run_until_complete(agent._anchor_cycle())

    chain.anchor_coherence.assert_called_once()
    chain.anchor_coherence_with_provenance.assert_not_called()


# ---------------------------------------------------------------------------
# T227-4: falls back to anchor_coherence when gov hash is all zeros
# ---------------------------------------------------------------------------

def test_t227_4_fallback_when_zero_gov_hash(tmp_path):
    """_anchor_cycle() falls back when gov_prov_hash is 64 zeros."""
    store = make_store(str(tmp_path))

    from unittest.mock import MagicMock, AsyncMock

    cfg = MagicMock()
    cfg.protocol_coherence_registry_address = "0xdeadbeef"

    chain = MagicMock()
    chain.anchor_coherence_with_provenance = AsyncMock(return_value="0xabc123tx")
    chain.anchor_coherence = AsyncMock(return_value="0xlegacytx")

    store.get_latest_governance_provenance_hash = lambda: "0" * 64

    from vapi_bridge.protocol_coherence_agent import ProtocolCoherenceAgent
    agent = ProtocolCoherenceAgent(store=store, cfg=cfg, chain=chain)

    asyncio.get_event_loop().run_until_complete(agent._anchor_cycle())

    chain.anchor_coherence.assert_called_once()
    chain.anchor_coherence_with_provenance.assert_not_called()


# ---------------------------------------------------------------------------
# T227-5: insert_protocol_coherence_log stores governance_provenance_hash
# ---------------------------------------------------------------------------

def test_t227_5_store_inserts_governance_provenance_hash(tmp_path):
    """insert_protocol_coherence_log accepts and stores governance_provenance_hash column."""
    store = make_store(str(tmp_path))

    prov = "b" * 64
    store.insert_protocol_coherence_log(
        merkle_root="c" * 64,
        agent_count=37,
        anchor_hash="",
        on_chain_confirmed=False,
        allowlist_hash="d" * 64,
        governance_provenance_hash=prov,
    )

    # Read back via sqlite directly
    import sqlite3
    row = sqlite3.connect(store._db_path).execute(
        "SELECT governance_provenance_hash FROM protocol_coherence_log ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert row[0] == prov


# ---------------------------------------------------------------------------
# T227-6: get_protocol_coherence_status returns governance_provenance_hash
# ---------------------------------------------------------------------------

def test_t227_6_status_returns_governance_provenance_hash(tmp_path):
    """get_protocol_coherence_status() includes governance_provenance_hash key."""
    store = make_store(str(tmp_path))

    prov = "e" * 64
    store.insert_protocol_coherence_log(
        merkle_root="f" * 64,
        agent_count=37,
        anchor_hash="",
        on_chain_confirmed=False,
        allowlist_hash="g" * 64,
        governance_provenance_hash=prov,
    )

    status = store.get_protocol_coherence_status()
    assert "governance_provenance_hash" in status
    assert status["governance_provenance_hash"] == prov


# ---------------------------------------------------------------------------
# T227-7: GOVERNANCE_PROVENANCE_ANCHOR_DRIFT fires on hash mismatch
# ---------------------------------------------------------------------------

def test_t227_7_drift_contradiction_fires_on_mismatch(tmp_path):
    """GOVERNANCE_PROVENANCE_ANCHOR_DRIFT fires when live chain hash != anchored hash."""
    store = make_store(str(tmp_path))

    # Insert a governance_provenance_chain entry with hash "aaa..."
    live_prov = "a" * 64
    store.insert_governance_provenance(
        governance_provenance_hash=live_prov,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="b" * 64,
        reason_category="refactor",
        reason_text="test governance event for phase 227",
    )

    # Insert a protocol_coherence_log entry with DIFFERENT hash "ccc..."
    anchored_prov = "c" * 64
    store.insert_protocol_coherence_log(
        merkle_root="d" * 64,
        agent_count=37,
        anchor_hash="0xtx",
        on_chain_confirmed=True,
        allowlist_hash="e" * 64,
        governance_provenance_hash=anchored_prov,
    )

    import logging
    from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.fleet_coherence_enabled = True
    cfg.dry_run = True
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    bus = MagicMock()
    logger = logging.getLogger("test_t227_7")
    agent = FleetSignalCoherenceAgent(store=store, config=cfg, bus=bus, logger=logger)

    results = asyncio.get_event_loop().run_until_complete(agent._check_contradictions())
    drift_fired = any(r.get("rule_name") == "GOVERNANCE_PROVENANCE_ANCHOR_DRIFT" for r in results)
    assert drift_fired, "Expected GOVERNANCE_PROVENANCE_ANCHOR_DRIFT to fire on mismatch"


# ---------------------------------------------------------------------------
# T227-8: GOVERNANCE_PROVENANCE_ANCHOR_DRIFT does not fire when hashes match
# ---------------------------------------------------------------------------

def test_t227_8_drift_contradiction_does_not_fire_on_match(tmp_path):
    """GOVERNANCE_PROVENANCE_ANCHOR_DRIFT does not fire when hashes match."""
    store = make_store(str(tmp_path))

    matching_prov = "f" * 64
    store.insert_governance_provenance(
        governance_provenance_hash=matching_prov,
        previous_provenance_hash="0" * 64,
        new_allowlist_hash="g" * 64,
        reason_category="bugfix",
        reason_text="matching prov hash test for phase 227",
    )

    store.insert_protocol_coherence_log(
        merkle_root="h" * 64,
        agent_count=37,
        anchor_hash="0xtx2",
        on_chain_confirmed=True,
        allowlist_hash="i" * 64,
        governance_provenance_hash=matching_prov,
    )

    import logging
    from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent
    from unittest.mock import MagicMock
    cfg = MagicMock()
    cfg.fleet_coherence_enabled = True
    cfg.dry_run = True
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    bus = MagicMock()
    logger = logging.getLogger("test_t227_8")
    agent = FleetSignalCoherenceAgent(store=store, config=cfg, bus=bus, logger=logger)

    results = asyncio.get_event_loop().run_until_complete(agent._check_contradictions())
    drift_fired = any(r.get("rule_name") == "GOVERNANCE_PROVENANCE_ANCHOR_DRIFT" for r in results)
    assert not drift_fired, "GOVERNANCE_PROVENANCE_ANCHOR_DRIFT should not fire when hashes match"
