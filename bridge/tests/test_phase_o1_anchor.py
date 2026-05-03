"""Phase O1 C1 — cedar_bundle_anchor.py tests.

T-O1-AN-1   anchor_bundle happy path with mocked chain
T-O1-AN-2   governance-tx-revert path — operational succeeds, governance fails;
            activation_log row records both attempts; AnchorResult.success=False
T-O1-AN-3   missing bundle file → CedarBundleAnchorError
T-O1-AN-4   no-op same-root — returns success without firing chain txs
T-O1-AN-5   reason gate (<10 chars) → CedarBundleAnchorError
T-O1-AN-6   _operator_authority_hash determinism + ts-sensitivity
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from vapi_bridge.cedar_bundle_anchor import (
    AnchorResult,
    CedarBundleAnchor,
    CedarBundleAnchorError,
    _operator_authority_hash,
)


SENTRY_ID = "0xb21e1ec258d2d381c313f84944bd36fbc63badb2c9a24c2412212d3a27e3e42c"


def _bundle_dict():
    return {
        "$schema": "vapi-cedar-bundle-v1",
        "agent_id": SENTRY_ID,
        "phase": "O1_SHADOW",
        "version": 1,
        "issued_at_iso": "2026-05-03T22:00:00Z",
        "lane_prefixes": ["wiki/"],
        "policies": [
            {
                "id": "P-001",
                "effect": "permit",
                "principal": {"agentId": SENTRY_ID},
                "action": "skill:read",
                "resource": "lane://wiki/**",
            },
        ],
    }


def _write_bundle(tmpdir, name="anchor_sentry.json", overrides=None):
    bundle = _bundle_dict()
    if overrides:
        bundle.update(overrides)
    p = Path(tmpdir) / name
    with open(p, "w", encoding="utf-8") as f:
        json.dump(bundle, f)
    return p


class _MockChain:
    """Mock VAPIChain that records calls + returns canned tx hashes."""
    def __init__(self, current_root=b"\x00" * 32, gov_should_revert=False, op_should_revert=False):
        self.current_root = current_root
        self.gov_should_revert = gov_should_revert
        self.op_should_revert = op_should_revert
        self.calls = []

    async def get_agent_scope_root(self, agent_id_hex):
        self.calls.append(("get", agent_id_hex))
        return self.current_root

    async def set_agent_scope_root(self, agent_id_hex, root_hex):
        self.calls.append(("set_op", agent_id_hex, root_hex))
        if self.op_should_revert:
            raise RuntimeError("simulated operational tx revert")
        # Update current_root to simulate on-chain mutation
        s = root_hex.lower()
        if s.startswith("0x"): s = s[2:]
        self.current_root = bytes.fromhex(s)
        return {"tx_hash": "0xop_mock_tx", "block_number": 100, "status": 1}

    async def update_agent_scope_governance(self, agent_id_hex, root_hex):
        self.calls.append(("set_gov", agent_id_hex, root_hex))
        if self.gov_should_revert:
            raise RuntimeError("simulated governance tx revert")
        return {"tx_hash": "0xgov_mock_tx", "block_number": 101, "status": 1}


class _MockStore:
    """Mock Store recording activation log inserts."""
    def __init__(self):
        self.rows = []
    def insert_operator_agent_activation(self, **kwargs):
        self.rows.append(kwargs)
        return len(self.rows)


# ----------------------------------------------------------------------
# T-O1-AN-1 — happy path
# ----------------------------------------------------------------------
def test_t_o1_an_1_happy_path():
    with tempfile.TemporaryDirectory() as tmpdir:
        bp = _write_bundle(tmpdir)
        chain = _MockChain(current_root=b"\x00" * 32)
        store = _MockStore()
        anchor = CedarBundleAnchor(chain=chain, store=store, bundle_dir=tmpdir)
        result = asyncio.run(anchor.anchor_bundle(
            bundle_path="anchor_sentry.json",
            reason_text="Phase O1 minimum-viable activation",
            operator_api_key="vapi-dev-local",
        ))
        assert result.success is True
        assert result.agent_id == SENTRY_ID
        assert result.from_phase == "O0_DORMANT"
        assert result.to_phase == "O1_SHADOW"
        assert result.operational_tx_hash == "0xop_mock_tx"
        assert result.governance_tx_hash == "0xgov_mock_tx"
        assert result.activation_log_id == 1
        # Operational FIRST per INV-OPERATOR-AGENT-001
        assert chain.calls[0][0] == "get"
        assert chain.calls[1][0] == "set_op"
        assert chain.calls[2][0] == "set_gov"


# ----------------------------------------------------------------------
# T-O1-AN-2 — governance-tx-revert path
# ----------------------------------------------------------------------
def test_t_o1_an_2_governance_revert_records_both():
    with tempfile.TemporaryDirectory() as tmpdir:
        bp = _write_bundle(tmpdir)
        chain = _MockChain(gov_should_revert=True)
        store = _MockStore()
        anchor = CedarBundleAnchor(chain=chain, store=store, bundle_dir=tmpdir)
        result = asyncio.run(anchor.anchor_bundle(
            bundle_path="anchor_sentry.json",
            reason_text="Phase O1 minimum-viable activation",
            operator_api_key="vapi-dev-local",
        ))
        # Governance reverted but activation_log row was still written
        assert result.success is False
        assert result.error and "governance" in result.error.lower()
        assert result.operational_tx_hash == "0xop_mock_tx"
        assert result.governance_tx_hash == "reverted"
        assert result.activation_log_id == 1
        assert len(store.rows) == 1


# ----------------------------------------------------------------------
# T-O1-AN-3 — missing bundle file
# ----------------------------------------------------------------------
def test_t_o1_an_3_missing_bundle():
    with tempfile.TemporaryDirectory() as tmpdir:
        chain = _MockChain()
        store = _MockStore()
        anchor = CedarBundleAnchor(chain=chain, store=store, bundle_dir=tmpdir)
        with pytest.raises(CedarBundleAnchorError, match="bundle load/parse failed"):
            asyncio.run(anchor.anchor_bundle(
                bundle_path="nonexistent.json",
                reason_text="this is at least 10 characters long",
                operator_api_key="vapi-dev-local",
            ))


# ----------------------------------------------------------------------
# T-O1-AN-4 — no-op same-root
# ----------------------------------------------------------------------
def test_t_o1_an_4_noop_same_root():
    """When bundle Merkle root matches current scopeRoot, no chain calls fire."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bp = _write_bundle(tmpdir)
        # Pre-compute the bundle's expected root and prime the mock chain to return it
        from vapi_bridge.cedar_parser import bundle_merkle_root
        with open(bp) as f:
            preroot = bundle_merkle_root(json.load(f))
        chain = _MockChain(current_root=preroot)
        store = _MockStore()
        anchor = CedarBundleAnchor(chain=chain, store=store, bundle_dir=tmpdir)
        result = asyncio.run(anchor.anchor_bundle(
            bundle_path="anchor_sentry.json",
            reason_text="Phase O1 idempotent re-anchor smoke test",
            operator_api_key="vapi-dev-local",
        ))
        assert result.success is True
        assert result.activation_log_id is None  # no insert when no-op
        assert result.from_scope_root == result.to_scope_root
        # Only the get_agent_scope_root call happened
        set_calls = [c for c in chain.calls if c[0].startswith("set")]
        assert len(set_calls) == 0


# ----------------------------------------------------------------------
# T-O1-AN-5 — reason gate
# ----------------------------------------------------------------------
def test_t_o1_an_5_reason_too_short():
    """reason_text < 10 chars raises CedarBundleAnchorError before chain calls."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bp = _write_bundle(tmpdir)
        chain = _MockChain()
        store = _MockStore()
        anchor = CedarBundleAnchor(chain=chain, store=store, bundle_dir=tmpdir)
        with pytest.raises(CedarBundleAnchorError, match="≥10 chars"):
            asyncio.run(anchor.anchor_bundle(
                bundle_path="anchor_sentry.json",
                reason_text="short",
                operator_api_key="vapi-dev-local",
            ))


# ----------------------------------------------------------------------
# T-O1-AN-6 — _operator_authority_hash determinism + ts-sensitivity
# ----------------------------------------------------------------------
def test_t_o1_an_6_authority_hash_determinism():
    a = _operator_authority_hash("vapi-dev-local", "test reason 12345", 1777840000000000000)
    b = _operator_authority_hash("vapi-dev-local", "test reason 12345", 1777840000000000000)
    c = _operator_authority_hash("vapi-dev-local", "test reason 12345", 1777840000000000001)  # ts+1
    d = _operator_authority_hash("different-key",  "test reason 12345", 1777840000000000000)
    e = _operator_authority_hash("vapi-dev-local", "different reason XX", 1777840000000000000)
    assert a == b, "same inputs must yield same hash"
    assert a != c, "ts mutation must change hash"
    assert a != d, "key mutation must change hash"
    assert a != e, "reason mutation must change hash"
    assert a.startswith("0x") and len(a) == 66
