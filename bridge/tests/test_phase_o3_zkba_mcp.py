"""Phase O3-ZKBA-TRACK1 C4 — MCP tool tests (Stream Z5).

T-ZKBA-12: vapi_zkba_status tool registered in TOOLS dict; schema shape
T-ZKBA-13: vapi_compile_zkba_artifact returns CLI command for GIC class +
           NO_BUILDER_SHIPPED stub for other classes
"""
import asyncio
import json
import os
import sys

import pytest


# Add vapi-mcp/ to sys.path so we can import knowledge_server
_HERE = os.path.dirname(__file__)
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_MCP_DIR = os.path.normpath(os.path.join(_REPO, "vapi-mcp"))
if _MCP_DIR not in sys.path:
    sys.path.insert(0, _MCP_DIR)


def _import_knowledge_server():
    """Import the knowledge_server module on demand. Side effects (KG load)
    are accepted; tests don't depend on KG state."""
    import importlib
    import knowledge_server  # type: ignore
    importlib.reload(knowledge_server)
    return knowledge_server


# ---------------------------------------------------------------------------
# T-ZKBA-12: vapi_zkba_status tool registration + schema
# ---------------------------------------------------------------------------

def test_t_zkba_12_mcp_vapi_zkba_status_tool():
    """Verify vapi_zkba_status is registered in TOOLS dict with the expected
    schema shape (no params; required=[])."""
    ks = _import_knowledge_server()
    assert "vapi_zkba_status" in ks.TOOLS, (
        f"vapi_zkba_status missing from TOOLS dict; "
        f"present tools: {sorted(ks.TOOLS.keys())[:20]}..."
    )
    tool = ks.TOOLS["vapi_zkba_status"]
    assert "description" in tool
    assert "schema" in tool
    assert "fn" in tool
    # Schema: no required params
    schema = tool["schema"]
    assert schema.get("type") == "object"
    assert schema.get("required", []) == []
    # Description mentions key concepts
    desc = tool["description"]
    assert "ZKBA" in desc or "zkba" in desc
    assert "zkba_artifact_log" in desc

    # Also verify vapi_compile_zkba_artifact + vapi_zkba_projection_manifest
    # are registered
    assert "vapi_compile_zkba_artifact" in ks.TOOLS
    assert "vapi_zkba_projection_manifest" in ks.TOOLS

    # vapi_compile_zkba_artifact schema: required=["zkba_class"]; enum 7 classes
    compile_schema = ks.TOOLS["vapi_compile_zkba_artifact"]["schema"]
    assert compile_schema.get("required", []) == ["zkba_class"]
    zkba_class_enum = compile_schema["properties"]["zkba_class"]["enum"]
    assert set(zkba_class_enum) == {
        "AIT", "GIC", "VHP", "HARDWARE", "CONSENT", "TOURNAMENT", "MARKET"
    }

    # vapi_zkba_projection_manifest schema: required=["commitment_hex"]
    manifest_schema = ks.TOOLS["vapi_zkba_projection_manifest"]["schema"]
    assert manifest_schema.get("required", []) == ["commitment_hex"]


# ---------------------------------------------------------------------------
# T-ZKBA-13: vapi_compile_zkba_artifact returns CLI command + stub for non-GIC
# ---------------------------------------------------------------------------

def test_t_zkba_13_mcp_vapi_compile_zkba_artifact_returns_command():
    """Verify the tool returns a CLI command (does NOT execute) for GIC,
    and a NO BUILDER SHIPPED stub for other classes."""
    ks = _import_knowledge_server()
    fn = ks.TOOLS["vapi_compile_zkba_artifact"]["fn"]

    # GIC class -> returns CLI command + builder metadata
    result_gic = asyncio.run(fn(zkba_class="GIC", grind_session_id="grind_test", ts_ns=1778000000000000000))
    assert result_gic["zkba_class"] == "GIC"
    assert "command_to_run" in result_gic
    assert "scripts/zkba_compile_gic_ledger.py" in result_gic["command_to_run"]
    assert "--session grind_test" in result_gic["command_to_run"]
    assert "--ts-ns 1778000000000000000" in result_gic["command_to_run"]
    assert result_gic["compiler"] == "scripts/vsd_ui_compiler.py"
    assert result_gic["compiler_version"] == "0.1.0"
    assert result_gic["manifest_schema"] == "vapi-zkba-manifest-v1"
    assert result_gic["proof_weight"] == "CHAIN_ONLY"
    assert "no chain submission" in result_gic["track1_invariant"]

    # AIT class -> NO BUILDER SHIPPED stub (only GIC has a builder at C4)
    result_ait = asyncio.run(fn(zkba_class="AIT"))
    assert result_ait["zkba_class"] == "AIT"
    assert result_ait["status"] == "NO BUILDER SHIPPED"
    assert "GIC" in result_ait["note"]

    # VHP class -> stub
    result_vhp = asyncio.run(fn(zkba_class="VHP"))
    assert result_vhp["status"] == "NO BUILDER SHIPPED"
