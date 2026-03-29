"""
Phase 135 — TournamentActivationChainAgent Tests (8 tests)

Tests:
1. tournament_activation_chain_log table — empty store returns empty list
2. insert_tournament_activation_chain — roundtrip
3. auto_activate_on_breakthrough config — PERMANENT False
4. agent permanent invariant — _AUTO_ACTIVATE_ON_BREAKTHROUGH constant is False
5. agent fires on breakthrough event (one-shot)
6. agent one-shot guard prevents double fire
7. GET /agent/tournament-activation-chain — 7 required keys
8. Tool #104 get_tournament_activation_chain — 7-key dict
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(_ROOT / "bridge"))

from vapi_bridge.store import Store


def _make_store() -> tuple[Store, str]:
    d = tempfile.mkdtemp()
    db = os.path.join(d, "test.db")
    return Store(db_path=db), db


# ---------------------------------------------------------------------------
# Test 1: empty table
# ---------------------------------------------------------------------------

def test_1_tournament_activation_chain_log_empty():
    store, _ = _make_store()
    entries = store.get_tournament_activation_chain(limit=10)
    assert entries == []


# ---------------------------------------------------------------------------
# Test 2: insert roundtrip
# ---------------------------------------------------------------------------

def test_2_insert_tournament_activation_chain_roundtrip():
    store, _ = _make_store()
    entry_id = store.insert_tournament_activation_chain(
        event_type="breakthrough_received",
        separation_ratio=1.05,
        n_players=3,
        gate_open_notified=True,
        notes="test note",
    )
    assert isinstance(entry_id, int) and entry_id >= 1
    entries = store.get_tournament_activation_chain(limit=1)
    assert len(entries) == 1
    e = entries[0]
    assert e["event_type"] == "breakthrough_received"
    assert abs(e["separation_ratio"] - 1.05) < 0.001
    assert e["n_players"] == 3
    assert e["gate_open_notified"] == 1
    assert e["auto_activate_blocked"] == 1
    assert e["operator_action_required"] == 1


# ---------------------------------------------------------------------------
# Test 3: auto_activate_on_breakthrough is PERMANENT False
# ---------------------------------------------------------------------------

def test_3_auto_activate_on_breakthrough_permanent_false():
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.auto_activate_on_breakthrough is False


# ---------------------------------------------------------------------------
# Test 4: agent constant is False
# ---------------------------------------------------------------------------

def test_4_agent_permanent_constant_false():
    from vapi_bridge.tournament_activation_chain_agent import _AUTO_ACTIVATE_ON_BREAKTHROUGH
    assert _AUTO_ACTIVATE_ON_BREAKTHROUGH is False


# ---------------------------------------------------------------------------
# Test 5: agent fires on breakthrough event
# ---------------------------------------------------------------------------

def test_5_agent_fires_on_breakthrough():
    store, _ = _make_store()
    cfg = MagicMock()
    cfg.auto_activate_on_breakthrough = False

    from vapi_bridge.tournament_activation_chain_agent import TournamentActivationChainAgent

    agent = TournamentActivationChainAgent(cfg=cfg, store=store, bus=None)

    async def _run():
        await agent._on_breakthrough({"ratio": 1.05, "n_players": 3})

    asyncio.get_event_loop().run_until_complete(_run())

    entries = store.get_tournament_activation_chain(limit=1)
    assert len(entries) == 1
    assert entries[0]["gate_open_notified"] == 1
    assert agent._fired is True


# ---------------------------------------------------------------------------
# Test 6: one-shot guard prevents double fire
# ---------------------------------------------------------------------------

def test_6_agent_one_shot_guard():
    store, _ = _make_store()
    cfg = MagicMock()
    from vapi_bridge.tournament_activation_chain_agent import TournamentActivationChainAgent

    agent = TournamentActivationChainAgent(cfg=cfg, store=store, bus=None)

    async def _run():
        await agent._on_breakthrough({"ratio": 1.05, "n_players": 3})
        await agent._on_breakthrough({"ratio": 1.10, "n_players": 3})  # should be ignored

    asyncio.get_event_loop().run_until_complete(_run())

    entries = store.get_tournament_activation_chain(limit=10)
    assert len(entries) == 1, "one-shot guard should prevent second fire"


# ---------------------------------------------------------------------------
# Test 7: GET /agent/tournament-activation-chain — 7 required keys
# ---------------------------------------------------------------------------

def test_7_endpoint_7_keys():
    from fastapi.testclient import TestClient
    from vapi_bridge.operator_api import create_operator_app

    store, db = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_per_minute = 0

    app = create_operator_app(cfg=cfg, store=store)
    client = TestClient(app, raise_server_exceptions=False)

    resp = client.get("/agent/tournament-activation-chain?api_key=test-key")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("gate_open_notified", "auto_activate_on_breakthrough",
                "operator_action_required", "last_ratio", "last_notification_ts",
                "notification_count", "timestamp"):
        assert key in data, f"missing key: {key}"
    # PERMANENT INVARIANT check
    assert data["auto_activate_on_breakthrough"] is False
    assert data["operator_action_required"] is True


# ---------------------------------------------------------------------------
# Test 8: Tool #104 returns 7-key dict
# ---------------------------------------------------------------------------

def test_8_tool_104_returns_7_keys():
    from vapi_bridge.bridge_agent import BridgeAgent

    store, _ = _make_store()
    cfg = MagicMock()
    cfg.operator_api_key = "test-key"

    agent = BridgeAgent.__new__(BridgeAgent)
    agent._store = store
    agent._cfg = cfg
    agent._chain = MagicMock()

    result = agent._execute_tool("get_tournament_activation_chain", {})
    for key in ("gate_open_notified", "auto_activate_on_breakthrough",
                "operator_action_required", "last_ratio", "last_notification_ts",
                "notification_count", "timestamp"):
        assert key in result, f"missing key: {key}"
    assert result["auto_activate_on_breakthrough"] is False
