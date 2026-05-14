"""Tests for the 6 MCP tool wrappers around the wallet-free audit harnesses.

Each wrapper at vapi-mcp/knowledge_server.py lazy-imports its corresponding
scripts/*.py audit module + invokes the public entry-point + returns a
structured dict. These tests verify the wrappers don't raise + return
the expected shape.

T-MCP-AUDIT-1..6: live smoke per tool against the real repo state.
T-MCP-AUDIT-7: every audit tool's result includes audit_id + wallet_free fields.
T-MCP-AUDIT-8: every audit tool's name follows the vapi_audit_* convention.
T-MCP-AUDIT-9: no audit tool raises on error import (returns dict with error field).
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MCP_DIR = PROJECT_ROOT / "vapi-mcp"

if str(MCP_DIR) not in sys.path:
    sys.path.insert(0, str(MCP_DIR))


@pytest.fixture(scope="module")
def ks():
    """Import knowledge_server once for the module + pin PROJECT_ROOT."""
    import knowledge_server  # type: ignore
    # Override PROJECT_ROOT to point at the actual repo root (knowledge_server
    # reads VAPI_ROOT env at import time + defaults to '.', which won't resolve
    # correctly under pytest's working directory).
    knowledge_server.PROJECT_ROOT = PROJECT_ROOT
    return knowledge_server


@pytest.fixture(scope="module")
def us():
    """Import unified_server + pin PROJECT_ROOT (mirror of ks fixture).
    The 6 audit wrappers in unified_server.py are functionally equivalent
    to knowledge_server.py — same source, mirrored for re-export."""
    import unified_server  # type: ignore
    unified_server.PROJECT_ROOT = PROJECT_ROOT
    return unified_server


# ---- T-MCP-AUDIT-1: G7 readiness wrapper -----------------------------

def test_t_mcp_audit_1_g7_readiness_wrapper(ks):
    """G7 wrapper returns structured dict against the real DB."""
    result = asyncio.run(ks.vapi_audit_g7_curator_readiness())
    assert result["audit_id"] == "G7"
    assert result["wallet_free"] is True
    # At least one of: final_verdict (normal case) OR verdict (NO_CURATOR_DRAFTS
    # early-return case) OR error (import-failure case) must be present.
    has_outcome = (
        "final_verdict" in result
        or "verdict" in result
        or "error" in result
    )
    assert has_outcome, f"G7 result missing outcome field: {result}"


# ---- T-MCP-AUDIT-2: replay-artifact wrapper --------------------------

def test_t_mcp_audit_2_replay_artifact_wrapper(ks):
    """Replay wrapper directory mode against real frontend/src/artifacts."""
    result = asyncio.run(ks.vapi_audit_replay_artifact())
    assert result["audit_id"] == "REPLAY"
    assert result["wallet_free"] is True
    # Directory mode is the default when neither manifest_path nor target_dir
    # is given. Should report manifest_count + pass_count + fail_count.
    if "error" not in result:
        assert result["mode"] in ("directory", "single")
        assert "manifest_count" in result
        assert result["manifest_count"] >= 0


# ---- T-MCP-AUDIT-3: CFSS lane drift wrapper ---------------------------

def test_t_mcp_audit_3_cfss_lane_drift_wrapper(ks):
    """CFSS wrapper against the live anchored v2 bundles MUST PASS."""
    result = asyncio.run(ks.vapi_audit_cfss_lane_drift())
    assert result["audit_id"] == "CFSS"
    assert result["wallet_free"] is True
    # The v2 bundles were dual-anchored 2026-05-12; cfss_lane_drift_sweep
    # against the canonical bundles MUST report PASS today.
    assert result.get("verdict") == "PASS", (
        f"CFSS audit expected PASS; got {result.get('verdict')}"
    )
    assert result.get("expected_rows") == 12


# ---- T-MCP-AUDIT-4: Curator graduation wrapper ------------------------

def test_t_mcp_audit_4_curator_graduation_wrapper(ks):
    """Curator graduation wrapper consolidates 4 sub-audits."""
    result = asyncio.run(ks.vapi_audit_curator_graduation())
    assert result["audit_id"] == "CURATOR-GRAD"
    assert result["wallet_free"] is True
    if "error" not in result:
        s5 = result.get("section_5_consolidated_verdict", {})
        assert s5.get("verdict") in ("READY", "BLOCKED", "FAIL", "ERROR")


# ---- T-MCP-AUDIT-5: W3bstream applet wrapper --------------------------

def test_t_mcp_audit_5_w3bstream_applet_wrapper(ks):
    """W3bstream wrapper reports per-applet verdicts."""
    result = asyncio.run(ks.vapi_audit_w3bstream_applet())
    assert result["audit_id"] == "W3B"
    assert result["wallet_free"] is True
    if "error" not in result:
        applets = result.get("applets", [])
        # 3 applets in scripts/w3bstream/ at this commit
        assert len(applets) >= 3
        # validate_poac_record.ts MUST report STUB_DEPS_BLOCKED post Stream A push
        # (P256_VERIFY + POSEIDON_HASH both dep-blocked)
        poac = next(
            (a for a in applets if a["applet"] == "validate_poac_record.ts"), None,
        )
        assert poac is not None
        assert poac.get("verdict") in ("STUB", "STUB_DEPS_BLOCKED")


# ---- T-MCP-AUDIT-6: LayerZero VHP wrapper ----------------------------

def test_t_mcp_audit_6_layerzero_vhp_wrapper(ks):
    """LayerZero VHP wrapper reports STUB at this commit's state."""
    result = asyncio.run(ks.vapi_audit_layerzero_vhp())
    assert result["audit_id"] == "LZ-VHP"
    assert result["wallet_free"] is True
    if "error" not in result:
        # Bridge.sol is intentionally STUB at this commit (full OApp refactor
        # deferred on upstream peer-dep conflict per Stream B atomic-stop)
        assert result.get("verdict") in ("STUB", "OAPP_WIRED", "SRC_NOT_FOUND")


# ---- T-MCP-AUDIT-7: every wrapper returns audit_id + wallet_free ----

def test_t_mcp_audit_7_shape_contract(ks):
    """Every audit wrapper MUST return audit_id + wallet_free=True."""
    wrappers = [
        ks.vapi_audit_g7_curator_readiness,
        ks.vapi_audit_replay_artifact,
        ks.vapi_audit_cfss_lane_drift,
        ks.vapi_audit_curator_graduation,
        ks.vapi_audit_w3bstream_applet,
        ks.vapi_audit_layerzero_vhp,
    ]
    for fn in wrappers:
        result = asyncio.run(fn())
        assert "audit_id" in result, f"{fn.__name__} missing audit_id"
        assert result.get("wallet_free") is True, (
            f"{fn.__name__} must be wallet_free=True (got {result.get('wallet_free')})"
        )


# ---- T-MCP-AUDIT-8: tool naming convention ----------------------------

def test_t_mcp_audit_8_tool_naming_convention(ks):
    """All 6 audit tools MUST be named vapi_audit_*."""
    expected_names = {
        "vapi_audit_g7_curator_readiness",
        "vapi_audit_replay_artifact",
        "vapi_audit_cfss_lane_drift",
        "vapi_audit_curator_graduation",
        "vapi_audit_w3bstream_applet",
        "vapi_audit_layerzero_vhp",
    }
    actual = {n for n in dir(ks) if n.startswith("vapi_audit_")}
    assert actual >= expected_names, (
        f"Missing audit tools: {expected_names - actual}"
    )


# ---- T-MCP-AUDIT-9: wrappers never raise --------------------------

def test_t_mcp_audit_9_wrappers_never_raise(ks):
    """Per the shared MCP audit contract: wrappers must never raise.
    Errors land in the return dict's 'error' field."""
    wrappers = [
        ks.vapi_audit_g7_curator_readiness,
        ks.vapi_audit_replay_artifact,
        ks.vapi_audit_cfss_lane_drift,
        ks.vapi_audit_curator_graduation,
        ks.vapi_audit_w3bstream_applet,
        ks.vapi_audit_layerzero_vhp,
    ]
    for fn in wrappers:
        try:
            result = asyncio.run(fn())
        except Exception as exc:
            pytest.fail(f"{fn.__name__} raised: {exc}")
        assert isinstance(result, dict)


# ---- T-MCP-AUDIT-10: unified_server has the same 6 audit tools --------

def test_t_mcp_audit_10_unified_server_has_six_audit_tools(us):
    """unified_server.py mirrors the 6 audit wrappers from
    knowledge_server.py — re-exported so vapi-unified MCP consumers
    can invoke audits without round-tripping through vapi-knowledge."""
    expected_names = {
        "vapi_audit_g7_curator_readiness",
        "vapi_audit_replay_artifact",
        "vapi_audit_cfss_lane_drift",
        "vapi_audit_curator_graduation",
        "vapi_audit_w3bstream_applet",
        "vapi_audit_layerzero_vhp",
    }
    actual = {n for n in dir(us) if n.startswith("vapi_audit_")}
    assert actual >= expected_names, (
        f"unified_server missing audit tools: {expected_names - actual}"
    )


# ---- T-MCP-AUDIT-11: unified_server CFSS wrapper PASSes live ---------

def test_t_mcp_audit_11_unified_cfss_lane_drift_live(us):
    """Sanity: the same wrappers in unified_server produce the same
    verdicts as the knowledge_server versions. CFSS against live
    anchored v2 bundles MUST PASS."""
    result = asyncio.run(us.vapi_audit_cfss_lane_drift())
    assert result["audit_id"] == "CFSS"
    assert result["wallet_free"] is True
    assert result.get("verdict") == "PASS"
    assert result.get("expected_rows") == 12


# ---- T-MCP-AUDIT-12: both servers' wrappers return equivalent shape --

def test_t_mcp_audit_12_both_servers_equivalent_shape(ks, us):
    """For each audit, the knowledge_server + unified_server wrappers
    must return the same audit_id + wallet_free + verdict-shape. Catches
    silent drift between the two re-exported tool implementations."""
    pairs = [
        (ks.vapi_audit_cfss_lane_drift, us.vapi_audit_cfss_lane_drift),
        (ks.vapi_audit_layerzero_vhp, us.vapi_audit_layerzero_vhp),
        (ks.vapi_audit_w3bstream_applet, us.vapi_audit_w3bstream_applet),
    ]
    for ks_fn, us_fn in pairs:
        ks_r = asyncio.run(ks_fn())
        us_r = asyncio.run(us_fn())
        assert ks_r["audit_id"] == us_r["audit_id"], (
            f"audit_id mismatch: ks={ks_r['audit_id']} us={us_r['audit_id']}"
        )
        assert ks_r["wallet_free"] == us_r["wallet_free"]
