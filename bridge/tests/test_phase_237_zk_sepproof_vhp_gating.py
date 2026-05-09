"""Phase 237-ZK-SEPPROOF Step G tests — VHP gating two-tier behaviour.

Tests the mint-vhp endpoint's sepproof gate:
  - vhp_sepproof_required=False (default): commitment optional; if supplied,
    must be anchored.
  - vhp_sepproof_required=True (opt-in tournament-grade): commitment required;
    mint rejects with 422 if missing or unanchored.

Tests use static source-code checks for the gate's structural correctness
(static analysis is sufficient for the gate's structure: the key behaviours
are conditional 422 raises and response field additions, both verifiable
by reading the source).  Full integration testing of mint-vhp is covered by
the existing Phase 99C test suite which we don't disturb.

T-237-SEP-VHP-1..6.
"""
from __future__ import annotations

import sys
import types as _types
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BRIDGE_DIR = Path(__file__).parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

# Stub heavy-import modules
for _mod in ["web3", "web3.exceptions", "eth_account", "anthropic"]:
    if _mod not in sys.modules:
        sys.modules[_mod] = _types.ModuleType(_mod)
if "dotenv" not in sys.modules:
    _dotenv = _types.ModuleType("dotenv")
    _dotenv.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    sys.modules["dotenv"] = _dotenv


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-VHP-1: config field exists with default False (backward compat)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_vhp_1_config_field_default_false(monkeypatch):
    monkeypatch.delenv("VHP_SEPPROOF_REQUIRED", raising=False)
    from vapi_bridge.config import Config
    cfg = Config()
    assert cfg.vhp_sepproof_required is False, (
        "Default must be False — backward compat with existing VHP mint flows"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-VHP-2: env override toggles to True (tournament-grade opt-in)
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_vhp_2_env_override(monkeypatch):
    monkeypatch.setenv("VHP_SEPPROOF_REQUIRED", "true")
    import importlib
    from vapi_bridge import config as _cfg_mod
    importlib.reload(_cfg_mod)
    cfg = _cfg_mod.Config()
    assert cfg.vhp_sepproof_required is True


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-VHP-3: mint-vhp endpoint accepts sepproof_commitment query param
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_vhp_3_endpoint_signature():
    """Static check: the mint_vhp endpoint signature includes sepproof_commitment
    Query param. Without this, the gate logic would never receive a commitment
    value to validate."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "operator_api.py").read_text(
        encoding="utf-8"
    )
    # Find the mint_vhp signature
    mint_idx = src.find("async def mint_vhp(")
    assert mint_idx != -1
    body_start = src.find("):", mint_idx)
    sig_block = src[mint_idx:body_start]
    assert "sepproof_commitment" in sig_block, (
        "mint_vhp signature must include sepproof_commitment query param "
        "for Phase 237-ZK-SEPPROOF Step G binding"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-VHP-4: gate logic structural shape — required + supplied + anchored
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_vhp_4_gate_structural_shape():
    """Static check on the gate's required code paths. The implementation
    must contain:
      - vhp_sepproof_required config flag read
      - on_chain_confirmed check on biometric_snapshot_log row
      - 422 raise when required + missing
      - 422 raise when supplied + not in biometric_snapshot_log
      - 422 raise when supplied + on_chain_confirmed=false
    """
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "operator_api.py").read_text(
        encoding="utf-8"
    )
    mint_idx = src.find("async def mint_vhp(")
    # Bound search to the mint_vhp body — find the next `async def` or `@app.`
    next_def = src.find("\n    @app.", mint_idx + 1)
    if next_def == -1:
        next_def = src.find("\n    async def ", mint_idx + 1)
    body = src[mint_idx:next_def] if next_def != -1 else src[mint_idx:]

    assert "vhp_sepproof_required" in body, "config flag read missing"
    assert "biometric_snapshot_log" in body, "snapshot table query missing"
    assert "on_chain_confirmed" in body, "on-chain confirmation check missing"
    # 422 paths — three distinct error messages
    assert "sepproof_commitment not found" in body, (
        "missing 'not found' 422 path for unknown commitment"
    )
    assert "not anchored on-chain" in body, (
        "missing 'not anchored' 422 path for on_chain_confirmed=false"
    )
    assert "sepproof_commitment query " in body, (
        "missing 'required tier' 422 path when commitment not supplied"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-VHP-5: response includes sepproof binding fields
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_vhp_5_response_metadata():
    """Static check: mint_vhp response dict includes the four sepproof
    binding fields so callers can audit which VHPs are SEPPROOF-attested."""
    src = (PROJECT_ROOT / "bridge" / "vapi_bridge" / "operator_api.py").read_text(
        encoding="utf-8"
    )
    mint_idx = src.find("async def mint_vhp(")
    next_def = src.find("\n    @app.", mint_idx + 1)
    body = src[mint_idx:next_def] if next_def != -1 else src[mint_idx:]

    for field in (
        '"sepproof_commitment":',
        '"sepproof_anchored":',
        '"sepproof_row_id":',
        '"sepproof_required":',
    ):
        assert field in body, (
            f"mint_vhp response must include {field} for Step G audit trail"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T-237-SEP-VHP-6: behavioral — gate logic in dry-run against in-memory store
# ─────────────────────────────────────────────────────────────────────────────

def test_t_237_sep_vhp_6_anchored_check_against_store():
    """Behavioural smoke: insert a biometric snapshot row with
    on_chain_confirmed=true, then verify the store query the gate uses
    returns the expected on_chain_confirmed value.  Tests the store-level
    contract the gate depends on."""
    import tempfile, os
    from vapi_bridge.store import Store

    db_path = os.path.join(tempfile.mkdtemp(), "sep_vhp_test.db")
    store = Store(db_path)

    # Insert anchored snapshot
    confirmed_commit = "ab" * 32
    store.insert_biometric_snapshot(
        snapshot_commitment=confirmed_commit,
        feature_dim=4,
        sorted_player_ids=[0, 1, 2],
        centroids_by_player={0: [1.0]*4, 1: [2.0]*4, 2: [3.0]*4},
        cov_inv=[[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]],
        ts_ns=1_778_316_000_000_000_000,
        on_chain_confirmed=True,
        tx_hash="0x" + "cd" * 32,
        trigger_reason="test_anchored_path",
    )
    # Insert unanchored snapshot
    unanchored_commit = "ef" * 32
    store.insert_biometric_snapshot(
        snapshot_commitment=unanchored_commit,
        feature_dim=4,
        sorted_player_ids=[0, 1, 2],
        centroids_by_player={0: [1.0]*4, 1: [2.0]*4, 2: [3.0]*4},
        cov_inv=[[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0], [0, 0, 0, 1.0]],
        ts_ns=1_778_316_500_000_000_000,
        on_chain_confirmed=False,
        tx_hash="",
        trigger_reason="test_unanchored_path",
    )

    # The gate's exact query — must match what's in mint_vhp body
    with store._conn() as conn:
        anchored_row = conn.execute(
            "SELECT id, on_chain_confirmed FROM biometric_snapshot_log "
            "WHERE snapshot_commitment = ? LIMIT 1",
            (confirmed_commit,),
        ).fetchone()
        unanchored_row = conn.execute(
            "SELECT id, on_chain_confirmed FROM biometric_snapshot_log "
            "WHERE snapshot_commitment = ? LIMIT 1",
            (unanchored_commit,),
        ).fetchone()
        missing_row = conn.execute(
            "SELECT id, on_chain_confirmed FROM biometric_snapshot_log "
            "WHERE snapshot_commitment = ? LIMIT 1",
            ("00" * 32,),
        ).fetchone()

    assert anchored_row is not None
    assert bool(anchored_row["on_chain_confirmed"]) is True

    assert unanchored_row is not None
    assert bool(unanchored_row["on_chain_confirmed"]) is False

    assert missing_row is None
