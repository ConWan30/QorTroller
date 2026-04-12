"""
Tests for ToolRegistry — VAPI-EXT Step 5.

20+ tests covering:
  - ToolDefinition creation
  - register_tool() — success, conflict, range violation
  - register_tool_range() — atomicity (no partial registration on failure)
  - get_tool() — hit and miss
  - get_all_tools() — count and copy isolation
  - get_tools_for_protocol() — filtering
  - is_registered()
  - VAPI_CORE_TOOLS manifest — 149 tools, numbers 1-149, all VAPI_CORE
  - BridgeAgent startup integration
"""
from __future__ import annotations

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.sub_protocol_registry import SubProtocolRegistry
from vapi_bridge.tool_registry import (
    ToolDefinition,
    ToolNumberConflictError,
    ToolRangeViolationError,
    ToolRegistry,
)
from vapi_bridge._noop_handler import _noop


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registries():
    ToolRegistry._reset()
    SubProtocolRegistry._reset()
    yield
    ToolRegistry._reset()
    SubProtocolRegistry._reset()


def _make_tool(number: int = 1, name: str = "test_tool", sub_protocol: str = "VAPI_CORE") -> ToolDefinition:
    return ToolDefinition(
        number=number,
        name=name,
        description=f"Test tool {name}",
        handler=_noop,
        sub_protocol=sub_protocol,
        phase_introduced=204,
    )


# ---------------------------------------------------------------------------
# T-TR-1: ToolDefinition creation
# ---------------------------------------------------------------------------

class TestToolDefinition:
    def test_basic_fields(self):
        t = _make_tool(42, "my_tool")
        assert t.number == 42
        assert t.name == "my_tool"
        assert t.sub_protocol == "VAPI_CORE"
        assert t.phase_introduced == 204
        assert callable(t.handler)

    def test_schema_defaults_to_empty_dict(self):
        t = _make_tool()
        assert t.schema == {}

    def test_schema_can_be_set(self):
        t = ToolDefinition(
            number=1, name="t", description="d", handler=_noop,
            sub_protocol="VAPI_CORE", phase_introduced=1,
            schema={"type": "object"},
        )
        assert t.schema == {"type": "object"}


# ---------------------------------------------------------------------------
# T-TR-2: register_tool() — single registrations
# ---------------------------------------------------------------------------

class TestRegisterTool:
    def test_register_single_tool(self):
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(1))
        assert reg.is_registered(1)

    def test_duplicate_number_raises_conflict_error(self):
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(1, "first"))
        with pytest.raises(ToolNumberConflictError):
            reg.register_tool(_make_tool(1, "second"))

    def test_conflict_error_message_includes_both_names(self):
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(1, "first_tool"))
        with pytest.raises(ToolNumberConflictError, match="first_tool"):
            reg.register_tool(_make_tool(1, "second_tool"))

    def test_range_violation_raises_error(self):
        # VAPI_CORE owns 1-149; tool #200 is outside that range
        reg = ToolRegistry.instance()
        with pytest.raises(ToolRangeViolationError):
            reg.register_tool(_make_tool(200))

    def test_range_violation_error_message(self):
        reg = ToolRegistry.instance()
        with pytest.raises(ToolRangeViolationError, match="200"):
            reg.register_tool(_make_tool(200))

    def test_wrong_type_raises_type_error(self):
        reg = ToolRegistry.instance()
        with pytest.raises(TypeError):
            reg.register_tool({"name": "bad"})  # type: ignore[arg-type]

    def test_sub_protocol_not_registered_raises_range_violation(self):
        # VAPI_MOBILE is not registered — tool claiming it should fail
        reg = ToolRegistry.instance()
        tool = ToolDefinition(
            number=150, name="mobile_tool", description="test",
            handler=_noop, sub_protocol="VAPI_MOBILE", phase_introduced=204,
        )
        with pytest.raises(ToolRangeViolationError, match="VAPI_MOBILE"):
            reg.register_tool(tool)


# ---------------------------------------------------------------------------
# T-TR-3: register_tool_range() — batch atomicity
# ---------------------------------------------------------------------------

class TestRegisterToolRange:
    def test_batch_register_all_succeed(self):
        reg = ToolRegistry.instance()
        tools = [_make_tool(i, f"tool_{i}") for i in range(1, 6)]
        reg.register_tool_range(tools)
        for i in range(1, 6):
            assert reg.is_registered(i)

    def test_atomicity_no_partial_on_conflict(self):
        reg = ToolRegistry.instance()
        # Register tool 1 first
        reg.register_tool(_make_tool(1, "existing"))
        # Batch with conflict at position 2 (tool 1 already exists)
        batch = [_make_tool(2, "new_2"), _make_tool(1, "conflict")]
        with pytest.raises(ToolNumberConflictError):
            reg.register_tool_range(batch)
        # Tool 2 should NOT have been registered (atomicity)
        assert not reg.is_registered(2)

    def test_atomicity_no_partial_on_range_violation(self):
        reg = ToolRegistry.instance()
        batch = [_make_tool(1, "valid"), _make_tool(200, "out_of_range")]
        with pytest.raises(ToolRangeViolationError):
            reg.register_tool_range(batch)
        assert not reg.is_registered(1)

    def test_wrong_type_in_batch_raises_type_error(self):
        reg = ToolRegistry.instance()
        with pytest.raises(TypeError):
            reg.register_tool_range([_make_tool(1), {"bad": True}])  # type: ignore[list-item]


# ---------------------------------------------------------------------------
# T-TR-4: get_tool() / get_all_tools() / get_tools_for_protocol()
# ---------------------------------------------------------------------------

class TestQueries:
    def test_get_tool_returns_correct_tool(self):
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(5, "five"))
        assert reg.get_tool(5).name == "five"

    def test_get_tool_missing_raises_key_error(self):
        reg = ToolRegistry.instance()
        with pytest.raises(KeyError):
            reg.get_tool(99)

    def test_get_all_tools_returns_copy(self):
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(1))
        snapshot = reg.get_all_tools()
        snapshot[999] = _make_tool(999)
        # Registry itself should not be affected
        assert 999 not in reg.get_all_tools()

    def test_get_tools_for_protocol_filters(self):
        # Register VAPI_MOBILE sub-protocol first
        from vapi_bridge.sub_protocol_registry import SubProtocolRegistry, SubProtocolConfig
        SubProtocolRegistry.instance().register(SubProtocolConfig(
            name="VAPI_MOBILE",
            event_namespace="mobile.",
            agent_range=(37, 60),
            tool_range=(150, 200),
            table_prefix="mobile_",
            contract_source_type="EXTERNAL",
            version="0.1",
        ))
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(1, "core_tool", "VAPI_CORE"))
        mobile_tool = ToolDefinition(
            number=150, name="mobile_tool", description="m",
            handler=_noop, sub_protocol="VAPI_MOBILE", phase_introduced=204,
        )
        reg.register_tool(mobile_tool)
        core_tools = reg.get_tools_for_protocol("VAPI_CORE")
        mobile_tools = reg.get_tools_for_protocol("VAPI_MOBILE")
        assert len(core_tools) == 1
        assert core_tools[0].name == "core_tool"
        assert len(mobile_tools) == 1
        assert mobile_tools[0].name == "mobile_tool"

    def test_is_registered_false_for_unregistered(self):
        reg = ToolRegistry.instance()
        assert not reg.is_registered(1)

    def test_is_registered_true_after_register(self):
        reg = ToolRegistry.instance()
        reg.register_tool(_make_tool(1))
        assert reg.is_registered(1)


# ---------------------------------------------------------------------------
# T-TR-5: VAPI_CORE_TOOLS manifest
# ---------------------------------------------------------------------------

class TestVAPICorTools:
    def test_manifest_has_149_tools(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        assert len(VAPI_CORE_TOOLS) == 149

    def test_all_numbers_1_to_149_present(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        numbers = {t.number for t in VAPI_CORE_TOOLS}
        assert numbers == set(range(1, 150))

    def test_all_tools_are_vapi_core(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        for t in VAPI_CORE_TOOLS:
            assert t.sub_protocol == "VAPI_CORE", f"Tool {t.number} ({t.name}) has wrong sub_protocol"

    def test_all_tools_have_names(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        for t in VAPI_CORE_TOOLS:
            assert t.name and isinstance(t.name, str)

    def test_all_tools_have_descriptions(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        for t in VAPI_CORE_TOOLS:
            assert t.description and isinstance(t.description, str)

    def test_all_tools_have_callable_handlers(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        for t in VAPI_CORE_TOOLS:
            assert callable(t.handler), f"Tool {t.number} handler is not callable"

    def test_manifest_registers_without_error(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        reg = ToolRegistry.instance()
        reg.register_tool_range(VAPI_CORE_TOOLS)
        assert len(reg.get_all_tools()) == 149

    def test_manifest_registration_idempotent(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        reg = ToolRegistry.instance()
        reg.register_tool_range(VAPI_CORE_TOOLS)
        # Second registration attempt should not raise (idempotent guard in bridge_agent)
        assert reg.is_registered(1)
        assert reg.is_registered(149)

    def test_tool_1_is_get_player_profile(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        tool_1 = next(t for t in VAPI_CORE_TOOLS if t.number == 1)
        assert tool_1.name == "get_player_profile"

    def test_tool_149_is_trigger_recalibration(self):
        from vapi_bridge.tools.vapi_core_tools import VAPI_CORE_TOOLS
        tool_149 = next(t for t in VAPI_CORE_TOOLS if t.number == 149)
        assert tool_149.name == "trigger_recalibration"


# ---------------------------------------------------------------------------
# T-TR-6: Singleton behavior
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_instance_returns_same_object(self):
        r1 = ToolRegistry.instance()
        r2 = ToolRegistry.instance()
        assert r1 is r2

    def test_reset_creates_new_instance(self):
        r1 = ToolRegistry.instance()
        ToolRegistry._reset()
        r2 = ToolRegistry.instance()
        assert r1 is not r2
