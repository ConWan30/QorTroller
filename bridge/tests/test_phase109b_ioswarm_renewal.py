"""Phase 109B — ioSwarm Renewal Coordinator tests (8 tests).

Test plan:
  1. test_1_store_insert_and_roundtrip        — insert_ioswarm_renewal + get_ioswarm_renewal_log
  2. test_2_certify_renew_4_5_approves        — coordinator with 4/5 CERTIFY_RENEW -> approved=True, ratio~0.80
  3. test_3_skip_renew_4_5_rejects            — coordinator with 4/5 SKIP_RENEW -> approved=False
  4. test_4_tie_becomes_hold_skip             — 2/4 CERTIFY + 2/4 SKIP -> HOLD, approved=False
  5. test_5_ioswarm_disabled_bypasses_coord   — ioswarm_renewal_enabled=False -> no coordinator call
  6. test_6_ioswarm_renewal_status_endpoint   — GET /agent/ioswarm-renewal-status 200, 8 required keys
  7. test_7_bad_key_returns_403               — wrong api_key -> 403
  8. test_8_tool_76_required_fields           — Tool #76 returns required fields
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import types

import pytest

# ---------------------------------------------------------------------------
# Sys-path bootstrap
# ---------------------------------------------------------------------------
_REPO = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# Stub heavy deps before any bridge import
for _mod in ("web3", "web3.exceptions", "eth_account"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

from bridge.vapi_bridge.ioswarm_renewal_coordinator import IoSwarmRenewalCoordinator  # noqa: E402
from bridge.vapi_bridge.store import Store as VAPIStore  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_store():
    tmp = tempfile.mkdtemp()
    return VAPIStore(os.path.join(tmp, "test.db"))


def _make_cfg(ioswarm_renewal_enabled: bool = False):
    return types.SimpleNamespace(
        operator_api_key="test-key-109b",
        rate_limit_enabled=False,
        ioswarm_renewal_enabled=ioswarm_renewal_enabled,
        ioswarm_renewal_min_quorum=3,
        # ioswarm Phase 109A fields
        ioswarm_enabled=False,
        ioswarm_quorum_threshold=0.60,
        ioswarm_block_quorum_threshold=0.67,
        ioswarm_node_count=5,
        ioswarm_endpoint="",
        # existing required fields
        agent_dry_run_mode=True,
        epistemic_consensus_enabled=True,
        epistemic_consensus_threshold=0.60,
        epistemic_recommended_threshold=0.65,
        epistemic_triage_prereq_required=False,
        separation_ratio_current=0.362,
        touchpad_recapture_complete=False,
    )


class _MockEmulator:
    """Inject controlled verdicts for coordinator tests."""

    def __init__(self, verdicts: list[dict]) -> None:
        self._verdicts = verdicts

    def evaluate_renewal(self, device_id, token_id, consecutive_clean, recent_block_count=0):
        return self._verdicts


def _certify_renew_verdicts(n_certify: int, n_skip: int) -> list[dict]:
    vds = []
    for i in range(n_certify):
        vds.append({"node_id": f"node_{i}", "verdict": "CERTIFY_RENEW", "confidence": 0.90})
    for j in range(n_skip):
        vds.append({"node_id": f"node_{n_certify + j}", "verdict": "SKIP_RENEW", "confidence": 0.85})
    return vds


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestIoSwarmRenewalStore:

    def test_1_store_insert_and_roundtrip(self):
        """insert_ioswarm_renewal + get_ioswarm_renewal_log roundtrip with 9 fields."""
        store = _make_store()
        row_id = store.insert_ioswarm_renewal(
            device_id="dev_rt",
            token_id=42,
            quorum_verdict="CERTIFY_RENEW",
            agreement_ratio=0.80,
            node_count=5,
            renewal_approved=1,
            node_verdicts_json=json.dumps([{"node_id": "n1", "verdict": "CERTIFY_RENEW", "confidence": 0.9}]),
        )
        assert row_id > 0
        rows = store.get_ioswarm_renewal_log(device_id="dev_rt", limit=5)
        assert len(rows) == 1
        r = rows[0]
        assert r["device_id"] == "dev_rt"
        assert r["token_id"] == 42
        assert r["quorum_verdict"] == "CERTIFY_RENEW"
        assert r["agreement_ratio"] == pytest.approx(0.80, abs=0.01)
        assert r["node_count"] == 5
        assert r["renewal_approved"] is True
        assert len(r["node_verdicts"]) == 1
        assert "created_at" in r


class TestIoSwarmRenewalCoordinator:

    def test_2_certify_renew_4_5_approves(self):
        """Coordinator with 4/5 CERTIFY_RENEW -> approved=True, ratio~0.80."""
        store = _make_store()
        cfg   = _make_cfg(ioswarm_renewal_enabled=True)
        emulator = _MockEmulator(_certify_renew_verdicts(n_certify=4, n_skip=1))
        coord = IoSwarmRenewalCoordinator(cfg=cfg, store=store, emulator=emulator)
        result = coord.evaluate_renewal(device_id="dev_a", token_id=1, consecutive_clean=5)
        assert result["approved"] is True, result
        assert result["quorum_verdict"] == "CERTIFY_RENEW", result
        assert result["agreement_ratio"] == pytest.approx(0.80, abs=0.01)

    def test_3_skip_renew_4_5_rejects(self):
        """Coordinator with 4/5 SKIP_RENEW -> approved=False."""
        store = _make_store()
        cfg   = _make_cfg(ioswarm_renewal_enabled=True)
        emulator = _MockEmulator(_certify_renew_verdicts(n_certify=1, n_skip=4))
        coord = IoSwarmRenewalCoordinator(cfg=cfg, store=store, emulator=emulator)
        result = coord.evaluate_renewal(device_id="dev_b", token_id=2, consecutive_clean=0)
        assert result["approved"] is False, result

    def test_4_tie_becomes_hold_skip(self):
        """2/4 CERTIFY_RENEW + 2/4 SKIP_RENEW -> HOLD -> approved=False."""
        store = _make_store()
        cfg   = _make_cfg(ioswarm_renewal_enabled=True)
        emulator = _MockEmulator(_certify_renew_verdicts(n_certify=2, n_skip=2))
        coord = IoSwarmRenewalCoordinator(cfg=cfg, store=store, emulator=emulator)
        result = coord.evaluate_renewal(device_id="dev_c", token_id=3, consecutive_clean=2)
        assert result["approved"] is False, result
        assert result["quorum_verdict"] == "HOLD", result


class TestIoSwarmRenewalAgentBypass:

    def test_5_ioswarm_disabled_bypasses_coordinator(self):
        """ioswarm_renewal_enabled=False -> coordinator never instantiated; renewal proceeds."""
        from bridge.vapi_bridge.vhp_renewal_agent import VHPRenewalAgent
        import asyncio

        store = _make_store()
        cfg   = _make_cfg(ioswarm_renewal_enabled=False)

        # Insert a fake expiring VHP into vhp_issuances
        import time as _t
        soon = _t.time() + 3 * 86_400  # expires in 3 days (< default 7-day warning)
        with store._conn() as conn:
            conn.execute(
                "INSERT INTO vhp_issuances "
                "(device_id, token_id, tx_hash, expires_at, cert_level, consecutive_clean) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("dev_bypass", 99, "0xtx", soon, 1, 3),
            )

        agent = VHPRenewalAgent(cfg=cfg, store=store, chain=None, bus=None)
        asyncio.get_event_loop().run_until_complete(agent._check_and_renew())

        # With ioswarm disabled, renewal proceeds (dry_run=True means no chain call)
        # ioswarm_renewal_log stays empty
        renewal_logs = store.get_ioswarm_renewal_log(device_id="dev_bypass")
        assert len(renewal_logs) == 0, "Coordinator should not have run"
        # VHP renewal log should have an entry (dry_run path)
        renewal_entries = store.get_vhp_renewal_log(device_id="dev_bypass")
        assert len(renewal_entries) == 1


class TestIoSwarmRenewalEndpoints:

    def _make_app(self, ioswarm_renewal_enabled: bool = False):
        from bridge.vapi_bridge.operator_api import create_operator_app
        from fastapi.testclient import TestClient
        store = _make_store()
        cfg   = _make_cfg(ioswarm_renewal_enabled=ioswarm_renewal_enabled)
        app   = create_operator_app(cfg=cfg, store=store, bus=None, chain=None)
        return TestClient(app), cfg, store

    def test_6_ioswarm_renewal_status_endpoint_200(self):
        """GET /agent/ioswarm-renewal-status returns 200 with 8 required keys."""
        client, cfg, store = self._make_app()
        resp = client.get("/agent/ioswarm-renewal-status", params={"api_key": "test-key-109b"})
        assert resp.status_code == 200, resp.text
        d = resp.json()
        for key in (
            "ioswarm_renewal_enabled", "min_quorum", "renewal_count",
            "task_spec_registered", "recent_renewal_logs", "recent_approvals",
            "recent_skips", "timestamp",
        ):
            assert key in d, f"Missing key: {key}"
        assert d["ioswarm_renewal_enabled"] is False
        assert d["task_spec_registered"] is True
        assert d["min_quorum"] == 3

    def test_7_bad_key_returns_403(self):
        """Wrong api_key -> 403 Forbidden."""
        client, _, _ = self._make_app()
        resp = client.get("/agent/ioswarm-renewal-status", params={"api_key": "bad-key"})
        assert resp.status_code == 403


class TestIoSwarmRenewalTool76:

    def test_8_tool_76_required_fields(self):
        """Tool #76 get_ioswarm_renewal_status returns required fields without raising."""
        from bridge.vapi_bridge.bridge_agent import BridgeAgent

        store = _make_store()
        cfg   = _make_cfg()

        agent = BridgeAgent.__new__(BridgeAgent)
        agent._cfg   = cfg
        agent._store = store
        agent._client = None
        agent._chain  = None
        agent._bus    = None

        result = agent._execute_tool("get_ioswarm_renewal_status", {})
        assert "ioswarm_renewal_enabled" in result, result
        assert "min_quorum" in result, result
        assert "renewal_count" in result, result
        assert result["ioswarm_renewal_enabled"] is False
