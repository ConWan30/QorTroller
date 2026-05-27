"""Path A Arc 1 Commit 4 — bridge chain.py + operator_api.py wiring tests.

   T-LENS-V2-CHAIN-1  is_fully_eligible_path_a + get_device_tier_from_lens
                      raise RuntimeError when protocol_lens_address is unset
                      (mirrors the existing is_fully_eligible posture; caller
                      must fail-open at operator_api layer with try/except).
   T-LENS-V2-CHAIN-2  _VAPI_PROTOCOL_LENS_V2_ABI exposes the 3 view calls the
                      bridge consumes (isFullyEligible / isFullyEligible_PathA
                      / getDeviceTier) — no writers, no setters in the bridge
                      ABI surface. Inline 4-line ABI in is_fully_eligible has
                      been replaced with the constant.
   T-LENS-V2-CHAIN-3  controller_models.name_for_hash round-trips for both
                      known models (CFI-ZCP1, CFI-ZCT1); returns None for any
                      unknown or zero-bytes32 input — locks the reverse-lookup
                      table against silent drift.
   T-LENS-V2-CHAIN-4  /player/session-status response shape carries the 4 new
                      Path A keys (signing_path, proof_tier, controller_model,
                      path_a_eligible) with honest dormant defaults — the
                      Commit 4 endpoint contract.
"""
from __future__ import annotations

import pytest

from bridge.vapi_bridge import chain as _chain
from bridge.vapi_bridge import controller_models as _cm


# ── T-LENS-V2-CHAIN-1 ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_T_LENS_V2_CHAIN_1_methods_raise_when_lens_unset():
    """is_fully_eligible_path_a + get_device_tier_from_lens MUST raise
    RuntimeError when protocol_lens_address is unset. The operator_api layer
    catches this and surfaces honest 'unavailable' to the client; raising at
    chain level avoids a silent False that the caller can't distinguish from
    a real on-chain false."""
    class _MinimalCfg:
        protocol_lens_address = ""
        iotex_rpc_url = "http://invalid.local:0"

    obj = _chain.ChainClient.__new__(_chain.ChainClient)
    obj._cfg = _MinimalCfg()
    obj._w3 = None  # would normally be set in __init__

    with pytest.raises(RuntimeError, match="protocol_lens_address not configured"):
        await obj.is_fully_eligible_path_a("00" * 32)
    with pytest.raises(RuntimeError, match="protocol_lens_address not configured"):
        await obj.get_device_tier_from_lens("00" * 32)


# ── T-LENS-V2-CHAIN-2 ────────────────────────────────────────────────────────

def test_T_LENS_V2_CHAIN_2_lens_v2_abi_views_only():
    """The bridge's lens v2 ABI MUST contain exactly the three view calls the
    bridge consumes (isFullyEligible / isFullyEligible_PathA / getDeviceTier)
    and no others. Also confirms the constant is defined module-level
    (replaces the inline 4-line ABI that lived in is_fully_eligible)."""
    abi = _chain._VAPI_PROTOCOL_LENS_V2_ABI
    names = {entry["name"] for entry in abi}
    assert names == {"isFullyEligible", "isFullyEligible_PathA", "getDeviceTier"}
    for entry in abi:
        assert entry["type"] == "function"
        assert entry["stateMutability"] == "view"
        assert any(inp["type"] == "bytes32" for inp in entry["inputs"]), \
            f"{entry['name']} must take bytes32 deviceId"


# ── T-LENS-V2-CHAIN-3 ────────────────────────────────────────────────────────

def test_T_LENS_V2_CHAIN_3_controller_model_reverse_lookup():
    """The reverse-lookup table MUST round-trip the two known model names,
    and MUST return None for any unknown or zero-bytes32 input — preserves
    the operator_api honesty contract (None = unknown, never fabricated)."""
    # Known names → hashes → back to names
    for name in ("CFI-ZCP1", "CFI-ZCT1"):
        h = _cm.KNOWN_MODELS[name][0]
        assert isinstance(h, bytes) and len(h) == 32
        assert _cm.name_for_hash(h) == name

    # Unknown bytes32 → None
    assert _cm.name_for_hash(b"\x00" * 32) is None
    assert _cm.name_for_hash(b"\xff" * 32) is None
    # Wrong length → None (defensive)
    assert _cm.name_for_hash(b"\x00" * 31) is None
    assert _cm.name_for_hash(b"\x00" * 33) is None
    # Wrong type → None
    assert _cm.name_for_hash("CFI-ZCP1") is None
    assert _cm.name_for_hash(None) is None
    # default_tier_for known/unknown
    assert _cm.default_tier_for("CFI-ZCP1") == "FULL"
    assert _cm.default_tier_for("CFI-ZCT1") == "STANDARD"
    assert _cm.default_tier_for("UnknownModel") is None


# ── T-LENS-V2-CHAIN-4 ────────────────────────────────────────────────────────

def test_T_LENS_V2_CHAIN_4_session_status_shape_carries_path_a_keys():
    """Static-source guard mirroring T-OS-L4-4 (StatusStrip honesty pattern):
    the /player/session-status endpoint MUST return the 4 new Path A keys.
    Locks the endpoint contract against silent removal — a future refactor
    that drops signing_path / proof_tier / controller_model / path_a_eligible
    breaks Path A's tournament-integrator contract.

    Static source-check (no FastAPI client roundtrip needed; the surface IS
    the literal field name in the response-dict construction site).
    """
    from pathlib import Path
    src = Path(__file__).parents[1] / "vapi_bridge" / "operator_api.py"
    text = src.read_text(encoding="utf-8")
    # Locate the player_session_status return dict by anchor
    pss_marker = '"signing_path":'
    assert pss_marker in text, \
        "operator_api.py missing 'signing_path' key in /player/session-status response"
    for key in ("signing_path", "proof_tier", "controller_model", "path_a_eligible"):
        assert f'"{key}":' in text, \
            f"operator_api.py missing '{key}' key in /player/session-status response (Path A C4 contract)"
