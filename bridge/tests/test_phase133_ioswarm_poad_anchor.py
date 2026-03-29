"""
Phase 133 — IoSwarm PoAd Auto-Anchor
Tests: +9 (Bridge → +9)

VAPI-exclusive: first DePIN protocol linking distributed AI-consensus (swarm_fingerprint)
to composable on-chain gaming proof (AdjudicationRegistry.recordAdjudication).
"""

import os
import sys
import tempfile
import time

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, os.path.join(ROOT, "bridge"))

from vapi_bridge.store import Store


def _make_store():
    d = tempfile.mkdtemp()
    return Store(db_path=os.path.join(d, "test_133.db"))


# ---------------------------------------------------------------------------

def test_1_poad_anchor_log_table_exists():
    """ioswarm_poad_anchor_log table created at store init."""
    store = _make_store()
    with store._conn() as conn:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ioswarm_poad_anchor_log'"
        )
        row = cur.fetchone()
    assert row is not None, "ioswarm_poad_anchor_log table must exist"


def test_2_insert_anchor_roundtrip():
    """insert_ioswarm_poad_anchor + get_ioswarm_poad_anchor_log roundtrip."""
    store = _make_store()
    row_id = store.insert_ioswarm_poad_anchor(
        device_id="dev_abc",
        session_id="sess_001",
        dual_veto=True,
        swarm_fingerprint="deadbeef" * 8,
        poad_hash="cafebabe" * 8,
        anchor_status="pending",
    )
    assert isinstance(row_id, int) and row_id > 0

    entries = store.get_ioswarm_poad_anchor_log(limit=10)
    assert len(entries) == 1
    e = entries[0]
    assert e["device_id"] == "dev_abc"
    assert e["session_id"] == "sess_001"
    assert e["dual_veto"] == 1
    assert e["swarm_fingerprint"] == "deadbeef" * 8
    assert e["anchor_status"] == "pending"


def test_3_update_anchor_tx_status():
    """update_ioswarm_poad_anchor_tx changes on_chain_tx and anchor_status."""
    store = _make_store()
    row_id = store.insert_ioswarm_poad_anchor(
        device_id="dev_xyz",
        dual_veto=True,
        swarm_fingerprint="aa" * 32,
        poad_hash="bb" * 32,
        anchor_status="pending",
    )
    store.update_ioswarm_poad_anchor_tx(row_id, "0xdeadbeef", "anchored")
    entries = store.get_ioswarm_poad_anchor_log()
    assert entries[0]["on_chain_tx"] == "0xdeadbeef"
    assert entries[0]["anchor_status"] == "anchored"


def test_4_get_anchor_log_newest_first():
    """get_ioswarm_poad_anchor_log returns entries newest first."""
    store = _make_store()
    store.insert_ioswarm_poad_anchor("dev_1", anchor_status="anchored")
    time.sleep(0.01)
    store.insert_ioswarm_poad_anchor("dev_2", anchor_status="pending")
    entries = store.get_ioswarm_poad_anchor_log()
    assert entries[0]["device_id"] == "dev_2"
    assert entries[1]["device_id"] == "dev_1"


def test_5_dual_veto_triggers_anchor_when_enabled():
    """IoSwarmAdjudicationCoordinator auto-anchor fires when ioswarm_poad_auto_anchor_enabled=True."""
    from unittest.mock import MagicMock, patch
    store = _make_store()
    cfg = MagicMock()
    cfg.ioswarm_classj_block_quorum = 0.67
    cfg.ioswarm_triage_block_quorum = 0.67
    cfg.ioswarm_poad_auto_anchor_enabled = True

    from vapi_bridge.ioswarm_adjudication_coordinator import IoSwarmAdjudicationCoordinator

    # Force dual_veto by making both emulators return BLOCK quorum
    classj_emu = MagicMock()
    classj_emu.evaluate_classj.return_value = [{"verdict": "BLOCK"}, {"verdict": "BLOCK"}, {"verdict": "BLOCK"}]
    triage_emu = MagicMock()
    triage_emu.evaluate_triage.return_value = [{"verdict": "BLOCK"}, {"verdict": "BLOCK"}, {"verdict": "BLOCK"}]

    # Mock ensure_future to prevent asyncio errors in sync test context
    with patch("asyncio.ensure_future") as mock_ef:
        coord = IoSwarmAdjudicationCoordinator(
            cfg=cfg, store=store,
            classj_emulator=classj_emu,
            triage_emulator=triage_emu,
        )
        result = coord.evaluate(
            device_id="test_dev",
            session_id="sess_123",
            entropy_variance=0.01,
            escalated=True,
        )

    assert result["dual_veto"] is True
    # ensure_future was called (anchor was scheduled)
    mock_ef.assert_called_once()


def test_6_dual_veto_no_anchor_when_disabled():
    """IoSwarmAdjudicationCoordinator does NOT schedule anchor when disabled."""
    from unittest.mock import MagicMock, patch
    store = _make_store()
    cfg = MagicMock()
    cfg.ioswarm_classj_block_quorum = 0.67
    cfg.ioswarm_triage_block_quorum = 0.67
    cfg.ioswarm_poad_auto_anchor_enabled = False

    from vapi_bridge.ioswarm_adjudication_coordinator import IoSwarmAdjudicationCoordinator

    classj_emu = MagicMock()
    classj_emu.evaluate_classj.return_value = [{"verdict": "BLOCK"}, {"verdict": "BLOCK"}, {"verdict": "BLOCK"}]
    triage_emu = MagicMock()
    triage_emu.evaluate_triage.return_value = [{"verdict": "BLOCK"}, {"verdict": "BLOCK"}, {"verdict": "BLOCK"}]

    with patch("asyncio.ensure_future") as mock_ef:
        coord = IoSwarmAdjudicationCoordinator(
            cfg=cfg, store=store,
            classj_emulator=classj_emu,
            triage_emulator=triage_emu,
        )
        result = coord.evaluate(
            device_id="test_dev",
            session_id="sess_123",
            entropy_variance=0.01,
            escalated=True,
        )

    assert result["dual_veto"] is True
    # ensure_future was NOT called (anchor disabled)
    mock_ef.assert_not_called()


def test_7_anchor_failure_non_blocking():
    """_async_anchor_poad never raises even when store and chain both fail."""
    import asyncio
    from unittest.mock import MagicMock
    from vapi_bridge.ioswarm_adjudication_coordinator import IoSwarmAdjudicationCoordinator

    store = MagicMock()
    store.insert_ioswarm_poad_anchor.side_effect = RuntimeError("store boom")
    cfg = MagicMock()
    coord = IoSwarmAdjudicationCoordinator(cfg=cfg, store=store)

    # Must complete without raising
    asyncio.run(coord._async_anchor_poad("dev_fail", "sess_fail", "fp_fail"))
    # No assertion needed — the test passes if no exception propagates


def test_8_endpoint_ioswarm_poad_anchor_7_keys():
    """GET /agent/ioswarm-poad-anchor-status returns the 7 required keys."""
    from unittest.mock import MagicMock
    import importlib

    store = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "testkey"
    cfg.ioswarm_poad_auto_anchor_enabled = False
    cfg.ioswarm_node_urls = ""
    cfg.ioswarm_node_timeout_seconds = 5.0

    import vapi_bridge.operator_api as _oa
    app = _oa.create_operator_app(cfg=cfg, store=store)

    try:
        from fastapi.testclient import TestClient
    except ImportError:
        pytest.skip("fastapi not available")

    client = TestClient(app)
    resp = client.get("/agent/ioswarm-poad-anchor-status?api_key=testkey")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("poad_auto_anchor_enabled", "anchored_count", "pending_count",
                "last_anchor_tx", "dual_veto_count", "anchor_failure_count", "timestamp"):
        assert key in data, f"Missing key: {key}"


def test_9_schema_version_133_present():
    """schema_versions contains (phase=133, migration_name='ioswarm_poad_anchor')."""
    store = _make_store()
    with store._conn() as conn:
        cur = conn.execute(
            "SELECT migration_name FROM schema_versions WHERE phase = 133"
        )
        row = cur.fetchone()
    assert row is not None, "schema_versions must have phase=133"
    assert row[0] == "ioswarm_poad_anchor"
