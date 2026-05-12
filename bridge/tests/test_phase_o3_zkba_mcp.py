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


# ---------------------------------------------------------------------------
# T-ZKBA-17: vapi_validate_zkba_manifest MCP tool registration + behavior
# (Phase O3-ZKBA-TRACK1 Lane B G4 follow-up, 2026-05-12)
# ---------------------------------------------------------------------------

def test_t_zkba_17_mcp_vapi_validate_zkba_manifest_registered():
    """Verify vapi_validate_zkba_manifest is registered with the expected
    schema shape (no required params; both 'manifest' and 'manifest_path'
    optional inputs)."""
    ks = _import_knowledge_server()
    assert "vapi_validate_zkba_manifest" in ks.TOOLS, \
        f"vapi_validate_zkba_manifest missing from TOOLS; have: {sorted(ks.TOOLS.keys())[:30]}"
    tool = ks.TOOLS["vapi_validate_zkba_manifest"]
    assert "description" in tool and "schema" in tool and "fn" in tool
    schema = tool["schema"]
    assert schema.get("type") == "object"
    # No REQUIRED params — caller supplies one of {manifest, manifest_path}
    assert schema.get("required", []) == []
    props = schema.get("properties", {})
    assert "manifest" in props
    assert "manifest_path" in props
    # Description mentions key concepts
    desc = tool["description"]
    assert "validate" in desc.lower() or "manifest" in desc.lower()
    assert "G4" in desc or "validator" in desc.lower()


def test_t_zkba_18_mcp_vapi_validate_zkba_manifest_happy_path():
    """Tool accepts an inline manifest dict + returns the validator
    ManifestValidationResult fields. Round-trip test: build a
    representative GIC manifest via scripts/zkba_manifest_validator
    helper and pass it through the MCP tool."""
    ks = _import_knowledge_server()
    fn = ks.TOOLS["vapi_validate_zkba_manifest"]["fn"]

    # Build a valid GIC manifest via the same helper used at G4
    import sys as _sys, os as _os
    _scripts = _os.path.normpath(_os.path.join(
        _os.path.dirname(__file__), "..", "..", "scripts"
    ))
    _sys.path.insert(0, _scripts)
    from zkba_manifest_validator import build_representative_manifest  # type: ignore
    from vapi_bridge.zkba_artifact import ZKBAClass  # type: ignore

    manifest = build_representative_manifest(zkba_class=ZKBAClass.GIC)
    result = asyncio.run(fn(manifest=manifest))
    assert result["valid"] is True, f"unexpected errors: {result['errors']}"
    assert result["errors"] == []
    assert result["zkba_class_name"] == "GIC"
    assert result["proof_weight_name"] == "CHAIN_ONLY"
    assert result["schema_name_form"] == "implementation"
    assert result["manifest_source"] == "inline"


def test_t_zkba_19_mcp_vapi_validate_zkba_manifest_rejects_malformed():
    """Tool returns valid=False + errors[] populated when input is
    malformed. Fail-open contract preserved end-to-end through the
    MCP boundary."""
    ks = _import_knowledge_server()
    fn = ks.TOOLS["vapi_validate_zkba_manifest"]["fn"]

    # Malformed: missing required fields
    bad = {"schema": "vapi-zkba-manifest-v1"}
    result = asyncio.run(fn(manifest=bad))
    assert result["valid"] is False
    assert len(result["errors"]) > 0
    assert any("missing required fields" in e for e in result["errors"])


def test_t_zkba_20_mcp_vapi_validate_zkba_manifest_no_input():
    """Tool returns clear error when neither 'manifest' nor
    'manifest_path' is provided."""
    ks = _import_knowledge_server()
    fn = ks.TOOLS["vapi_validate_zkba_manifest"]["fn"]
    result = asyncio.run(fn())
    assert result["valid"] is False
    assert any("must provide either" in e for e in result["errors"])
    assert result["manifest_source"] == "none"
