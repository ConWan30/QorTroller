"""
Tests for SubProtocolRegistry — VAPI-EXT Step 1.

20+ tests covering:
  - VAPI_CORE pre-registration
  - register() success paths
  - name conflict detection
  - agent_range overlap detection
  - tool_range overlap detection
  - event_namespace collision detection
  - table_prefix collision detection
  - contract_source_type collision detection
  - deactivate() behaviour
  - range ownership queries
  - singleton reset between tests
"""
from __future__ import annotations

import pytest

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from vapi_bridge.sub_protocol_registry import (
    SubProtocolConfig,
    SubProtocolConflictError,
    SubProtocolRegistry,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_cfg(**kwargs) -> SubProtocolConfig:
    """Build a minimal non-conflicting SubProtocolConfig."""
    defaults = dict(
        name="TEST_PROTO",
        event_namespace="test.",
        agent_range=(100, 200),
        tool_range=(1000, 1099),
        table_prefix="test_",
        contract_source_type="TEST",
        version="phase_test",
        dry_run=True,
        active=True,
    )
    defaults.update(kwargs)
    return SubProtocolConfig(**defaults)


# ---------------------------------------------------------------------------
# Fixture: fresh registry for each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_registry():
    SubProtocolRegistry._reset()
    yield
    SubProtocolRegistry._reset()


# ---------------------------------------------------------------------------
# T-EXT-REG-1: VAPI_CORE is pre-registered on first instance() call
# ---------------------------------------------------------------------------

class TestVapiCorePreRegistered:
    def test_vapi_core_in_registry(self):
        reg = SubProtocolRegistry.instance()
        assert reg.is_registered("VAPI_CORE")

    def test_vapi_core_is_active(self):
        reg = SubProtocolRegistry.instance()
        assert reg.is_active("VAPI_CORE")

    def test_vapi_core_agent_range(self):
        reg = SubProtocolRegistry.instance()
        cfg = reg.get("VAPI_CORE")
        assert cfg.agent_range == (1, 36)

    def test_vapi_core_tool_range(self):
        reg = SubProtocolRegistry.instance()
        cfg = reg.get("VAPI_CORE")
        assert cfg.tool_range == (1, 149)

    def test_vapi_core_contract_source_type(self):
        reg = SubProtocolRegistry.instance()
        cfg = reg.get("VAPI_CORE")
        assert cfg.contract_source_type == "VAPI"

    def test_vapi_core_no_namespace(self):
        reg = SubProtocolRegistry.instance()
        cfg = reg.get("VAPI_CORE")
        assert cfg.event_namespace == ""

    def test_vapi_core_no_table_prefix(self):
        reg = SubProtocolRegistry.instance()
        cfg = reg.get("VAPI_CORE")
        assert cfg.table_prefix == ""


# ---------------------------------------------------------------------------
# T-EXT-REG-2: Singleton behaviour
# ---------------------------------------------------------------------------

class TestSingleton:
    def test_same_instance_returned(self):
        a = SubProtocolRegistry.instance()
        b = SubProtocolRegistry.instance()
        assert a is b

    def test_reset_creates_fresh_instance(self):
        a = SubProtocolRegistry.instance()
        SubProtocolRegistry._reset()
        b = SubProtocolRegistry.instance()
        assert a is not b


# ---------------------------------------------------------------------------
# T-EXT-REG-3: Successful registration
# ---------------------------------------------------------------------------

class TestSuccessfulRegistration:
    def test_register_new_protocol(self):
        reg = SubProtocolRegistry.instance()
        cfg = _make_cfg()
        reg.register(cfg)
        assert reg.is_registered("TEST_PROTO")
        assert reg.is_active("TEST_PROTO")

    def test_get_registered_returns_all(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(name="PROTO_A", event_namespace="a.", agent_range=(100, 150),
                                tool_range=(1000, 1049), table_prefix="a_",
                                contract_source_type="PROTO_A"))
        reg.register(_make_cfg(name="PROTO_B", event_namespace="b.", agent_range=(151, 200),
                                tool_range=(1050, 1099), table_prefix="b_",
                                contract_source_type="PROTO_B"))
        registered = reg.get_registered()
        assert "VAPI_CORE" in registered
        assert "PROTO_A" in registered
        assert "PROTO_B" in registered

    def test_get_active_returns_only_active(self):
        reg = SubProtocolRegistry.instance()
        cfg = _make_cfg()
        reg.register(cfg)
        active = reg.get_active()
        assert "TEST_PROTO" in active
        assert "VAPI_CORE" in active


# ---------------------------------------------------------------------------
# T-EXT-REG-4: Name conflict
# ---------------------------------------------------------------------------

class TestNameConflict:
    def test_duplicate_name_raises(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg())
        with pytest.raises(SubProtocolConflictError, match="already registered"):
            reg.register(_make_cfg())

    def test_vapi_core_name_raises(self):
        reg = SubProtocolRegistry.instance()
        with pytest.raises(SubProtocolConflictError, match="already registered"):
            reg.register(_make_cfg(name="VAPI_CORE"))


# ---------------------------------------------------------------------------
# T-EXT-REG-5: Agent range collision
# ---------------------------------------------------------------------------

class TestAgentRangeCollision:
    def test_overlap_with_vapi_core_raises(self):
        reg = SubProtocolRegistry.instance()
        with pytest.raises(SubProtocolConflictError, match="Agent range"):
            # VAPI_CORE owns (1, 36) — requesting (30, 50) overlaps
            reg.register(_make_cfg(agent_range=(30, 50)))

    def test_adjacent_range_ok(self):
        reg = SubProtocolRegistry.instance()
        # VAPI_CORE ends at 36 — starting at 37 is fine
        reg.register(_make_cfg(agent_range=(37, 100)))
        assert reg.is_registered("TEST_PROTO")

    def test_overlap_between_two_new_protocols_raises(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(name="PROTO_A", event_namespace="a.", agent_range=(100, 150),
                                tool_range=(1000, 1049), table_prefix="a_",
                                contract_source_type="A"))
        with pytest.raises(SubProtocolConflictError, match="Agent range"):
            reg.register(_make_cfg(name="PROTO_B", event_namespace="b.", agent_range=(140, 200),
                                    tool_range=(1050, 1099), table_prefix="b_",
                                    contract_source_type="B"))


# ---------------------------------------------------------------------------
# T-EXT-REG-6: Tool range collision
# ---------------------------------------------------------------------------

class TestToolRangeCollision:
    def test_overlap_with_vapi_core_tool_range_raises(self):
        reg = SubProtocolRegistry.instance()
        with pytest.raises(SubProtocolConflictError, match="Tool range"):
            # VAPI_CORE owns tools (1, 149) — requesting (100, 200) overlaps
            reg.register(_make_cfg(tool_range=(100, 200)))

    def test_tool_range_starting_at_150_ok(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(tool_range=(150, 250)))
        assert reg.is_registered("TEST_PROTO")


# ---------------------------------------------------------------------------
# T-EXT-REG-7: Event namespace collision
# ---------------------------------------------------------------------------

class TestEventNamespaceCollision:
    def test_duplicate_namespace_raises(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(name="PROTO_A", event_namespace="mobile.", agent_range=(100, 150),
                                tool_range=(150, 200), table_prefix="a_",
                                contract_source_type="A"))
        with pytest.raises(SubProtocolConflictError, match="Event namespace"):
            reg.register(_make_cfg(name="PROTO_B", event_namespace="mobile.",
                                    agent_range=(151, 200), tool_range=(201, 250),
                                    table_prefix="b_", contract_source_type="B"))

    def test_empty_namespace_does_not_collide(self):
        """Two protocols with empty namespace should not conflict (VAPI_CORE has empty)."""
        # VAPI_CORE already has empty namespace — new protocol with non-empty is fine
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(event_namespace="mobile."))
        assert reg.is_registered("TEST_PROTO")


# ---------------------------------------------------------------------------
# T-EXT-REG-8: Table prefix collision
# ---------------------------------------------------------------------------

class TestTablePrefixCollision:
    def test_duplicate_prefix_raises(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(name="PROTO_A", event_namespace="a.", agent_range=(100, 150),
                                tool_range=(150, 200), table_prefix="mobile_",
                                contract_source_type="A"))
        with pytest.raises(SubProtocolConflictError, match="Table prefix"):
            reg.register(_make_cfg(name="PROTO_B", event_namespace="b.", agent_range=(151, 200),
                                    tool_range=(201, 250), table_prefix="mobile_",
                                    contract_source_type="B"))


# ---------------------------------------------------------------------------
# T-EXT-REG-9: contract_source_type collision
# ---------------------------------------------------------------------------

class TestContractSourceTypeCollision:
    def test_duplicate_source_type_raises(self):
        reg = SubProtocolRegistry.instance()
        with pytest.raises(SubProtocolConflictError, match="contract_source_type"):
            # VAPI_CORE uses "VAPI" — trying to register with same value fails
            reg.register(_make_cfg(contract_source_type="VAPI"))


# ---------------------------------------------------------------------------
# T-EXT-REG-10: Deactivation
# ---------------------------------------------------------------------------

class TestDeactivation:
    def test_deactivate_removes_from_active(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg())
        reg.deactivate("TEST_PROTO")
        assert reg.is_registered("TEST_PROTO")
        assert not reg.is_active("TEST_PROTO")
        active = reg.get_active()
        assert "TEST_PROTO" not in active

    def test_deactivated_ranges_no_longer_block(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(name="PROTO_A", event_namespace="a.", agent_range=(100, 150),
                                tool_range=(150, 200), table_prefix="a_",
                                contract_source_type="A"))
        reg.deactivate("PROTO_A")
        # After deactivation, the same ranges can be claimed by a new protocol
        reg.register(_make_cfg(name="PROTO_B", event_namespace="b.", agent_range=(100, 150),
                                tool_range=(150, 200), table_prefix="b_",
                                contract_source_type="B"))
        assert reg.is_active("PROTO_B")

    def test_vapi_core_cannot_be_deactivated(self):
        reg = SubProtocolRegistry.instance()
        with pytest.raises(SubProtocolConflictError):
            reg.deactivate("VAPI_CORE")

    def test_deactivate_unknown_raises(self):
        reg = SubProtocolRegistry.instance()
        with pytest.raises(KeyError):
            reg.deactivate("NONEXISTENT")


# ---------------------------------------------------------------------------
# T-EXT-REG-11: Range ownership queries
# ---------------------------------------------------------------------------

class TestRangeOwnership:
    def test_tool_range_owner_vapi_core(self):
        reg = SubProtocolRegistry.instance()
        assert reg.tool_range_owner(1) == "VAPI_CORE"
        assert reg.tool_range_owner(149) == "VAPI_CORE"
        assert reg.tool_range_owner(75) == "VAPI_CORE"

    def test_tool_range_owner_outside_all_ranges(self):
        reg = SubProtocolRegistry.instance()
        assert reg.tool_range_owner(150) is None

    def test_agent_range_owner_vapi_core(self):
        reg = SubProtocolRegistry.instance()
        assert reg.agent_range_owner(1) == "VAPI_CORE"
        assert reg.agent_range_owner(36) == "VAPI_CORE"

    def test_agent_range_owner_outside(self):
        reg = SubProtocolRegistry.instance()
        assert reg.agent_range_owner(37) is None

    def test_tool_range_owner_new_protocol(self):
        reg = SubProtocolRegistry.instance()
        reg.register(_make_cfg(tool_range=(150, 299)))
        assert reg.tool_range_owner(150) == "TEST_PROTO"
        assert reg.tool_range_owner(299) == "TEST_PROTO"
        assert reg.tool_range_owner(200) == "TEST_PROTO"
