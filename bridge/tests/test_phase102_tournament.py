"""
Phase 102 — Developer Integration Layer: Bridge Tests (8 tests)
Bridge count: 1414 → 1422 (+8)
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from vapi_bridge.store import Store

try:
    from starlette.testclient import TestClient
except ImportError:
    from fastapi.testclient import TestClient


# ── Helpers ────────────────────────────────────────────────────────────────

def make_store() -> Store:
    """Create an isolated Store for testing."""
    td = tempfile.mkdtemp()
    return Store(str(Path(td) / "test_102.db"))


def make_cfg(**kwargs):
    """Minimal config object."""
    class Cfg:
        agent_dry_run_mode       = True
        vhp_renewal_warning_days = 7
    for k, v in kwargs.items():
        setattr(Cfg, k, v)
    return Cfg()


# ── test_1: insert_vhp_renewal + get_vhp_renewal_log ──────────────────────

def test_1_insert_and_get_vhp_renewal_log():
    """insert_vhp_renewal + get_vhp_renewal_log returns record with 8 required fields."""
    store = make_store()
    now   = time.time()
    store.insert_vhp_renewal(
        device_id="dev-abc",
        token_id=1,
        old_expires_at=now,
        new_expires_at=now + 90 * 86400,
        tx_hash="0xdeadbeef",
        dry_run=True,
    )
    logs = store.get_vhp_renewal_log()
    assert len(logs) == 1
    record = logs[0]
    for f in ("id", "device_id", "token_id", "old_expires_at",
              "new_expires_at", "tx_hash", "dry_run", "created_at"):
        assert f in record, f"Missing field: {f}"
    assert record["device_id"] == "dev-abc"
    assert record["token_id"]  == 1
    assert record["dry_run"]   is True


# ── test_2: get_expiring_vhps ─────────────────────────────────────────────

def test_2_get_expiring_vhps():
    """get_expiring_vhps(cutoff) returns VHPs where expires_at < cutoff AND > now."""
    store = make_store()
    now   = time.time()
    # Insert a VHP issuance that expires in 3 days (within 7-day window)
    store.insert_vhp_issuance(
        device_id="dev-expiring",
        to_address="0xabc",
        token_id=10,
        cert_level=1,
        consecutive_clean=3,
        expires_at=now + 3 * 86400,
        tx_hash="0xfeed",
    )
    # Insert one that is already expired (should NOT appear)
    store.insert_vhp_issuance(
        device_id="dev-expired",
        to_address="0xdef",
        token_id=11,
        cert_level=1,
        consecutive_clean=1,
        expires_at=now - 86400,
        tx_hash="0xbeef",
    )
    cutoff   = now + 7 * 86400
    expiring = store.get_expiring_vhps(cutoff)
    device_ids = [e["device_id"] for e in expiring]
    assert "dev-expiring" in device_ids
    assert "dev-expired"  not in device_ids


# ── test_3: get_total_vhp_count ───────────────────────────────────────────

def test_3_get_total_vhp_count_zero():
    """get_total_vhp_count() returns 0 on fresh store."""
    store = make_store()
    assert store.get_total_vhp_count() == 0


# ── test_4: GET /agent/vhp-renewal-log endpoint ───────────────────────────

def test_4_vhp_renewal_log_endpoint():
    """GET /agent/vhp-renewal-log returns 200 with {logs, total_count, timestamp}."""
    from vapi_bridge.operator_api import create_operator_app
    from unittest.mock import MagicMock

    store = make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "testkey102"
    cfg.rate_limit_requests = 100
    cfg.rate_limit_window_seconds = 60.0

    app    = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app)
    resp   = client.get("/agent/vhp-renewal-log?api_key=testkey102")
    assert resp.status_code == 200
    data = resp.json()
    assert "logs"        in data
    assert "total_count" in data
    assert "timestamp"   in data


# ── test_5: bad api_key → 403 ─────────────────────────────────────────────

def test_5_bad_api_key():
    """bad api_key on GET /agent/vhp-renewal-log → 403."""
    from vapi_bridge.operator_api import create_operator_app
    from unittest.mock import MagicMock

    store = make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "realkey"
    cfg.rate_limit_requests = 100
    cfg.rate_limit_window_seconds = 60.0

    app    = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app)
    resp   = client.get("/agent/vhp-renewal-log?api_key=wrongkey")
    assert resp.status_code == 403


# ── test_6: VHPRenewalAgent dry_run ───────────────────────────────────────

def test_6_vhp_renewal_agent_dry_run():
    """VHPRenewalAgent._check_and_renew with dry_run=True → no chain call; inserts renewal."""
    from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent

    store = make_store()
    now   = time.time()

    # Insert an expiring VHP
    store.insert_vhp_issuance(
        device_id="dev-renew",
        to_address="0x1234",
        token_id=5,
        cert_level=1,
        consecutive_clean=2,
        expires_at=now + 2 * 86400,
        tx_hash="0x0abc",
    )

    chain_calls = []

    class FakeChain:
        async def renew_vhp(self, token_id):
            chain_calls.append(token_id)
            return "0xtxhash"

    cfg   = make_cfg(agent_dry_run_mode=True, vhp_renewal_warning_days=7)
    agent = VHPRenewalAgent(cfg, store, chain=FakeChain())
    asyncio.get_event_loop().run_until_complete(agent._check_and_renew())

    assert len(chain_calls) == 0, "chain.renew_vhp should NOT be called in dry_run mode"
    logs = store.get_vhp_renewal_log()
    assert len(logs) == 1
    assert logs[0]["dry_run"] is True
    assert logs[0]["device_id"] == "dev-renew"


# ── test_7: Tool #69 get_vhp_renewal_log ─────────────────────────────────

def test_7_tool_69_get_vhp_renewal_log():
    """Tool #69 get_vhp_renewal_log returns renewal_count in result dict."""
    from vapi_bridge.bridge_agent import BridgeAgent

    store = make_store()

    class Cfg:
        agent_api_key    = "toolkey"
        operator_api_key = "toolkey"

    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg   = Cfg()

    result = agent._execute_tool("get_vhp_renewal_log", {})
    assert "renewal_count" in result
    assert isinstance(result["renewal_count"], int)
    assert "lifecycle_warning" in result


# ── test_8: VHPRenewalAgent publishes vhp_lifecycle_warning ──────────────

def test_8_vhp_lifecycle_warning_published():
    """VHPRenewalAgent publishes vhp_lifecycle_warning when total_vhp_count==0."""
    from vapi_bridge.vhp_renewal_agent import VHPRenewalAgent

    store = make_store()

    published = []

    class FakeBus:
        def publish_sync(self, topic, payload, source=None):
            published.append((topic, payload))

    cfg   = make_cfg()
    agent = VHPRenewalAgent(cfg, store, bus=FakeBus())
    asyncio.run(agent._check_and_renew())

    assert any(t == "vhp_lifecycle_warning" for t, _ in published), \
        "Expected vhp_lifecycle_warning event when no VHPs issued"
    warning = next(p for t, p in published if t == "vhp_lifecycle_warning")
    assert warning.get("reason") == "no_vhps_ever_issued"
