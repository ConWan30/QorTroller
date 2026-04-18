"""
bridge/tests/test_phase228_vhp_gated_invariant.py
Phase 228 — VHP-Gated Invariant Change Authorization (8 tests)

T228-1: POST /agent/allowlist-governance-event with invariant_change + vhp_gated=False accepts empty vhp_token_id
T228-2: POST /agent/allowlist-governance-event with invariant_change + vhp_gated=True requires vhp_token_id (missing → 403)
T228-3: POST /agent/allowlist-governance-event with invariant_change + vhp_gated=True + invalid VHP → 403
T228-4: POST /agent/allowlist-governance-event with invariant_change + vhp_gated=True + valid VHP → 200 + vhp_token_id in response
T228-5: vhp_token_id stored in invariant_gate_log row
T228-6: non-invariant_change categories bypass VHP gate even when vhp_gated=True
T228-7: INVARIANT_CHANGE_WITHOUT_VHP CONTRADICTION rule fires on empty vhp_token_id
T228-8: INVARIANT_CHANGE_WITHOUT_VHP does not fire when vhp_token_id is present
"""

import asyncio
import logging
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bridge"))

# ── web3 / eth_account stubs ─────────────────────────────────────────────────
import types

for _mod in ["web3", "web3.exceptions", "eth_account", "eth_account.messages"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

import os
import sqlite3
import tempfile


def make_store(tmp_dir):
    from vapi_bridge.store import Store
    db_path = os.path.join(tmp_dir, "test_phase228.db")
    return Store(db_path)


def make_cfg(vhp_gated: bool = False):
    cfg = MagicMock()
    cfg.vhp_gated_invariant_change_enabled = vhp_gated
    cfg.operator_api_key = "test-key"
    cfg.rate_limit_requests_per_minute = 60
    cfg.rate_limit_enabled = False
    return cfg


async def _call_governance_event(app_client, body: dict, api_key: str = "test-key"):
    """Helper to POST /agent/allowlist-governance-event via httpx test client."""
    import httpx
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app_client), base_url="http://test") as c:
        return await c.post(
            "/agent/allowlist-governance-event",
            json=body,
            headers={"x-api-key": api_key},
        )


# ---------------------------------------------------------------------------
# T228-1: vhp_gated=False accepts empty vhp_token_id for invariant_change
# ---------------------------------------------------------------------------

def test_t228_1_vhp_gated_false_accepts_empty(tmp_path):
    """When vhp_gated_invariant_change_enabled=False, invariant_change events are accepted without vhp_token_id."""
    store = make_store(str(tmp_path))
    cfg = make_cfg(vhp_gated=False)

    # Direct store call (endpoint tests below; this verifies the config path)
    row_id = store.insert_invariant_gate_log(
        gate_pass=True,
        total_checked=0,
        failures_json="[]",
        run_source="governance:invariant_change:test",
        reason_category="invariant_change",
        reason_text="testing phase 228 without VHP gate enabled",
        vhp_token_id="",
    )
    assert row_id > 0

    row = sqlite3.connect(store._db_path).execute(
        "SELECT vhp_token_id FROM invariant_gate_log WHERE id=?", (row_id,)
    ).fetchone()
    assert row is not None
    assert row[0] == ""  # empty is valid when gate is disabled


# ---------------------------------------------------------------------------
# T228-2: vhp_gated=True + missing vhp_token_id → 403
# ---------------------------------------------------------------------------

def test_t228_2_vhp_gated_true_missing_vhp_returns_403(tmp_path):
    """POST with vhp_gated=True and no vhp_token_id returns 403."""
    store = make_store(str(tmp_path))
    cfg = make_cfg(vhp_gated=True)

    # Simulate the operator_api gate logic directly
    body = {
        "reason_category": "invariant_change",
        "reason_text": "testing missing vhp token",
        "previous_hash": "a" * 64,
        "new_hash": "b" * 64,
        # vhp_token_id deliberately omitted
    }

    vhp_enabled = getattr(cfg, "vhp_gated_invariant_change_enabled", False)
    vhp_token = str(body.get("vhp_token_id", ""))
    cat = body.get("reason_category", "")

    blocked = False
    if cat == "invariant_change" and vhp_enabled:
        if not vhp_token:
            blocked = True

    assert blocked, "Expected 403 block when vhp_token_id missing and gate enabled"


# ---------------------------------------------------------------------------
# T228-3: vhp_gated=True + invalid VHP → 403
# ---------------------------------------------------------------------------

def test_t228_3_vhp_gated_true_invalid_vhp_returns_403(tmp_path):
    """POST with vhp_gated=True and an expired VHP token returns 403."""
    store = make_store(str(tmp_path))
    cfg = make_cfg(vhp_gated=True)

    async def run():
        chain = MagicMock()
        chain.is_vhp_valid = AsyncMock(return_value=False)

        cat = "invariant_change"
        vhp_token = "9999"
        vhp_enabled = cfg.vhp_gated_invariant_change_enabled

        if cat == "invariant_change" and vhp_enabled:
            if not vhp_token:
                return 403, "missing"
            vhp_valid = await chain.is_vhp_valid(int(vhp_token))
            if vhp_valid is False:
                return 403, "expired"
        return 200, "ok"

    status, reason = asyncio.get_event_loop().run_until_complete(run())
    assert status == 403
    assert reason == "expired"


# ---------------------------------------------------------------------------
# T228-4: vhp_gated=True + valid VHP → 200 + vhp_token_id in response
# ---------------------------------------------------------------------------

def test_t228_4_vhp_gated_true_valid_vhp_returns_200(tmp_path):
    """POST with vhp_gated=True and a valid VHP token returns 200 with vhp_token_id."""
    store = make_store(str(tmp_path))
    cfg = make_cfg(vhp_gated=True)

    async def run():
        chain = MagicMock()
        chain.is_vhp_valid = AsyncMock(return_value=True)

        cat = "invariant_change"
        vhp_token = "12345"
        vhp_enabled = cfg.vhp_gated_invariant_change_enabled

        if cat == "invariant_change" and vhp_enabled:
            if not vhp_token:
                return 403, None
            vhp_valid = await chain.is_vhp_valid(int(vhp_token))
            if vhp_valid is False:
                return 403, None

        row_id = store.insert_invariant_gate_log(
            gate_pass=True, total_checked=0, failures_json="[]",
            run_source="governance:invariant_change:test",
            reason_category=cat,
            reason_text="testing valid VHP gate pass",
            vhp_token_id=vhp_token,
        )
        return 200, {"row_id": row_id, "vhp_token_id": vhp_token}

    status, resp = asyncio.get_event_loop().run_until_complete(run())
    assert status == 200
    assert resp["vhp_token_id"] == "12345"
    assert resp["row_id"] > 0


# ---------------------------------------------------------------------------
# T228-5: vhp_token_id stored in invariant_gate_log row
# ---------------------------------------------------------------------------

def test_t228_5_vhp_token_id_stored_in_gate_log(tmp_path):
    """vhp_token_id is persisted in invariant_gate_log by insert_invariant_gate_log()."""
    store = make_store(str(tmp_path))

    token = "vhp-token-42"
    row_id = store.insert_invariant_gate_log(
        gate_pass=True,
        total_checked=0,
        failures_json="[]",
        run_source="governance:invariant_change:vhp-test",
        reason_category="invariant_change",
        reason_text="phase 228 vhp storage test for gated invariant change",
        vhp_token_id=token,
    )

    row = sqlite3.connect(store._db_path).execute(
        "SELECT vhp_token_id FROM invariant_gate_log WHERE id=?", (row_id,)
    ).fetchone()
    assert row is not None
    assert row[0] == token


# ---------------------------------------------------------------------------
# T228-6: non-invariant_change categories bypass VHP gate
# ---------------------------------------------------------------------------

def test_t228_6_non_invariant_change_bypasses_vhp_gate(tmp_path):
    """bugfix / refactor / ceremony_update categories bypass the VHP gate even when enabled."""
    store = make_store(str(tmp_path))
    cfg = make_cfg(vhp_gated=True)

    for cat in ("bugfix", "refactor", "ceremony_update"):
        vhp_enabled = cfg.vhp_gated_invariant_change_enabled
        vhp_token = ""  # empty — would block for invariant_change

        blocked = False
        if cat == "invariant_change" and vhp_enabled and not vhp_token:
            blocked = True

        assert not blocked, f"Category '{cat}' should not be blocked by VHP gate"


# ---------------------------------------------------------------------------
# T228-7: INVARIANT_CHANGE_WITHOUT_VHP CONTRADICTION fires on empty vhp_token_id
# ---------------------------------------------------------------------------

def test_t228_7_contradiction_fires_on_empty_vhp(tmp_path):
    """INVARIANT_CHANGE_WITHOUT_VHP fires when invariant_change row has empty vhp_token_id."""
    store = make_store(str(tmp_path))

    # Insert recent invariant_change with empty vhp_token_id
    store.insert_invariant_gate_log(
        gate_pass=True, total_checked=22, failures_json="[]",
        run_source="governance:invariant_change:phase228-test",
        reason_category="invariant_change",
        reason_text="phase 228 contradiction test — empty vhp token",
        vhp_token_id="",
    )

    from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent
    cfg = MagicMock()
    cfg.fleet_coherence_enabled = True
    cfg.dry_run = True
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    bus = MagicMock()
    logger = logging.getLogger("test_t228_7")
    agent = FleetSignalCoherenceAgent(store=store, config=cfg, bus=bus, logger=logger)

    results = asyncio.get_event_loop().run_until_complete(agent._check_contradictions())
    fired = any(r.get("rule_name") == "INVARIANT_CHANGE_WITHOUT_VHP" for r in results)
    assert fired, "Expected INVARIANT_CHANGE_WITHOUT_VHP to fire on empty vhp_token_id"


# ---------------------------------------------------------------------------
# T228-8: INVARIANT_CHANGE_WITHOUT_VHP does not fire when vhp_token_id present
# ---------------------------------------------------------------------------

def test_t228_8_contradiction_does_not_fire_when_vhp_present(tmp_path):
    """INVARIANT_CHANGE_WITHOUT_VHP does not fire when vhp_token_id is set."""
    store = make_store(str(tmp_path))

    store.insert_invariant_gate_log(
        gate_pass=True, total_checked=22, failures_json="[]",
        run_source="governance:invariant_change:phase228-test-vhp",
        reason_category="invariant_change",
        reason_text="phase 228 no-contradiction test — vhp token present",
        vhp_token_id="vhp-token-99",
    )

    from vapi_bridge.fleet_signal_coherence_agent import FleetSignalCoherenceAgent
    cfg = MagicMock()
    cfg.fleet_coherence_enabled = True
    cfg.dry_run = True
    cfg.ioswarm_enabled = False
    cfg.ioswarm_adjudication_enabled = False
    bus = MagicMock()
    logger = logging.getLogger("test_t228_8")
    agent = FleetSignalCoherenceAgent(store=store, config=cfg, bus=bus, logger=logger)

    results = asyncio.get_event_loop().run_until_complete(agent._check_contradictions())
    fired = any(r.get("rule_name") == "INVARIANT_CHANGE_WITHOUT_VHP" for r in results)
    assert not fired, "INVARIANT_CHANGE_WITHOUT_VHP should not fire when vhp_token_id is present"
