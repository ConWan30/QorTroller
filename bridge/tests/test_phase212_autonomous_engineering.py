"""
Phase 212 — Autonomous Engineering Layer Tests
T212-1..8

Tests for the 5 new tools in vapi-mcp/unified_server.py (Tools 13-17):
  T212-1: vapi_skill_state_sync — drift_detected=False when phase matches CLAUDE.md
  T212-2: vapi_skill_state_sync — drift_detected=True when stale phase supplied
  T212-3: vapi_phase_advance_proposal — returns valid proposal with autoresearch_pre_score
  T212-4: vapi_code_change_impact — endpoint pattern: +8 bridge +4 SDK
  T212-5: vapi_code_change_impact — CRITICAL risk on PoAC/wire_format keyword
  T212-6: vapi_engineering_decision — returns verdict + implementation_steps
  T212-7: vapi_autonomous_gap_scan — ranked_gaps non-empty, G-001 is first (CRITICAL lowest effort)
  T212-8: vapi_autonomous_gap_scan — hardware_ok=False excludes hardware gaps
"""
import os
import sys
import tempfile
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

# ── stub web3 / eth_account before any import ────────────────────────────────
for _mod in ("web3", "web3.exceptions", "eth_account", "eth_account.messages",
             "web3.middleware", "web3.gas_strategies", "web3.gas_strategies.time_based"):
    if _mod not in sys.modules:
        sys.modules[_mod] = types.ModuleType(_mod)

_fake_web3 = sys.modules["web3"]
if not hasattr(_fake_web3, "Web3"):
    class _W3Stub:
        HTTPProvider = lambda *a, **kw: None
        class middleware_onion:
            inject = lambda *a, **kw: None
    _fake_web3.Web3 = _W3Stub

_fake_exc = sys.modules["web3.exceptions"]
if not hasattr(_fake_exc, "ContractLogicError"):
    _fake_exc.ContractLogicError = type("ContractLogicError", (Exception,), {})


# ── import helper ─────────────────────────────────────────────────────────────

def _import_unified():
    """Import unified_server with VAPI_ROOT patched to a temp dir."""
    unified_path = ROOT / "vapi-mcp"
    if str(unified_path) not in sys.path:
        sys.path.insert(0, str(unified_path))
    tmpdir = tempfile.mkdtemp()
    os.environ.setdefault("VAPI_ROOT", tmpdir)
    import importlib
    if "unified_server" in sys.modules:
        return sys.modules["unified_server"]
    import unified_server as mod
    return mod


# ─────────────────────────────────────────────────────────────────────────────
# T212-1: vapi_skill_state_sync — no drift when current phase matches live
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_1_skill_state_sync_no_drift():
    """vapi_skill_state_sync returns drift_detected=False when phase matches CLAUDE.md."""
    import asyncio
    mod = _import_unified()

    # Patch _parse_claude_md to return known state
    orig = mod._parse_claude_md
    mod._CLAUDE_CACHE_U["state"] = {
        "phase_num": "212", "bridge": "2276", "sdk": "452", "hardhat": "482",
        "agents": "36", "contracts": "43", "l4_anomaly": "7.009",
        "l4_continuity": "5.367", "separation_ratio": "1.177",
    }
    mod._CLAUDE_CACHE_U["mtime"] = 1e15  # far future — cache never expires

    try:
        result = asyncio.run(mod.vapi_skill_state_sync(
            current_skill_phase=212, current_skill_bridge=2276
        ))
    finally:
        mod._CLAUDE_CACHE_U["mtime"] = 0.0
        mod._CLAUDE_CACHE_U["state"] = {}

    assert result["drift_detected"] is False
    assert result["drift_items"] == []
    assert result["lag_phases"] == 0
    assert "wif_040_status" in result
    assert "STRUCTURALLY_CLOSED" in result["wif_040_status"]
    assert "sync_block" in result
    assert "NOT authoritative" in result["sync_block"]


# ─────────────────────────────────────────────────────────────────────────────
# T212-2: vapi_skill_state_sync — drift detected when stale phase supplied
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_2_skill_state_sync_drift_detected():
    """vapi_skill_state_sync returns drift_detected=True with correct lag when stale phase given."""
    import asyncio
    mod = _import_unified()

    mod._CLAUDE_CACHE_U["state"] = {
        "phase_num": "212", "bridge": "2276", "sdk": "452", "hardhat": "482",
        "agents": "36", "contracts": "43", "l4_anomaly": "7.009",
        "l4_continuity": "5.367", "separation_ratio": "1.177",
    }
    mod._CLAUDE_CACHE_U["mtime"] = 1e15

    try:
        result = asyncio.run(mod.vapi_skill_state_sync(
            current_skill_phase=156, current_skill_bridge=1868
        ))
    finally:
        mod._CLAUDE_CACHE_U["mtime"] = 0.0
        mod._CLAUDE_CACHE_U["state"] = {}

    assert result["drift_detected"] is True
    assert result["lag_phases"] == 56   # 212 - 156 = 56
    assert len(result["drift_items"]) >= 2  # phase + bridge both stale
    # sync_block contains live values
    assert "212" in result["sync_block"]
    assert "canonical_values" in result
    assert result["canonical_values"]["phase"] == 212


# ─────────────────────────────────────────────────────────────────────────────
# T212-3: vapi_phase_advance_proposal — returns valid structured proposal
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_3_phase_advance_proposal_structure():
    """vapi_phase_advance_proposal returns all expected keys with valid autoresearch_pre_score."""
    import asyncio
    mod = _import_unified()

    mod._CLAUDE_CACHE_U["state"] = {
        "phase_num": "211", "bridge": "2268", "sdk": "452", "hardhat": "482",
        "agents": "36", "contracts": "43",
    }
    mod._CLAUDE_CACHE_U["mtime"] = 1e15

    try:
        result = asyncio.run(mod.vapi_phase_advance_proposal(
            focus_area="separation_ratio", next_phase_number=212
        ))
    finally:
        mod._CLAUDE_CACHE_U["mtime"] = 0.0
        mod._CLAUDE_CACHE_U["state"] = {}

    assert result["proposed_phase"] == 212
    assert isinstance(result["proposed_phase_name"], str)
    assert len(result["proposed_phase_name"]) > 5
    assert result["focus_area"] == "separation_ratio"
    assert "rationale" in result
    assert "test_delta" in result
    assert "bridge" in result["test_delta"]
    assert "autoresearch_pre_score" in result
    pre = result["autoresearch_pre_score"]
    assert "score" in pre
    assert isinstance(pre["score"], float)
    assert 0.0 <= pre["score"] <= 1.0
    assert "invariants_preserved" in result
    assert "TOURNAMENT BLOCKER" in result["invariants_preserved"]


# ─────────────────────────────────────────────────────────────────────────────
# T212-4: vapi_code_change_impact — endpoint pattern gives +8 bridge +4 SDK
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_4_code_change_impact_endpoint_pattern():
    """vapi_code_change_impact predicts +8 bridge +4 SDK for new HTTP endpoint."""
    import asyncio
    mod = _import_unified()

    mod._CLAUDE_CACHE_U["state"] = {
        "phase_num": "212", "bridge": "2276", "sdk": "456", "hardhat": "482",
    }
    mod._CLAUDE_CACHE_U["mtime"] = 1e15

    try:
        result = asyncio.run(mod.vapi_code_change_impact(
            files_to_touch=["bridge/vapi_bridge/main.py", "bridge/vapi_bridge/store.py"],
            change_description="Add mainnet readiness gate endpoint and store table",
            adds_endpoint=True,
            adds_contract=False,
            adds_sdk_class=False,
            adds_mcp_tool=False,
        ))
    finally:
        mod._CLAUDE_CACHE_U["mtime"] = 0.0
        mod._CLAUDE_CACHE_U["state"] = {}

    assert result["test_delta"]["bridge"] == 8
    assert result["test_delta"]["sdk"] == 4
    assert result["test_delta"]["hardhat"] == 0
    assert result["test_counts_after"]["bridge"] == 2276 + 8
    assert result["whitepaper_update_required"] is True
    assert "§8.5" in result["whitepaper_sections"][0]


# ─────────────────────────────────────────────────────────────────────────────
# T212-5: vapi_code_change_impact — CRITICAL risk on PoAC keyword
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_5_code_change_impact_critical_risk():
    """vapi_code_change_impact flags CRITICAL risk when change touches PoAC wire format."""
    import asyncio
    mod = _import_unified()

    result = asyncio.run(mod.vapi_code_change_impact(
        files_to_touch=["bridge/vapi_bridge/poac_parser.py"],
        change_description="Modify PoAC wire format to add a 4-byte checksum field",
        adds_endpoint=False,
        adds_contract=False,
    ))

    assert result["risk_level"] == "CRITICAL"
    assert result["risk_score"] >= 0.40
    assert len(result["critical_risks"]) >= 1
    assert "CRITICAL" in result["critical_risks"][0]
    assert "STOP" in result["recommendation"]


# ─────────────────────────────────────────────────────────────────────────────
# T212-6: vapi_engineering_decision — returns verdict and implementation steps
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_6_engineering_decision_structure():
    """vapi_engineering_decision returns verdict, steps, and autoresearch pre-score."""
    import asyncio
    mod = _import_unified()

    result = asyncio.run(mod.vapi_engineering_decision(
        wif_id_or_description="WIF-040 skill manifest temporal drift structural fix",
        effort_budget_hours=4,
    ))

    assert "verdict" in result
    assert result["verdict"] in ("proceed", "defer", "BLOCK")
    assert "verdict_reason" in result
    assert "implementation_steps" in result
    assert isinstance(result["implementation_steps"], list)
    assert len(result["implementation_steps"]) >= 5
    assert "autoresearch_pre_score" in result
    pre = result["autoresearch_pre_score"]
    assert "score" in pre
    assert isinstance(pre["score"], float)
    # separation_ratio_impact is always present
    assert result["separation_ratio_impact"] in ("DIRECT", "INDIRECT")


# ─────────────────────────────────────────────────────────────────────────────
# T212-7: vapi_autonomous_gap_scan — ranked_gaps non-empty, G-001 first
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_7_autonomous_gap_scan_ranking():
    """vapi_autonomous_gap_scan returns ranked_gaps with G-001 (CRITICAL, 2h) first."""
    import asyncio
    mod = _import_unified()

    mod._CLAUDE_CACHE_U["state"] = {
        "phase_num": "212", "bridge": "2276", "sdk": "456", "hardhat": "482",
    }
    mod._CLAUDE_CACHE_U["mtime"] = 1e15

    try:
        result = asyncio.run(mod.vapi_autonomous_gap_scan(
            max_gaps=8, hardware_ok=False
        ))
    finally:
        mod._CLAUDE_CACHE_U["mtime"] = 0.0
        mod._CLAUDE_CACHE_U["state"] = {}

    assert "ranked_gaps" in result
    assert len(result["ranked_gaps"]) >= 1

    top = result["ranked_gaps"][0]
    assert top["severity"] == "CRITICAL"
    assert top["hardware"] is False
    assert top["id"] == "G-001"

    assert "separation_path_analysis" in result
    assert "autonomous_action_recommendation" in result
    rec = result["autonomous_action_recommendation"]
    assert "recommended_action" in rec
    assert "invariants_always_preserved" in result
    assert "TOURNAMENT BLOCKER" in result["invariants_always_preserved"]


# ─────────────────────────────────────────────────────────────────────────────
# T212-8: vapi_autonomous_gap_scan — hardware_ok=False excludes hardware gaps
# ─────────────────────────────────────────────────────────────────────────────

def test_t212_8_autonomous_gap_scan_hardware_filter():
    """vapi_autonomous_gap_scan with hardware_ok=False excludes all hardware-required gaps."""
    import asyncio
    mod = _import_unified()

    result = asyncio.run(mod.vapi_autonomous_gap_scan(
        max_gaps=10, hardware_ok=False
    ))

    for gap in result["ranked_gaps"]:
        assert gap["hardware"] is False, (
            f"Gap {gap['id']} requires hardware but was returned with hardware_ok=False"
        )

    # With hardware_ok=True, should return more gaps
    result_hw = asyncio.run(mod.vapi_autonomous_gap_scan(
        max_gaps=10, hardware_ok=True
    ))
    assert result_hw["total_gaps_found"] >= result["total_gaps_found"]
